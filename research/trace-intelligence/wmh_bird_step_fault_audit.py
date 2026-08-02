#!/usr/bin/env python3
"""Audit SkillAdaptor/AgentRx-style step fault attribution on WMH-BIRD.

The corpus has recorded tool trajectories, rewards, and gold SQL sidecars. We
replay every extracted SQL command and compare it with the gold result. For a
failed trajectory we report the first structural mismatch category (or an
execution error); for a trajectory with a later correct SQL we record recovery.
This is a *gold-diff proxy* for step attribution, not a causal diagnosis or a
skill-improvement intervention.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from sqlglot import exp, parse_one

from bird_trace_artifact_reuse import canonical_rows, extract_sql


SCHEMA_VERSION = "frankengate-wmh-bird-step-fault-audit-v1"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def attrs(span: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for item in span.get("attributes", []):
        if not isinstance(item, dict) or not isinstance(item.get("key"), str):
            continue
        value = item.get("value")
        if isinstance(value, dict) and isinstance(value.get("stringValue"), str):
            values[item["key"]] = value["stringValue"]
    return values


def table_names(sql: str) -> set[str]:
    try:
        return {node.name.casefold() for node in parse_one(sql, read="sqlite").find_all(exp.Table)}
    except Exception:
        return set(re.findall(r"\b(?:FROM|JOIN|UPDATE|INTO)\s+([A-Za-z_][A-Za-z0-9_]*)", sql, re.I))


def column_names(sql: str) -> set[str]:
    try:
        return {node.name.casefold() for node in parse_one(sql, read="sqlite").find_all(exp.Column)}
    except Exception:
        return set()


def fault_category(candidate: str, gold: str) -> str:
    try:
        actual = parse_one(candidate, read="sqlite")
        expected = parse_one(gold, read="sqlite")
    except Exception:
        return "parse_or_other"
    if table_names(candidate) != table_names(gold):
        return "table_selection"
    if column_names(candidate) != column_names(gold):
        return "projection_or_column"
    actual_where = actual.find(exp.Where)
    expected_where = expected.find(exp.Where)
    if (actual_where is None) != (expected_where is None) or (actual_where and expected_where and actual_where.sql() != expected_where.sql()):
        return "predicate"
    if len(list(actual.find_all(exp.Join))) != len(list(expected.find_all(exp.Join))):
        return "join_condition"
    if bool(actual.find(exp.Group)) != bool(expected.find(exp.Group)) or bool(actual.find(exp.Having)) != bool(expected.find(exp.Having)):
        return "aggregation"
    if bool(actual.find(exp.Order)) != bool(expected.find(exp.Order)) or bool(actual.find(exp.Limit)) != bool(expected.find(exp.Limit)):
        return "ordering_or_limit"
    return "literal_or_other"


def execute(connection: sqlite3.Connection, sql: str) -> tuple[str, tuple[tuple[str, ...], ...] | None]:
    steps = [0]

    def progress() -> int:
        steps[0] += 1
        return int(steps[0] > 200_000)

    connection.set_progress_handler(progress, 1_000)
    try:
        return "ok", canonical_rows(connection.execute(sql).fetchall())
    except sqlite3.Error:
        return "error", None
    finally:
        connection.set_progress_handler(None, 0)


def run(traces_path: Path, manifest: Path, db_root: Path, gold_root: Path, output: Path) -> dict[str, Any]:
    db_map = {str((row := json.loads(line))["task_id"]): str(row["data"]["db_name"]) for line in manifest.open(encoding="utf-8")}
    gold_map = {path.stem: json.loads(path.read_text(encoding="utf-8"))["gold_sql"] for path in gold_root.glob("bird-train-*.json")}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for line in traces_path.open(encoding="utf-8", errors="replace"):
        span = json.loads(line)
        if isinstance(span.get("traceId"), str):
            grouped[span["traceId"]].append(span)

    # Repeated model runs are useful for outcome variance, but not needed for
    # this step-attribution mechanics audit. Keep one deterministic trace per
    # task/reward bucket so one pathological query cannot dominate runtime.
    selected_ids: set[str] = set()
    per_bucket: dict[tuple[str, str], list[str]] = defaultdict(list)
    for trace_id, spans in grouped.items():
        metadata: dict[str, Any] = {}
        for span in spans:
            raw_metadata = attrs(span).get("wmh.trace.metadata")
            if raw_metadata:
                try:
                    metadata = json.loads(raw_metadata)
                except json.JSONDecodeError:
                    pass
        base = str(metadata.get("base_task_id", ""))
        if not base:
            continue
        reward = str(int(float(metadata.get("reward", 0.0))))
        per_bucket[(base, reward)].append(trace_id)
    for trace_ids in per_bucket.values():
        selected_ids.add(sorted(trace_ids)[0])
    source_trace_count = len(grouped)
    grouped = {trace_id: spans for trace_id, spans in grouped.items() if trace_id in selected_ids}
    result_cache: dict[tuple[str, str], tuple[str, tuple[tuple[str, ...], ...] | None]] = {}
    rows: list[dict[str, Any]] = []
    aggregate: Counter[str] = Counter()
    category_by_reward: Counter[str] = Counter()
    for trace_id, spans in sorted(grouped.items()):
        ordered = sorted(spans, key=lambda span: int(span.get("startTimeUnixNano", 0)))
        metadata: dict[str, Any] = {}
        commands: list[str] = []
        for span in ordered:
            values = attrs(span)
            raw_metadata = values.get("wmh.trace.metadata")
            if raw_metadata:
                try:
                    metadata = json.loads(raw_metadata)
                except json.JSONDecodeError:
                    pass
            raw_arguments = values.get("gen_ai.tool.call.arguments")
            if raw_arguments:
                try:
                    command = json.loads(raw_arguments).get("command", "")
                except (TypeError, json.JSONDecodeError):
                    command = ""
                sql = extract_sql(command) if isinstance(command, str) else None
                if sql:
                    commands.append(sql)
        base = str(metadata.get("base_task_id", ""))
        if base not in db_map or base not in gold_map:
            aggregate["skipped_missing_gold_or_manifest"] += 1
            continue
        db_name = db_map[base]
        db_path = db_root / db_name / f"{db_name}.sqlite"
        connection = sqlite3.connect(db_path)
        try:
            cache_key = (db_name, gold_map[base])
            gold_status, gold_rows = result_cache.get(cache_key, ("missing", None))
            if cache_key not in result_cache:
                gold_status, gold_rows = execute(connection, gold_map[base])
                result_cache[cache_key] = (gold_status, gold_rows)
            outcomes: list[str] = []
            categories: list[str] = []
            for sql in commands:
                cache_key = (db_name, sql)
                status, rows_value = result_cache.get(cache_key, ("missing", None))
                if cache_key not in result_cache:
                    status, rows_value = execute(connection, sql)
                    result_cache[cache_key] = (status, rows_value)
                if status != "ok":
                    outcomes.append("execution_error")
                    categories.append("execution_error")
                elif gold_status == "ok" and rows_value == gold_rows:
                    outcomes.append("correct")
                    categories.append("correct")
                else:
                    category = fault_category(sql, gold_map[base])
                    outcomes.append(category)
                    categories.append(category)
        finally:
            connection.close()
        try:
            reward = float(metadata.get("reward", 0.0))
        except (TypeError, ValueError):
            reward = 0.0
        reward_key = str(int(reward))
        aggregate["traces"] += 1
        aggregate[f"reward_{reward_key}"] += 1
        aggregate["sql_traces"] += int(bool(outcomes))
        aggregate["sql_steps"] += len(outcomes)
        correct_indices = [index for index, outcome in enumerate(outcomes) if outcome == "correct"]
        first = outcomes[0] if outcomes else "no_sql"
        aggregate[f"first_{first}"] += 1
        category_by_reward[f"reward_{reward_key}:{first}"] += 1
        if correct_indices:
            aggregate["has_correct_sql"] += 1
            aggregate[f"correct_step_{correct_indices[0] + 1}"] += 1
        if correct_indices and first != "correct":
            aggregate["recovered_after_first_fault"] += 1
        rows.append({
            "trace_hash": hashlib.sha256(trace_id.encode()).hexdigest(),
            "base_task_hash": hashlib.sha256(base.encode()).hexdigest(),
            "db_name": db_name,
            "reward": reward,
            "sql_steps": len(outcomes),
            "first_outcome": first,
            "correct_step": correct_indices[0] + 1 if correct_indices else None,
            "recovered_after_first_fault": bool(correct_indices and first != "correct"),
        })
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source": {"traces_sha256": file_hash(traces_path), "manifest_sha256": file_hash(manifest), "gold_sha256": hashlib.sha256("".join(path.read_text(encoding="utf-8") for path in sorted(gold_root.glob("bird-train-*.json"))).encode()).hexdigest(), "raw_content_committed": False},
        "aggregate": {"source_trace_count": source_trace_count, "selected_trace_count": len(rows), **dict(sorted(aggregate.items()))},
        "category_by_reward": dict(sorted(category_by_reward.items())),
        "rows": rows,
        "claim_boundary": {"gold_diff_step_proxy_measured": True, "causal_fault_attribution_established": False, "skill_revision_utility_measured": False, "enterprise_transfer_established": False, "reason": "Gold-result and AST differences identify a replay discrepancy, not the true first human/model cause. No targeted revision was applied and no skill utility intervention was run."},
    }
    result["result_sha256"] = hashlib.sha256(json.dumps(result, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["aggregate"], sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--traces", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--db-root", type=Path, required=True)
    parser.add_argument("--gold-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.traces, args.manifest, args.db_root, args.gold_root, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
