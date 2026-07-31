#!/usr/bin/env python3
"""Independently verify a sealed BIRD skill-factorial receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def candidate_sql(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    match = re.search(r"```(?:sql)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    if match:
        text = match.group(1).strip()
    match = re.search(r"\b(?:WITH|SELECT)\b", text, flags=re.IGNORECASE)
    if not match:
        return None
    text = text[match.start() :].rstrip(";").strip()
    if ";" in text or not re.match(r"^(?:WITH|SELECT)\b", text, re.IGNORECASE):
        return None
    return text


def execute(connection: sqlite3.Connection, sql: str) -> tuple[tuple[str, ...], tuple[tuple[Any, ...], ...]]:
    cursor = connection.execute(sql)
    columns = tuple(str(item[0]) for item in (cursor.description or ()))
    return columns, tuple(tuple(row) for row in cursor.fetchall())


def verify(*, result_path: Path, raw_path: Path, tasks_path: Path, gold_dir: Path, database_dir: Path) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    raw_rows = json.loads(raw_path.read_text(encoding="utf-8"))
    task_by_hash: dict[str, dict[str, Any]] = {}
    for line in tasks_path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if isinstance(row, dict) and isinstance(row.get("task_id"), str):
            task_by_hash[sha256_text(row["task_id"])] = row
    connections: dict[str, sqlite3.Connection] = {}
    summary: dict[str, Counter[str]] = {}
    errors: Counter[str] = Counter()
    try:
        for row in raw_rows:
            arm = str(row.get("arm"))
            bucket = summary.setdefault(arm, Counter())
            response = row.get("response", "")
            if sha256_text(response) != row.get("response_sha256", sha256_text(response)):
                errors["response_hash_mismatch"] += 1
            task = task_by_hash.get(row.get("task_hash"))
            if task is None:
                errors["task_hash_missing"] += 1
                continue
            family = task.get("data", {}).get("db_name")
            if not isinstance(family, str):
                errors["family_missing"] += 1
                continue
            connection = connections.setdefault(
                family,
                sqlite3.connect(f"file:{database_dir / (family + '.sqlite')}?mode=ro&immutable=1", uri=True),
            )
            gold = json.loads((gold_dir / f"{task['task_id']}.json").read_text(encoding="utf-8"))["gold_sql"]
            try:
                gold_result = execute(connection, gold)
            except sqlite3.Error:
                errors["gold_execution_error"] += 1
                continue
            candidate = candidate_sql(response)
            if candidate is None:
                bucket["candidate_error"] += 1
                continue
            try:
                candidate_result = execute(connection, candidate)
            except sqlite3.Error:
                bucket["candidate_error"] += 1
                continue
            exact = candidate_result == gold_result
            unordered = candidate_result[0] == gold_result[0] and sorted(map(repr, candidate_result[1])) == sorted(map(repr, gold_result[1]))
            bucket["exact" if exact else "unordered" if unordered else "mismatch"] += 1
            bucket["episodes"] += 1
    finally:
        for connection in connections.values():
            connection.close()
    recomputed = {arm: dict(sorted(counter.items())) for arm, counter in summary.items()}
    expected = {
        arm: {
            key: value
            for key, value in values.items()
            if key in {"episodes", "exact", "unordered", "mismatch", "candidate_error"}
        }
        for arm, values in result.get("summary", {}).items()
    }
    return {
        "schema_version": "frankengate-bird-sql-skill-factorial-verification-v1",
        "raw_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
        "rows_verified": len(raw_rows),
        "recomputed_summary": recomputed,
        "receipt_summary_matches": recomputed == expected,
        "errors": dict(sorted(errors.items())),
        "independent_evaluator": "fresh SQLite connections and duplicated SQL extraction/comparison logic",
        "claim_boundary": {
            "verification_passed": recomputed == expected and not errors,
            "causal_skill_benefit_confirmed": False,
            "automatic_promotion_authorized": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--gold-dir", type=Path, required=True)
    parser.add_argument("--database-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verified = verify(
        result_path=args.result, raw_path=args.raw, tasks_path=args.tasks,
        gold_dir=args.gold_dir, database_dir=args.database_dir,
    )
    args.output.write_text(json.dumps(verified, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(verified, sort_keys=True))
    return 0 if verified["claim_boundary"]["verification_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
