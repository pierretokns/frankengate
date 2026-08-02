#!/usr/bin/env python3
"""Family-disjoint BIRD-SQL replay with a validated subplan library arm.

The library is built only from evidence-family gold SQL. Target-family rows,
gold SQL, and result values remain sealed from the model. The experiment is a
composition/transfer test, not a claim that raw SQL examples are a safe
production memory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import time
from collections import Counter
from pathlib import Path
from typing import Any

from bird_sql_skill_factorial import call_codex
from bird_sql_trace_replay import execute_read_only, open_read_only, sql_candidate, row_key, unordered_key


ARMS = ("no_skill", "formatting_placebo", "composable_subplan_library")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_tasks(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_library(tasks: list[dict[str, Any]], *, gold_dir: Path, source_families: list[str], per_family: int) -> str:
    rows: list[dict[str, Any]] = []
    for family in source_families:
        candidates = sorted(
            (row for row in tasks if row.get("data", {}).get("db_name") == family),
            key=lambda row: str(row.get("task_id")),
        )[:per_family]
        for row in candidates:
            task_id = row["task_id"]
            gold = json.loads((gold_dir / f"{task_id}.json").read_text(encoding="utf-8"))["gold_sql"]
            rows.append({"family": family, "question": row["prompt"], "sql": gold})
    if not rows:
        raise ValueError("validated source library is empty")
    lines = [
        "VALIDATED SUBPLAN LIBRARY (source families only)",
        "These examples are evidence, not answer keys. Reuse compatible joins, filters, grouping, or aggregation patterns; never copy a complete query merely because the wording is similar.",
        "Inspect the target schema, map target identifiers, execute the newly composed query, and abstain if no compatible pattern exists.",
    ]
    for index, row in enumerate(rows, 1):
        lines.extend([f"EXAMPLE {index} (source_family={row['family']})", f"Question: {row['question']}", f"Validated SQL: {row['sql']}"])
    return "\n".join(lines)


def prompt_for(task: dict[str, Any], schema: str, arm: str, library: str) -> str:
    extra = ""
    if arm == "formatting_placebo":
        extra = "\nReturn only one SQL statement in a ```sql``` block."
    elif arm == "composable_subplan_library":
        extra = "\nUse this validated subplan library only as a source of compatible patterns. Compose a new query for the target task; do not copy a whole source query.\n\n" + library
    return (
        "You are a careful SQLite text-to-SQL solver. Do not use tools or the network. "
        "Return exactly one read-only SELECT or WITH statement and nothing else."
        + extra + "\n\nTarget schema:\n" + schema + "\nTarget question:\n" + str(task.get("prompt", ""))
    )


def choose_tasks(tasks: list[dict[str, Any]], heldout: list[str], per_family: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for family in heldout:
        rows = sorted((row for row in tasks if row.get("data", {}).get("db_name") == family), key=lambda row: row["task_id"])
        selected.extend(rows[:per_family])
    if len(selected) != len(heldout) * per_family:
        raise ValueError("heldout family lacks enough tasks")
    return selected


def run(*, tasks_path: Path, schema_dir: Path, gold_dir: Path, database_dir: Path, heldout: list[str], source_families: list[str], per_family: int, source_per_family: int, model: str, workdir: Path, timeout: float, output: Path, raw_output: Path) -> dict[str, Any]:
    tasks = load_tasks(tasks_path)
    selected = choose_tasks(tasks, heldout, per_family)
    library = build_library(tasks, gold_dir=gold_dir, source_families=source_families, per_family=source_per_family)
    library_hash = sha256_text(library)
    connections: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []
    raw_rows: list[dict[str, Any]] = []
    aggregate: dict[str, Counter[str]] = {arm: Counter() for arm in ARMS}
    try:
        for task in selected:
            family = task["data"]["db_name"]
            schema = (schema_dir / f"{family}.sql").read_text(encoding="utf-8")
            gold = json.loads((gold_dir / f"{task['task_id']}.json").read_text(encoding="utf-8"))["gold_sql"]
            connection = connections.setdefault(family, open_read_only(database_dir / f"{family}.sqlite"))
            try:
                gold_result = execute_read_only(connection, gold)
            except Exception:
                gold_result = None
            for arm in ARMS:
                prompt = prompt_for(task, schema, arm, library)
                response, ok, elapsed_ms = call_codex(prompt, model, workdir, timeout)
                candidate = sql_candidate(response)
                outcome = "model_error" if not ok else "unparseable" if candidate is None else "candidate_error"
                exact = unordered = False
                if candidate is not None and gold_result is not None:
                    try:
                        result = execute_read_only(connection, candidate)
                        exact = row_key(*result) == row_key(*gold_result)
                        unordered = unordered_key(*result) == unordered_key(*gold_result)
                        outcome = "exact" if exact else "unordered" if unordered else "mismatch"
                    except Exception:
                        pass
                aggregate[arm][outcome] += 1
                aggregate[arm]["episodes"] += 1
                aggregate[arm]["elapsed_ms_total"] += round(elapsed_ms, 3)
                task_hash = sha256_text(task["task_id"])
                rows.append({"arm": arm, "family": family, "task_hash": task_hash, "model": model, "response_sha256": sha256_text(response), "outcome": outcome, "exact": exact, "unordered": unordered, "elapsed_ms": round(elapsed_ms, 3)})
                raw_rows.append({"arm": arm, "family": family, "task_hash": task_hash, "response": response})
    finally:
        for connection in connections.values():
            connection.close()
    result = {
        "schema_version": "frankengate-bird-sql-composable-factorial-v1",
        "protocol": {"arms": list(ARMS), "heldout_families": heldout, "source_families": source_families, "tasks_per_heldout_family": per_family, "source_examples_per_family": source_per_family, "task_count": len(selected), "model": model, "harness": "codex-cli-subscription", "library_sha256": library_hash, "gold_hidden_from_proposer": True, "source_target_families_disjoint": not set(heldout) & set(source_families)},
        "summary": {arm: dict(sorted(values.items())) for arm, values in aggregate.items()},
        "episodes": rows,
        "claim_boundary": {"independent_family_disjoint_run": True, "causal_subplan_benefit_confirmed": False, "automatic_promotion_authorized": False, "reason": "Validated source examples are tested as a composition arm on held-out BIRD families; promotion still requires independent verification, more families/seeds, changed-system replay, and cost/negative-transfer gates."},
    }
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    raw_output.write_text(json.dumps(raw_rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", type=Path, required=True); parser.add_argument("--schema-dir", type=Path, required=True); parser.add_argument("--gold-dir", type=Path, required=True); parser.add_argument("--database-dir", type=Path, required=True)
    parser.add_argument("--heldout-family", action="append", required=True); parser.add_argument("--source-family", action="append", required=True)
    parser.add_argument("--tasks-per-family", type=int, default=5); parser.add_argument("--source-examples-per-family", type=int, default=4)
    parser.add_argument("--model", default="gpt-5.6-luna"); parser.add_argument("--workdir", type=Path, required=True); parser.add_argument("--timeout", type=float, default=180); parser.add_argument("--output", type=Path, required=True); parser.add_argument("--raw-output", type=Path, required=True)
    args = parser.parse_args()
    run(tasks_path=args.tasks, schema_dir=args.schema_dir, gold_dir=args.gold_dir, database_dir=args.database_dir, heldout=args.heldout_family, source_families=args.source_family, per_family=args.tasks_per_family, source_per_family=args.source_examples_per_family, model=args.model, workdir=args.workdir, timeout=args.timeout, output=args.output, raw_output=args.raw_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

