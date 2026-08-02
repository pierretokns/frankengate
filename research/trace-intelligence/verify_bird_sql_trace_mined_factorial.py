#!/usr/bin/env python3
"""Independently verify the trace-mined BIRD frontier factorial.

The runner deliberately keeps raw model responses outside the repository. This
verifier joins the external raw rows to the aggregate receipt by task hash,
re-extracts SQL, and replays each candidate and gold query over fresh immutable
SQLite connections. It also distinguishes a candidate execution error from a
gold/evaluator failure; the first run exposed why that distinction matters.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
import time
from collections import Counter
from pathlib import Path
from typing import Any


MAX_ROWS = 10_000
MAX_RESULT_BYTES = 8 * 1024 * 1024
MAX_SQL_SECONDS = 2.0


class ReplayLimit(Exception):
    """A query exceeded the bounded retrospective evaluator."""


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sql_candidate(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    fenced = re.search(r"```(?:sql)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    match = re.search(r"\b(?:WITH|SELECT)\b", text, flags=re.IGNORECASE)
    if not match:
        return None
    text = text[match.start() :].rstrip(";").strip()
    if ";" in text or not re.match(r"^(?:WITH|SELECT)\b", text, re.IGNORECASE):
        return None
    return text


def execute(connection: sqlite3.Connection, sql: str) -> tuple[tuple[str, ...], tuple[tuple[Any, ...], ...]]:
    deadline = time.monotonic() + MAX_SQL_SECONDS
    connection.set_progress_handler(
        lambda: 1 if time.monotonic() >= deadline else 0,
        10_000,
    )
    try:
        cursor = connection.execute(sql)
        columns = tuple(str(item[0]) for item in (cursor.description or ()))
        rows: list[tuple[Any, ...]] = []
        result_bytes = 0
        while True:
            batch = cursor.fetchmany(512)
            if not batch:
                break
            rows.extend(tuple(row) for row in batch)
            result_bytes += sum(len(repr(row)) for row in batch)
            if len(rows) > MAX_ROWS or result_bytes > MAX_RESULT_BYTES:
                raise ReplayLimit
        return columns, tuple(rows)
    except sqlite3.OperationalError as exc:
        if "interrupted" in str(exc).lower():
            raise ReplayLimit from exc
        raise
    finally:
        connection.set_progress_handler(None, 0)


def unordered(result: tuple[tuple[str, ...], tuple[tuple[Any, ...], ...]], gold: tuple[tuple[str, ...], tuple[tuple[Any, ...], ...]]) -> bool:
    return result[0] == gold[0] and sorted(map(repr, result[1])) == sorted(map(repr, gold[1]))


def verify(*, result_path: Path, raw_path: Path, tasks_path: Path, gold_dir: Path, database_dir: Path) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    raw_rows = json.loads(raw_path.read_text(encoding="utf-8"))
    task_by_hash: dict[str, dict[str, Any]] = {}
    for line in tasks_path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if isinstance(row, dict) and isinstance(row.get("task_id"), str):
            task_by_hash[sha256_text(row["task_id"])] = row
    episode_by_key = {
        (row.get("arm"), row.get("task_hash")): row
        for row in result.get("episodes", [])
    }
    summary: dict[str, Counter[str]] = {}
    errors: Counter[str] = Counter()
    connections: dict[str, sqlite3.Connection] = {}
    try:
        for raw in raw_rows:
            arm = str(raw.get("arm"))
            task_hash = raw.get("task_hash")
            bucket = summary.setdefault(arm, Counter())
            bucket["episodes"] += 1
            episode = episode_by_key.get((raw.get("arm"), task_hash))
            if episode is None:
                errors["receipt_episode_missing"] += 1
            else:
                if episode.get("response_sha256") != sha256_text(str(raw.get("response", ""))):
                    errors["response_hash_mismatch"] += 1
            task = task_by_hash.get(task_hash)
            if task is None:
                errors["task_hash_missing"] += 1
                bucket["task_join_error"] += 1
                continue
            family = task.get("data", {}).get("db_name")
            if not isinstance(family, str):
                errors["family_missing"] += 1
                bucket["task_join_error"] += 1
                continue
            connection = connections.setdefault(
                family,
                sqlite3.connect(
                    f"file:{database_dir / (family + '.sqlite')}?mode=ro&immutable=1",
                    uri=True,
                ),
            )
            gold = json.loads((gold_dir / f"{task['task_id']}.json").read_text(encoding="utf-8"))["gold_sql"]
            try:
                gold_result = execute(connection, gold)
            except (ReplayLimit, sqlite3.Error):
                errors["gold_execution_error"] += 1
                bucket["gold_execution_error"] += 1
                continue
            candidate = sql_candidate(raw.get("response"))
            if candidate is None:
                bucket["candidate_unparseable"] += 1
                continue
            try:
                candidate_result = execute(connection, candidate)
            except (ReplayLimit, sqlite3.Error):
                bucket["candidate_execution_error"] += 1
                continue
            if candidate_result == gold_result:
                bucket["exact"] += 1
            elif unordered(candidate_result, gold_result):
                bucket["unordered"] += 1
            else:
                bucket["mismatch"] += 1
    finally:
        for connection in connections.values():
            connection.close()

    recomputed = {arm: dict(sorted(counter.items())) for arm, counter in summary.items()}
    # The run that produced the receipt used the less precise historical label
    # candidate_error. Normalize that label only for comparison; no outcome is
    # silently converted into a success.
    expected: dict[str, dict[str, Any]] = {}
    for arm, values in result.get("summary", {}).items():
        normalized = {
            ("candidate_execution_error" if key == "candidate_error" else key): value
            for key, value in values.items()
            if key in {"episodes", "exact", "unordered", "mismatch", "candidate_error", "candidate_execution_error", "candidate_unparseable", "gold_execution_error", "task_join_error"}
        }
        expected[arm] = normalized
    return {
        "schema_version": "frankengate-bird-sql-trace-mined-factorial-verification-v1",
        "raw_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
        "rows_verified": len(raw_rows),
        "recomputed_summary": recomputed,
        "normalized_receipt_summary": expected,
        "receipt_summary_matches": recomputed == expected,
        "errors": dict(sorted(errors.items())),
        "independent_evaluator": "fresh immutable SQLite connections with duplicated SQL extraction, execution, and result comparison",
        "claim_boundary": {
            "verification_passed": recomputed == expected and not errors,
            "causal_skill_benefit_confirmed": False,
            "automatic_promotion_authorized": False,
            "reason": "Verification confirms accounting and replay only; one family-disjoint frontier run is not a promotion claim.",
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
        result_path=args.result,
        raw_path=args.raw,
        tasks_path=args.tasks,
        gold_dir=args.gold_dir,
        database_dir=args.database_dir,
    )
    args.output.write_text(json.dumps(verified, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(verified, sort_keys=True))
    return 0 if verified["claim_boundary"]["verification_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
