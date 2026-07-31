#!/usr/bin/env python3
"""Replay recorded BIRD-SQL candidate queries without emitting trace content.

The HF corpus stores candidate SQL in the trace metadata and tool outputs in
separate OTel spans. This verifier joins only by the opaque trace id in memory,
executes the candidate and pinned gold query against a fresh read-only SQLite
connection, and writes aggregate-only evidence. It is intentionally a
retrospective replay check, not a model intervention or a claim about natural
user behavior.
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


SCHEMA_VERSION = "frankengate-bird-sql-trace-replay-v1"
MAX_ROWS = 10_000
MAX_RESULT_BYTES = 8 * 1024 * 1024
MAX_SQL_SECONDS = 2.0


class ReplayLimit(Exception):
    """A query exceeded the bounded retrospective evaluator limits."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def attribute_map(span: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in span.get("attributes", []):
        if not isinstance(item, dict) or not isinstance(item.get("key"), str):
            continue
        value = item.get("value")
        if not isinstance(value, dict):
            continue
        for key in ("stringValue", "intValue", "doubleValue", "boolValue"):
            if key in value:
                result[item["key"]] = value[key]
                break
    return result


def load_traces(path: Path) -> dict[str, dict[str, Any]]:
    traces: dict[str, dict[str, Any]] = {}
    malformed = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                span = json.loads(line)
            except json.JSONDecodeError:
                malformed += 1
                continue
            if not isinstance(span, dict) or not isinstance(span.get("traceId"), str):
                malformed += 1
                continue
            attrs = attribute_map(span)
            metadata_raw = attrs.get("wmh.trace.metadata")
            if isinstance(metadata_raw, str):
                try:
                    metadata = json.loads(metadata_raw)
                except json.JSONDecodeError:
                    metadata = None
                if isinstance(metadata, dict):
                    traces.setdefault(span["traceId"], {}).update(
                        {"metadata": metadata}
                    )
    return traces


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
    text = text[match.start() :].strip()
    # Only one read-only statement is eligible for this verifier.
    if ";" in text.rstrip(";"):
        return None
    text = text.rstrip(";").strip()
    if not re.match(r"^(?:WITH|SELECT)\b", text, flags=re.IGNORECASE):
        return None
    return text


def open_read_only(database: Path) -> sqlite3.Connection:
    """Open one immutable read-only connection per database for this run."""
    return sqlite3.connect(f"file:{database}?mode=ro&immutable=1", uri=True)


def execute_read_only(
    connection: sqlite3.Connection, sql: str
) -> tuple[tuple[str, ...], list[tuple[Any, ...]]]:
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
        return columns, rows
    except sqlite3.OperationalError as exc:
        if "interrupted" in str(exc).lower():
            raise ReplayLimit from exc
        raise
    finally:
        connection.set_progress_handler(None, 0)


def row_key(columns: tuple[str, ...], rows: list[tuple[Any, ...]]) -> tuple[Any, ...]:
    # Include column order and multiplicity for the primary verdict.
    return (columns, tuple(rows))


def unordered_key(columns: tuple[str, ...], rows: list[tuple[Any, ...]]) -> tuple[Any, ...]:
    return (columns, tuple(sorted((repr(row) for row in rows))))


def run(
    *, trace_path: Path, task_path: Path, gold_dir: Path, database_dir: Path,
    max_traces: int | None = None,
) -> dict[str, Any]:
    traces = load_traces(trace_path)
    tasks: dict[str, dict[str, Any]] = {}
    with task_path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            value = json.loads(line)
            if isinstance(value, dict) and isinstance(value.get("task_id"), str):
                tasks[value["task_id"]] = value

    counts: Counter[str] = Counter()
    by_reward: dict[str, Counter[str]] = {"0": Counter(), "1": Counter(), "other": Counter()}
    models: Counter[str] = Counter()
    connections: dict[str, sqlite3.Connection] = {}
    gold_cache: dict[str, tuple[tuple[str, ...], list[tuple[Any, ...]]] | None] = {}
    try:
      for index, item in enumerate(traces.values()):
        if max_traces is not None and index >= max_traces:
            break
        metadata = item.get("metadata")
        if not isinstance(metadata, dict):
            counts["missing_metadata"] += 1
            continue
        counts["traces_with_metadata"] += 1
        base_task_id = metadata.get("base_task_id")
        task = tasks.get(base_task_id) if isinstance(base_task_id, str) else None
        if task is None:
            counts["task_join_missing"] += 1
            continue
        db_name = task.get("data", {}).get("db_name") if isinstance(task.get("data"), dict) else None
        if not isinstance(db_name, str):
            counts["database_join_missing"] += 1
            continue
        gold_path = gold_dir / f"{base_task_id}.json"
        database_path = database_dir / f"{db_name}.sqlite"
        if not gold_path.is_file() or not database_path.is_file():
            counts["replay_artifact_missing"] += 1
            continue
        gold = json.loads(gold_path.read_text(encoding="utf-8"))
        gold_sql = gold.get("gold_sql") if isinstance(gold, dict) else None
        candidate = sql_candidate(metadata.get("final_answer"))
        reward = metadata.get("reward")
        reward_bucket = "1" if reward == 1.0 else "0" if reward == 0.0 else "other"
        model = metadata.get("model")
        if isinstance(model, str):
            models[model] += 1
        by_reward[reward_bucket]["traces"] += 1
        if not isinstance(gold_sql, str):
            counts["gold_sql_missing"] += 1
            by_reward[reward_bucket]["gold_missing"] += 1
            continue
        connection = connections.setdefault(db_name, open_read_only(database_path))
        if base_task_id in gold_cache:
            gold_result = gold_cache[base_task_id]
        else:
          try:
            gold_result = execute_read_only(connection, gold_sql)
          except ReplayLimit:
            gold_result = "__LIMIT__"
          except sqlite3.Error:
            gold_result = None
          gold_cache[base_task_id] = gold_result
        if gold_result == "__LIMIT__":
            counts["gold_result_limit"] += 1
            by_reward[reward_bucket]["gold_result_limit"] += 1
            continue
        if gold_result is None:
            counts["gold_execution_error"] += 1
            by_reward[reward_bucket]["gold_execution_error"] += 1
            continue
        counts["gold_executed"] += 1
        by_reward[reward_bucket]["gold_executed"] += 1
        if candidate is None:
            counts["candidate_unparseable"] += 1
            by_reward[reward_bucket]["candidate_unparseable"] += 1
            continue
        counts["candidate_parseable"] += 1
        try:
            candidate_result = execute_read_only(connection, candidate)
        except ReplayLimit:
            counts["candidate_result_limit"] += 1
            by_reward[reward_bucket]["candidate_result_limit"] += 1
            continue
        except sqlite3.Error:
            counts["candidate_execution_error"] += 1
            by_reward[reward_bucket]["candidate_execution_error"] += 1
            continue
        counts["candidate_executed"] += 1
        by_reward[reward_bucket]["candidate_executed"] += 1
        exact = row_key(*candidate_result) == row_key(*gold_result)
        unordered = unordered_key(*candidate_result) == unordered_key(*gold_result)
        counts["exact_match" if exact else "not_exact_match"] += 1
        counts["unordered_match" if unordered else "not_unordered_match"] += 1
        by_reward[reward_bucket]["exact_match" if exact else "not_exact_match"] += 1
        by_reward[reward_bucket]["unordered_match" if unordered else "not_unordered_match"] += 1

    finally:
      for connection in connections.values():
        connection.close()

    return {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "trace_file_sha256": sha256_file(trace_path),
            "task_file_sha256": sha256_file(task_path),
            "trace_file": trace_path.name,
            "task_file": task_path.name,
            "gold_sidecar_count": len(list(gold_dir.glob("*.json"))),
            "database_count": len(list(database_dir.glob("*.sqlite"))),
        },
        "counts": dict(sorted(counts.items())),
        "by_reward": {key: dict(sorted(value.items())) for key, value in by_reward.items()},
        "models": dict(sorted(models.items())),
        "claim_boundary": {
            "replay_executed": counts["candidate_executed"] > 0,
            "causal_skill_benefit_confirmed": False,
            "natural_user_behavior_confirmed": False,
            "reason": "This is retrospective candidate-versus-gold execution matching on SQLite; it does not measure a new intervention or preserve OTel parentage/latency.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--traces", type=Path, required=True)
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--gold-dir", type=Path, required=True)
    parser.add_argument("--database-dir", type=Path, required=True)
    parser.add_argument("--max-traces", type=int, default=None)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(
        trace_path=args.traces,
        task_path=args.tasks,
        gold_dir=args.gold_dir,
        database_dir=args.database_dir,
        max_traces=args.max_traces,
    )
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
