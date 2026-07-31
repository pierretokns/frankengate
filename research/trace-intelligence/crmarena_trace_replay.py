#!/usr/bin/env python3
"""Replay CRMArena recorded SQL tool calls against the pinned org database."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-crmarena-trace-replay-v1"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def attrs(span: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for item in span.get("attributes", []):
        if not isinstance(item, dict) or not isinstance(item.get("key"), str):
            continue
        value = item.get("value")
        if isinstance(value, dict):
            for key in ("stringValue", "intValue", "doubleValue", "boolValue"):
                if key in value:
                    values[item["key"]] = value[key]
                    break
    return values


def canonical_rows(connection: sqlite3.Connection, sql: str) -> list[dict[str, Any]]:
    cursor = connection.execute(sql)
    columns = [str(item[0]) for item in (cursor.description or ())]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def extract_sql(command: Any) -> str | None:
    if not isinstance(command, str):
        return None
    try:
        parts = shlex.split(command)
    except ValueError:
        return None
    for index, part in enumerate(parts[:-1]):
        if part.endswith("query.py"):
            candidate = parts[index + 1].strip()
            if candidate.upper().startswith(("SELECT", "WITH")):
                return candidate
    return None


def run(*, traces: Path, database: Path, output: Path) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    malformed = 0
    with traces.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                span = json.loads(line)
            except json.JSONDecodeError:
                malformed += 1
                continue
            if isinstance(span, dict) and isinstance(span.get("traceId"), str):
                grouped.setdefault(span["traceId"], []).append(span)

    counts: Counter[str] = Counter()
    rewards: Counter[str] = Counter()
    connection = sqlite3.connect(f"file:{database}?mode=ro&immutable=1", uri=True)
    try:
        for spans in grouped.values():
            metadata: dict[str, Any] | None = None
            for span in spans:
                values = attrs(span)
                raw = values.get("wmh.trace.metadata")
                if isinstance(raw, str):
                    try:
                        parsed = json.loads(raw)
                    except json.JSONDecodeError:
                        parsed = None
                    if isinstance(parsed, dict):
                        metadata = parsed
            if metadata is None:
                counts["missing_metadata"] += 1
                continue
            counts["traces_with_metadata"] += 1
            reward = metadata.get("reward")
            rewards["1" if reward == 1.0 else "0" if reward == 0.0 else "other"] += 1
            pending_sql: str | None = None
            for span in spans:
                values = attrs(span)
                operation = values.get("gen_ai.operation.name")
                if operation == "chat":
                    raw_args = values.get("gen_ai.tool.call.arguments")
                    if isinstance(raw_args, str):
                        try:
                            args = json.loads(raw_args)
                        except json.JSONDecodeError:
                            args = None
                        command = args.get("command") if isinstance(args, dict) else None
                        pending_sql = extract_sql(command)
                elif operation == "execute_tool":
                    recorded = values.get("gen_ai.tool.message")
                    if pending_sql is None:
                        counts["non_query_tool_result"] += 1
                        continue
                    counts["query_tool_calls"] += 1
                    if not isinstance(recorded, str):
                        counts["missing_recorded_result"] += 1
                        pending_sql = None
                        continue
                    try:
                        expected = json.loads(recorded)
                        actual = canonical_rows(connection, pending_sql)
                    except json.JSONDecodeError:
                        counts["recorded_observation_not_json"] += 1
                        pending_sql = None
                        continue
                    except (sqlite3.Error, TypeError):
                        counts["replay_error"] += 1
                        pending_sql = None
                        continue
                    if actual == expected:
                        counts["exact_result_match"] += 1
                    else:
                        counts["result_mismatch"] += 1
                    pending_sql = None
    finally:
        connection.close()

    result = {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "trace_sha256": sha256_file(traces),
            "database_sha256": sha256_file(database),
            "trace_file": traces.name,
            "database_file": database.name,
        },
        "counts": dict(sorted(counts.items())),
        "rewards": dict(sorted(rewards.items())),
        "malformed_spans": malformed,
        "claim_boundary": {
            "replay_executed": counts["query_tool_calls"] > 0,
            "causal_skill_benefit_confirmed": False,
            "full_otel_fidelity_confirmed": False,
            "reason": "Recorded SQL tool calls and observations were replayed against the pinned SQLite org; this does not establish causal skill utility or production Salesforce behavior.",
        },
    }
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--traces", type=Path, required=True)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(traces=args.traces, database=args.database, output=args.output)["counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
