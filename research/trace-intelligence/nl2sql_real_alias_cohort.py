#!/usr/bin/env python3
"""Build a content-free manifest and external raw cohort for real NL2SQL alias retrieval.

The cohort is derived from the pinned Defog PostgreSQL questions and the pinned
database DDL.  Raw questions and SQL stay outside Git.  The manifest records
only hashes, counts, and construction rules; benchmark receipts can therefore
be reviewed without publishing the underlying source text.

This is deliberately a *retrieval* cohort, not semantic-alias ground truth.
Targets are schema objects referenced by the gold SQL.  Cases whose question
contains no target surface are labelled ``implicit_target`` for stratification,
not as proven semantic aliases.  Cross-database distractors and scope-swapped
NIL cases provide wrong-system and abstention pressure for the next blinded
frontier/SME adjudication pass.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "frankengate-nl2sql-real-alias-cohort-v1"
DATABASES = ("broker", "car_dealership", "derm_treatment", "ewallet")
SOURCE_FILES = (
    "questions_gen_postgres.csv",
    "instruct_basic_postgres.csv",
    "instruct_advanced_postgres.csv",
)
SEED = 20260803
WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]{1,}")
CREATE_RE = re.compile(
    r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([A-Za-z_][A-Za-z0-9_.]*)\s*\((.*?)\);",
    re.IGNORECASE | re.DOTALL,
)
FROM_RE = re.compile(
    r"\b(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_.]*)\s*(?:(?:AS\s+)?([A-Za-z_][A-Za-z0-9_]*))?",
    re.IGNORECASE,
)
QUALIFIED_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\b")
SQL_WORDS = {
    "select", "from", "where", "join", "left", "right", "inner", "outer", "full",
    "on", "and", "or", "as", "group", "by", "order", "having", "limit", "offset",
    "with", "union", "all", "distinct", "case", "when", "then", "else", "end",
    "asc", "desc", "null", "is", "not", "in", "exists", "between", "like", "ilike",
    "true", "false", "count", "sum", "avg", "min", "max", "coalesce", "cast",
    "date", "interval", "current", "date_trunc", "extract", "over", "partition",
    "row_number", "dense_rank", "rank", "as", "asc", "desc",
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode())


def normalize(value: str) -> str:
    value = value.strip('"`').lower().replace("_", "")
    if value.endswith("ies") and len(value) > 4:
        return value[:-3] + "y"
    if value.endswith("es") and len(value) > 4:
        return value[:-2]
    if value.endswith("s") and len(value) > 3:
        return value[:-1]
    return value


def schema_from_ddl(path: Path) -> dict[str, list[str]]:
    tables: dict[str, list[str]] = {}
    text = path.read_text(encoding="utf-8")
    for match in CREATE_RE.finditer(text):
        table = match.group(1).split(".")[-1].lower()
        columns: list[str] = []
        for line in match.group(2).splitlines():
            line = line.strip()
            if not line or line.startswith("--"):
                continue
            column = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\s+", line)
            if column:
                columns.append(column.group(1).lower())
        tables[table] = columns
    if not tables:
        raise ValueError(f"no CREATE TABLE statements found in {path}")
    return tables


def sql_tables(sql: str, schema: dict[str, list[str]]) -> tuple[dict[str, str], list[str]]:
    aliases: dict[str, str] = {}
    referenced: list[str] = []
    for match in FROM_RE.finditer(sql):
        table = match.group(1).split(".")[-1].lower()
        alias = (match.group(2) or "").lower()
        if table not in schema:
            continue
        referenced.append(table)
        aliases[table] = table
        aliases[table.lower()] = table
        if alias and alias not in SQL_WORDS:
            aliases[alias] = table
    return aliases, list(dict.fromkeys(referenced))


def gold_targets(sql: str, schema: dict[str, list[str]]) -> list[dict[str, str]]:
    aliases, referenced_tables = sql_tables(sql, schema)
    columns = {column for values in schema.values() for column in values}
    targets: set[tuple[str, str]] = set()
    # Keep table references themselves as retrieval targets.
    for table in referenced_tables:
        targets.add((table, table))
    for left, right in QUALIFIED_RE.findall(sql):
        left = left.lower()
        right = right.lower()
        table = aliases.get(left)
        if table and right in schema.get(table, []):
            targets.add((table, right))
    # Unqualified references are assigned only to referenced tables containing
    # the column.  This avoids treating SQL aliases and CTE names as schema IDs.
    sql_without_qualified = QUALIFIED_RE.sub(" ", sql)
    for token in WORD_RE.findall(sql_without_qualified.lower()):
        if token in columns and token not in SQL_WORDS:
            matches = [table for table in referenced_tables if token in schema.get(table, [])]
            if matches:
                targets.update((table, token) for table in matches)
    return [{"table": table, "identifier": identifier} for table, identifier in sorted(targets)]


def question_tokens(question: str) -> set[str]:
    return {token.lower() for token in WORD_RE.findall(question) if token.lower() not in SQL_WORDS}


def exact_surface(question: str, identifier: str) -> bool:
    return any(normalize(token) == normalize(identifier) for token in question_tokens(question))


def lexical_score(question: str, candidate: dict[str, str]) -> float:
    query = question_tokens(question)
    terms = set(WORD_RE.findall((candidate["table"] + " " + candidate["identifier"]).lower()))
    exact = sum(normalize(token) == normalize(candidate["identifier"]) for token in query)
    return exact * 10.0 + len(query & terms) + (0.5 if normalize(candidate["table"]) in {normalize(t) for t in query} else 0.0)


def _candidate(db: str, table: str, identifier: str) -> dict[str, str]:
    return {"db": db, "table": table, "identifier": identifier}


def _case_id(source: str, row_number: int, question: str, scope_db: str) -> str:
    digest = sha256_json([source, row_number, question, scope_db])[:16]
    return f"defog-alias:{digest}"


def _build_real_cases(rows: list[dict[str, Any]], schemas: dict[str, dict[str, list[str]]], *, per_category: int) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    candidates_by_db: dict[str, list[dict[str, str]]] = {
        db: [_candidate(db, table, identifier) for table, columns in schemas[db].items() for identifier in [table, *columns]]
        for db in DATABASES
    }
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        db = row["db_name"]
        targets = gold_targets(row["query"], schemas[db])
        if not targets:
            continue
        category = "explicit_target" if any(exact_surface(row["question"], target["identifier"]) for target in targets) else "implicit_target"
        row = dict(row)
        row["targets"] = targets
        row["category"] = category
        grouped[f"{db}:{category}"].append(row)
    rng = random.Random(SEED)
    for key, group in sorted(grouped.items()):
        group.sort(key=lambda row: sha256_json([row["_source"], row["_row"], row["question"]]))
        db, category = key.split(":", 1)
        selected = group[:per_category]
        for row in selected:
            target_keys = {(target["table"], target["identifier"]) for target in row["targets"]}
            all_current = candidates_by_db[db]
            ranked = sorted(all_current, key=lambda candidate: (-lexical_score(row["question"], candidate), candidate["table"], candidate["identifier"]))
            pool: dict[tuple[str, str, str], dict[str, str]] = {}
            for target in row["targets"]:
                pool[(db, target["table"], target["identifier"])] = _candidate(db, target["table"], target["identifier"])
            # Add lexical same-scope alternatives.
            for candidate in ranked[:10]:
                pool[(candidate["db"], candidate["table"], candidate["identifier"])] = candidate
            target_norms = {normalize(target["identifier"]) for target in row["targets"]}
            # Cross-scope exact-morphology collisions are deliberate hard negatives.
            for other_db in DATABASES:
                if other_db == db:
                    continue
                for candidate in candidates_by_db[other_db]:
                    if normalize(candidate["identifier"]) in target_norms:
                        pool[(candidate["db"], candidate["table"], candidate["identifier"])] = candidate
            # Never truncate away a gold target or a deliberately inserted
            # cross-scope collision.  Fill the remaining slots by lexical
            # order so the candidate set is both bounded and reproducible.
            ordered = sorted(
                pool.values(),
                key=lambda candidate: (
                    (candidate["db"], candidate["table"], candidate["identifier"])
                    not in {(db, target["table"], target["identifier"]) for target in row["targets"]},
                    candidate["db"] != db,
                    -lexical_score(row["question"], candidate),
                    candidate["table"],
                    candidate["identifier"],
                ),
            )
            required = [candidate for candidate in ordered if candidate["db"] == db and (candidate["table"], candidate["identifier"]) in target_keys]
            collisions = [candidate for candidate in ordered if candidate["db"] != db and normalize(candidate["identifier"]) in target_norms]
            candidates = []
            for candidate in [*required, *collisions, *ordered]:
                key = (candidate["db"], candidate["table"], candidate["identifier"])
                if key not in {(item["db"], item["table"], item["identifier"]) for item in candidates}:
                    candidates.append(candidate)
                if len(candidates) >= 20:
                    break
            cases.append({
                "case_id": _case_id(row["_source"], row["_row"], row["question"], db),
                "source": {"file": row["_source"], "row": row["_row"], "question_sha256": sha256_bytes(row["question"].encode())},
                "question": row["question"],
                "scope_db": db,
                "category": category,
                "target_objects": [{"db": db, **target} for target in row["targets"]],
                "candidates": candidates,
            })
    # Scope-swapped NILs use a real question but a database family with no
    # matching target object.  Exclude every object whose key appeared in the
    # source target set so the NIL construction is explicit and reproducible.
    for row in sorted(rows, key=lambda value: sha256_json([value["_source"], value["_row"]])):
        source_db = row["db_name"]
        targets = gold_targets(row["query"], schemas[source_db])
        if not targets:
            continue
        target_keys = {(target["table"], target["identifier"]) for target in targets}
        for scope_db in DATABASES:
            if scope_db == source_db:
                continue
            if any((candidate["table"], candidate["identifier"]) in target_keys for candidate in candidates_by_db[scope_db]):
                continue
            candidates = sorted(candidates_by_db[scope_db], key=lambda candidate: (-lexical_score(row["question"], candidate), candidate["table"], candidate["identifier"]))[:12]
            cases.append({
                "case_id": _case_id(row["_source"], row["_row"], row["question"], scope_db),
                "source": {"file": row["_source"], "row": row["_row"], "question_sha256": sha256_bytes(row["question"].encode())},
                "question": row["question"],
                "scope_db": scope_db,
                "category": "scope_swapped_nil",
                "target_objects": [],
                "candidates": candidates,
            })
            if sum(case["category"] == "scope_swapped_nil" for case in cases) >= per_category * len(DATABASES):
                break
        if sum(case["category"] == "scope_swapped_nil" for case in cases) >= per_category * len(DATABASES):
            break
    return sorted(cases, key=lambda case: case["case_id"])


def build(source_root: Path, ddl_root: Path, *, per_category: int = 4) -> tuple[dict[str, Any], dict[str, Any]]:
    schemas = {db: schema_from_ddl(ddl_root / db / f"{db}.sql") for db in DATABASES}
    rows: list[dict[str, Any]] = []
    source_hashes: dict[str, str] = {}
    for source_name in SOURCE_FILES:
        source = source_root / source_name
        source_hashes[source_name] = sha256_bytes(source.read_bytes())
        with source.open(encoding="utf-8", newline="") as handle:
            for row_number, row in enumerate(csv.DictReader(handle)):
                if row.get("db_name") in DATABASES:
                    row["_source"] = source_name
                    row["_row"] = row_number
                    rows.append(row)
    ddl_hashes = {db: sha256_bytes((ddl_root / db / f"{db}.sql").read_bytes()) for db in DATABASES}
    cases = _build_real_cases(rows, schemas, per_category=per_category)
    raw = {
        "schema_version": SCHEMA_VERSION,
        "seed": SEED,
        "cases": cases,
        "source": {"csv_sha256": source_hashes, "ddl_sha256": ddl_hashes, "raw_content_committed": False},
    }
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "seed": SEED,
        "sources": {"csv_sha256": source_hashes, "ddl_sha256": ddl_hashes, "enterprise_rows": len(rows)},
        "cases": {
            "count": len(cases),
            "categories": dict(sorted(Counter(case["category"] for case in cases).items())),
            "candidate_count": {"min": min(map(lambda case: len(case["candidates"]), cases)), "max": max(map(lambda case: len(case["candidates"]), cases))},
            "targeted_cases": sum(bool(case["target_objects"]) for case in cases),
            "scope_swapped_nil_cases": sum(case["category"] == "scope_swapped_nil" for case in cases),
        },
        "selection": {"per_db_per_target_category": per_category, "candidate_pool": "target objects + lexical same-scope candidates + exact-morphology cross-scope collisions; scope-swapped NILs exclude source targets"},
        "raw_sha256": sha256_json(raw),
        "claim_boundary": "Real public NL2SQL retrieval cohort with gold-SQL target objects and constructed scope-swapped NILs. It is not SME semantic-alias truth or evidence of downstream agent utility.",
    }
    return raw, manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--ddl-root", type=Path, required=True)
    parser.add_argument("--raw-output", type=Path, required=True)
    parser.add_argument("--manifest-output", type=Path, required=True)
    parser.add_argument("--per-category", type=int, default=4)
    args = parser.parse_args()
    raw, manifest = build(args.source_root, args.ddl_root, per_category=args.per_category)
    args.raw_output.parent.mkdir(parents=True, exist_ok=True)
    args.raw_output.write_text(json.dumps(raw, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    args.manifest_output.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"cases": manifest["cases"], "raw_sha256": manifest["raw_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
