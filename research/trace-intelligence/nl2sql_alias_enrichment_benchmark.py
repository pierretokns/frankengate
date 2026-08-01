#!/usr/bin/env python3
"""Measure whether train-only approved aliases improve NL2SQL object retrieval.

This is a public-proxy retrieval experiment, not semantic-alias ground truth.
The raw Defog rows and schema remain external; the receipt contains hashes and
aggregate metrics only. Alias links are learned from training questions and
gold-SQL target identifiers, then evaluated on a deterministic row holdout.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from nl2sql_real_alias_cohort import DATABASES, gold_targets, normalize, question_tokens, schema_from_ddl


WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]{1,}")
SOURCE_FILES = (
    "questions_gen_postgres.csv",
    "instruct_basic_postgres.csv",
    "instruct_advanced_postgres.csv",
)
SCHEMA_VERSION = "frankengate-nl2sql-alias-enrichment-v1"
SEED = 20260804


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def stable_hash(value: Any) -> str:
    return sha256_bytes(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())


def lexical_score(question: str, candidate: dict[str, str]) -> float:
    query = question_tokens(question)
    terms = set(WORD_RE.findall((candidate["table"] + " " + candidate["identifier"]).lower()))
    exact = sum(normalize(token) == normalize(candidate["identifier"]) for token in query)
    return exact * 10.0 + len(query & terms) + (0.5 if normalize(candidate["table"]) in {normalize(t) for t in query} else 0.0)


def load_rows(source_root: Path) -> tuple[list[dict[str, Any]], dict[str, str]]:
    rows: list[dict[str, Any]] = []
    hashes: dict[str, str] = {}
    for source_name in SOURCE_FILES:
        path = source_root / source_name
        hashes[source_name] = sha256_bytes(path.read_bytes())
        with path.open(encoding="utf-8", newline="") as handle:
            for row_number, row in enumerate(csv.DictReader(handle)):
                if row.get("db_name") not in DATABASES:
                    continue
                row = dict(row)
                row["_source"] = source_name
                row["_row"] = row_number
                row["_id"] = stable_hash([source_name, row_number, row.get("question", ""), row.get("db_name", "")])
                rows.append(row)
    return rows, hashes


def is_holdout(row: dict[str, Any]) -> bool:
    # Stable 30% holdout, independent of input ordering.
    return int(row["_id"][:8], 16) % 10 < 3


def build_alias_maps(train_rows: list[dict[str, Any]], schemas: dict[str, dict[str, list[str]]]) -> dict[str, dict[str, dict[str, int]]]:
    counts: dict[str, dict[str, Counter[str]]] = {db: defaultdict(Counter) for db in DATABASES}
    for row in train_rows:
        db = row["db_name"]
        targets = gold_targets(row["query"], schemas[db])
        for surface in question_tokens(row["question"]):
            for target in targets:
                identifier = target["identifier"].lower()
                # The baseline already normalizes morphology. Measure only
                # surface forms that add information beyond that baseline.
                if normalize(surface) == normalize(identifier):
                    continue
                counts[db][surface][identifier] += 1
    return {db: {surface: dict(counter) for surface, counter in values.items()} for db, values in counts.items()}


def approved_aliases(alias_counts: dict[str, dict[str, dict[str, int]]], min_support: int) -> dict[str, dict[str, set[str]]]:
    approved: dict[str, dict[str, set[str]]] = {db: {} for db in DATABASES}
    for db, surfaces in alias_counts.items():
        for surface, identifiers in surfaces.items():
            kept = {identifier for identifier, count in identifiers.items() if count >= min_support}
            # Ambiguous surface forms are not auto-approved; they become NIL
            # or review candidates rather than wrong-system links.
            if len(kept) == 1:
                approved[db][surface] = kept
    return approved


def candidate_pool(db: str, schemas: dict[str, dict[str, list[str]]], target_ids: set[str]) -> list[dict[str, str]]:
    candidates: list[dict[str, str]] = []
    for table, columns in schemas[db].items():
        candidates.append({"db": db, "table": table, "identifier": table})
        candidates.extend({"db": db, "table": table, "identifier": column} for column in columns)
    # Preserve explicit cross-system same-surface negatives.
    for other_db in DATABASES:
        if other_db == db:
            continue
        for table, columns in schemas[other_db].items():
            for identifier in [table, *columns]:
                if normalize(identifier) in {normalize(value) for value in target_ids}:
                    candidates.append({"db": other_db, "table": table, "identifier": identifier})
    return candidates


def rank(case: dict[str, Any], aliases: dict[str, set[str]], alias_bonus: float) -> list[int]:
    question = case["question"]
    tokens = question_tokens(question)
    alias_targets = {target for token in tokens for target in aliases.get(token, set())}
    candidates = case["candidates"]
    return sorted(
        range(len(candidates)),
        key=lambda index: (
            lexical_score(question, candidates[index])
            + (alias_bonus if candidates[index]["identifier"].lower() in alias_targets else 0.0),
            candidates[index]["db"] == case["scope_db"],
            candidates[index]["table"],
            candidates[index]["identifier"],
        ),
        reverse=True,
    )


def case_metrics(case: dict[str, Any], order: list[int]) -> dict[str, float | int | None]:
    target_keys = {(target["db"], target["table"], target["identifier"]) for target in case["target_objects"]}
    positions = [position for position, index in enumerate(order, start=1) if tuple(case["candidates"][index].values()) in target_keys]
    first = min(positions) if positions else None
    target_norms = {normalize(target["identifier"]) for target in case["target_objects"]}
    wrong_before = 0.0
    if first is not None:
        wrong_before = float(any(
            case["candidates"][index]["db"] != case["scope_db"]
            and normalize(case["candidates"][index]["identifier"]) in target_norms
            for index in order[: first - 1]
        ))
    return {
        "mrr": 1.0 / first if first else 0.0,
        "recall_at_1": float(first == 1),
        "recall_at_5": float(first is not None and first <= 5),
        "wrong_system_before_target": wrong_before,
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {"cases": len(rows)}
    for key in ("mrr", "recall_at_1", "recall_at_5", "wrong_system_before_target"):
        values = [float(row[key]) for row in rows]
        result[key] = round(sum(values) / len(values), 6) if values else None
    return result


def run(source_root: Path, ddl_root: Path, output: Path) -> dict[str, Any]:
    rows, source_hashes = load_rows(source_root)
    schemas = {db: schema_from_ddl(ddl_root / db / f"{db}.sql") for db in DATABASES}
    train_rows = [row for row in rows if not is_holdout(row)]
    test_rows = [row for row in rows if is_holdout(row)]
    alias_counts = build_alias_maps(train_rows, schemas)
    maps = {"support1": approved_aliases(alias_counts, 1), "support2": approved_aliases(alias_counts, 2)}
    cases: list[dict[str, Any]] = []
    for row in test_rows:
        db = row["db_name"]
        targets = [{"db": db, **target} for target in gold_targets(row["query"], schemas[db])]
        if not targets:
            continue
        candidates = candidate_pool(db, schemas, {target["identifier"] for target in targets})
        cases.append({
            "id": row["_id"],
            "question": row["question"],
            "scope_db": db,
            "target_objects": targets,
            "candidates": candidates,
        })
    per_arm: dict[str, list[dict[str, Any]]] = {"lexical": [], "alias_support1": [], "alias_support2": []}
    covered = {"support1": 0, "support2": 0}
    total_targets = 0
    for case in cases:
        total_targets += len(case["target_objects"])
        for arm, aliases, bonus in (
            ("lexical", {}, 0.0),
            ("alias_support1", maps["support1"].get(case["scope_db"], {}), 5.0),
            ("alias_support2", maps["support2"].get(case["scope_db"], {}), 5.0),
        ):
            order = rank(case, aliases, bonus)
            per_arm[arm].append(case_metrics(case, order))
        for support in ("support1", "support2"):
            aliases = maps[support].get(case["scope_db"], {})
            for target in case["target_objects"]:
                if target["identifier"].lower() in {value for token in question_tokens(case["question"]) for value in aliases.get(token, set())}:
                    covered[support] += 1
    result = {
        "schema_version": SCHEMA_VERSION,
        "dataset": {
            "source_files_sha256": source_hashes,
            "row_count": len(rows),
            "train_rows": len(train_rows),
            "test_rows": len(test_rows),
            "evaluated_cases": len(cases),
            "target_count": total_targets,
            "raw_content_committed": False,
        },
        "split": {"seed": SEED, "rule": "stable row hash, first hexadecimal digit bucket modulo 10 < 3", "source_row_overlap": 0},
        "alias_learning": {
            "support1_unique_links": sum(len(values) for db in maps["support1"].values() for values in db.values()),
            "support2_unique_links": sum(len(values) for db in maps["support2"].values() for values in db.values()),
            "ambiguous_surface_count": sum(1 for db in alias_counts.values() for values in db.values() if len(values) > 1),
            "target_coverage": {key: {"covered_targets": value, "total_targets": total_targets, "rate": round(value / total_targets, 6) if total_targets else 0.0} for key, value in covered.items()},
        },
        "aggregate": {arm: aggregate(values) for arm, values in per_arm.items()},
        "claim_boundary": "Public Defog gold-SQL target-object proxy. Alias links are train-only exact surface-to-gold-identifier associations; they are not SME semantic aliases. No enterprise utility, changed-schema replay, or human quality label is claimed.",
    }
    result["result_sha256"] = stable_hash(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--ddl-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.source_root, args.ddl_root, args.output)
    print(json.dumps({"aggregate": result["aggregate"], "alias_learning": result["alias_learning"], "result_sha256": result["result_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
