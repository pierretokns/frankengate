#!/usr/bin/env python3
"""Measure retrieval of parameterized SQL artifacts with explicit NILs.

This is a dataset-grounded retrieval probe, not an execution or enterprise
quality benchmark.  It uses the public Defog PostgreSQL CSVs, normalizes SQL
literals into a structural template, and creates deterministic parameter
mutations of source questions.  Questions from the held-out generated file
whose normalized template is absent from the source pool are explicit proxy
NILs.  Raw questions and SQL remain outside the repository; the receipt stores
hashes and aggregates only.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from sqlglot import exp, parse_one


SCHEMA_VERSION = "frankengate-parameterized-artifact-retrieval-v1"
TOKEN_RE = re.compile(r"[a-z][a-z0-9_]+")
STOPWORDS = frozenset(
    "a an and are as at by for from how in into is of on or per return the to what which with"
    .split()
)
DATE_RE = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")
DAYS_RE = re.compile(r"\b(\d+)\s+days\b", re.IGNORECASE)
TOP_RE = re.compile(r"\btop\s+(\d+)\b", re.IGNORECASE)
LIMIT_RE = re.compile(r"\bLIMIT\s+(\d+)\b", re.IGNORECASE)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def question_tokens(value: str) -> frozenset[str]:
    return frozenset(token for token in TOKEN_RE.findall(value.lower()) if token not in STOPWORDS)


def template_sql(sql: str) -> str:
    """Replace literals while retaining table/column/operator structure."""
    parsed = parse_one(sql, read="postgres")
    normalized = parsed.transform(
        lambda node: exp.Placeholder() if isinstance(node, exp.Literal) else node
    )
    return normalized.sql(dialect="postgres", pretty=False)


def mutate_question(question: str, index: int) -> str:
    """Change only common parameter expressions, deterministically."""
    value = question
    value, days = DAYS_RE.subn(lambda match: f"{int(match.group(1)) + 15} days", value, count=1)
    if not days:
        value, _ = TOP_RE.subn(lambda match: f"top {int(match.group(1)) + 2}", value, count=1)
    if index % 2 == 0:
        value = DATE_RE.sub(
            lambda match: f"{int(match.group(1)) + 1}-{match.group(2)}-{match.group(3)}",
            value,
            count=1,
        )
    # Keep the intent fixed while changing the surface form.  This makes the
    # lexical arm a real baseline instead of a near-duplicate string match.
    replacements = (
        (r"\bWhat are\b", "Report"),
        (r"\bHow many\b", "Count"),
        (r"\bReturn\b", "Provide"),
        (r"\bnumber of\b", "count of"),
        (r"\btotal transaction amount\b", "aggregate transaction value"),
        (r"\btop\b", "highest"),
        (r"\binclusive of\b", "including"),
    )
    for pattern, replacement in replacements:
        value = re.sub(pattern, replacement, value, count=1, flags=re.IGNORECASE)
    if value == question:
        value = f"For a different reporting parameter, {question[0].lower() + question[1:]}"
    return value


def mutate_sql(sql: str, index: int) -> str:
    value, days = re.subn(
        r"INTERVAL\s+'(\d+)\s+days'",
        lambda match: f"INTERVAL '{int(match.group(1)) + 15} days'",
        sql,
        count=1,
        flags=re.IGNORECASE,
    )
    if not days:
        value, _ = LIMIT_RE.subn(lambda match: f"LIMIT {int(match.group(1)) + 2}", value, count=1)
    if index % 2 == 0:
        value = DATE_RE.sub(
            lambda match: f"{int(match.group(1)) + 1}-{match.group(2)}-{match.group(3)}",
            value,
            count=1,
        )
    return value


def load_rows(path: Path, databases: set[str]) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]
    return [row for row in rows if row.get("db_name") in databases and row.get("question") and row.get("query")]


def rank(target: dict[str, Any], candidates: list[dict[str, Any]], arm: str) -> list[dict[str, Any]]:
    target_tokens = target["tokens"]
    scored: list[tuple[float, float, str, dict[str, Any]]] = []
    for candidate in candidates:
        overlap = len(target_tokens & candidate["tokens"])
        lexical = overlap / len(target_tokens) if target_tokens else 0.0
        template = float(target["template"] == candidate["template"])
        if arm == "lexical":
            primary, secondary = lexical, template
        elif arm == "template":
            primary, secondary = template, lexical
        elif arm == "template_gate":
            if not template:
                continue
            primary, secondary = template, lexical
        else:
            raise ValueError(f"unknown arm: {arm}")
        scored.append((primary, secondary, candidate["id"], candidate))
    scored.sort(key=lambda row: (-row[0], -row[1], row[2]))
    return [row[3] for row in scored]


def reciprocal_rank(ranked: list[dict[str, Any]], expected_id: str) -> float:
    for index, candidate in enumerate(ranked, 1):
        if candidate["id"] == expected_id:
            return 1.0 / index
    return 0.0


def run(source_basic: Path, source_advanced: Path, target_path: Path, databases: set[str], output: Path) -> dict[str, Any]:
    source_rows = load_rows(source_basic, databases) + load_rows(source_advanced, databases)
    candidates: list[dict[str, Any]] = []
    parse_failures: Counter[str] = Counter()
    for index, row in enumerate(source_rows):
        try:
            template = template_sql(row["query"])
        except Exception as exc:  # preserve a typed data-quality count
            parse_failures[type(exc).__name__] += 1
            continue
        candidates.append(
            {
                "id": f"source:{row['db_name']}:{index}:{sha256_text(row['question'])[:16]}",
                "database": row["db_name"],
                "tokens": question_tokens(row["question"]),
                "template": sha256_text(template),
                "question_sha256": sha256_text(row["question"]),
                "sql_sha256": sha256_text(row["query"]),
            }
        )
    if not candidates:
        raise ValueError("no source artifacts were admitted")
    by_db = {database: [candidate for candidate in candidates if candidate["database"] == database] for database in databases}

    positive_targets: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates):
        if index >= len(source_rows):
            break
        row = source_rows[index]
        mutated_question = mutate_question(row["question"], index)
        mutated_sql = mutate_sql(row["query"], index)
        try:
            template = sha256_text(template_sql(mutated_sql))
        except Exception:
            continue
        positive_targets.append(
            {
                "id": f"positive:{index}:{sha256_text(mutated_question)[:16]}",
                "database": row["db_name"],
                "tokens": question_tokens(mutated_question),
                "template": template,
                "expected_id": candidate["id"],
                "question_sha256": sha256_text(mutated_question),
            }
        )

    target_rows = load_rows(target_path, databases)
    source_templates = {database: {candidate["template"] for candidate in by_db[database]} for database in databases}
    nil_targets: list[dict[str, Any]] = []
    for index, row in enumerate(target_rows):
        try:
            template = sha256_text(template_sql(row["query"]))
        except Exception:
            continue
        if template in source_templates[row["db_name"]]:
            continue
        nil_targets.append(
            {
                "id": f"nil:{index}:{sha256_text(row['question'])[:16]}",
                "database": row["db_name"],
                "tokens": question_tokens(row["question"]),
                "template": template,
                "expected_id": None,
                "question_sha256": sha256_text(row["question"]),
            }
        )

    arms = ("lexical", "template", "template_gate")
    aggregate: dict[str, Counter[str]] = {arm: Counter() for arm in arms}
    rows: list[dict[str, Any]] = []
    for target_kind, targets in (("parameter_mutation", positive_targets), ("template_nil", nil_targets)):
        for target in targets:
            pool = by_db[target["database"]]
            for arm in arms:
                ranked = rank(target, pool, arm)
                top = ranked[0] if ranked else None
                expected_id = target["expected_id"]
                correct = bool(expected_id and top and top["id"] == expected_id)
                abstained = not bool(ranked)
                if target_kind == "parameter_mutation":
                    aggregate[arm]["targets"] += 1
                    aggregate[arm]["top1_correct"] += int(correct)
                    aggregate[arm]["top5_correct"] += int(any(c["id"] == expected_id for c in ranked[:5]))
                    aggregate[arm]["mrr_sum"] += reciprocal_rank(ranked, expected_id)
                    aggregate[arm]["template_available"] += int(any(c["template"] == target["template"] for c in pool))
                else:
                    aggregate[arm]["nil_targets"] += 1
                    aggregate[arm]["abstained_nil"] += int(abstained)
                    aggregate[arm]["false_accept_nil"] += int(not abstained)
                rows.append(
                    {
                        "kind": target_kind,
                        "target_id_sha256": sha256_text(target["id"]),
                        "database": target["database"],
                        "arm": arm,
                        "ranked_count": len(ranked),
                        "top1_correct": correct,
                        "abstained": abstained,
                        "template_available": any(c["template"] == target["template"] for c in pool),
                    }
                )

    for arm, values in aggregate.items():
        targets = values.get("targets", 0)
        values["mrr"] = round(values.get("mrr_sum", 0.0) / targets, 6) if targets else 0.0
        values.pop("mrr_sum", None)

    receipt = {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "basic_sha256": file_sha256(source_basic),
            "advanced_sha256": file_sha256(source_advanced),
            "target_sha256": file_sha256(target_path),
            "databases": sorted(databases),
            "candidate_count": len(candidates),
            "parameter_mutation_count": len(positive_targets),
            "template_nil_count": len(nil_targets),
            "parse_failures": dict(sorted(parse_failures.items())),
            "raw_content_committed": False,
        },
        "retrieval": {
            "arms": list(arms),
            "scope_filter": True,
            "template": "SQL AST literals replaced with placeholders",
            "nil_definition": "held-out target normalized SQL template absent from same-database source pool",
        },
        "aggregate": {arm: dict(sorted(values.items())) for arm, values in aggregate.items()},
        "rows": rows,
        "claim_boundary": {
            "parameterized_retrieval_measured": True,
            "explicit_proxy_nil_abstention_measured": True,
            "sql_execution_oracle_used": False,
            "enterprise_semantic_quality_established": False,
            "reason": "Public Defog structural retrieval probe; parameter mutations inherit source intent and NILs are template-absence proxies, not SME labels.",
        },
    }
    receipt["result_sha256"] = hashlib.sha256(stable_json(receipt)).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"aggregate": receipt["aggregate"], "result_sha256": receipt["result_sha256"]}, sort_keys=True))
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-basic", type=Path, required=True)
    parser.add_argument("--source-advanced", type=Path, required=True)
    parser.add_argument("--targets", type=Path, required=True)
    parser.add_argument("--database", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.source_basic.resolve(), args.source_advanced.resolve(), args.targets.resolve(), set(args.database), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
