#!/usr/bin/env python3
"""Frontier replay using independently validated artifacts mined from traces.

Unlike the earlier composition factorial, the library is built from actual
recorded BIRD tool calls and admits only queries that match their independent
gold sidecars.  Held-out target families, gold SQL, and result values remain
sealed from the model.  Raw model responses stay in an external audit file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from bird_sql_skill_factorial import call_codex
from bird_sql_trace_replay import execute_read_only, open_read_only, row_key, sql_candidate, unordered_key
from bird_trace_artifact_reuse import execute, load_tasks, load_trace_candidates


ARMS = ("no_skill", "formatting_placebo", "trace_validated_artifact_library")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_library(harness_root: Path, source_families: list[str], per_family: int) -> tuple[str, int, dict[str, int]]:
    tasks = load_tasks(harness_root)
    candidates = load_trace_candidates(harness_root, tasks)
    by_family: dict[str, list[tuple[int, str, str]]] = {family: [] for family in source_families}
    for prompt, sql in candidates.items():
        task = tasks[prompt]
        if task.database not in by_family:
            continue
        trace_result = execute(task.db_path, sql)
        gold_result = execute(task.db_path, task.gold_sql)
        if trace_result is None or gold_result is None or trace_result != gold_result:
            continue
        by_family[task.database].append((task.order, task.prompt, sql))
    rows: list[tuple[str, str, str]] = []
    counts: dict[str, int] = {}
    for family in source_families:
        selected = sorted(by_family[family])[:per_family]
        counts[family] = len(selected)
        rows.extend((family, prompt, sql) for _, prompt, sql in selected)
    if any(count != per_family for count in counts.values()):
        raise ValueError(f"validated trace library lacks a source family: {counts}")
    lines = [
        "VALIDATED TRACE-ARTIFACT LIBRARY (source families only)",
        "Every example below is an independently executed trace query whose result matched its gold outcome. These are reusable structural evidence, not answer keys. Inspect the target schema and compose only compatible joins, filters, grouping, or aggregation; never copy a query solely because wording is similar.",
    ]
    for index, (family, prompt, sql) in enumerate(rows, 1):
        lines.extend([f"ARTIFACT {index} (source_family={family})", f"Trace task: {prompt}", f"Validated SQL artifact: {sql}"])
    return "\n".join(lines), len(rows), counts


def choose_tasks(tasks: list[dict[str, Any]], heldout: list[str], per_family: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for family in heldout:
        rows = sorted((row for row in tasks if row.get("data", {}).get("db_name") == family), key=lambda row: row["task_id"])
        selected.extend(rows[:per_family])
    if len(selected) != len(heldout) * per_family:
        raise ValueError("heldout family lacks enough tasks")
    return selected


def choose_eligible_tasks(
    tasks: list[dict[str, Any]],
    heldout: list[str],
    per_family: int,
    database_dir: Path,
    gold_dir: Path,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Select only tasks whose independent gold outcome fits the bounded evaluator.

    BIRD contains questions whose answer relation has more than the replay
    cap.  Sending those tasks to the model and then treating every arm as a
    candidate error would conflate an evaluator limitation with model
    behavior.  Preflight the gold sidecar before any model call and record the
    excluded count in the receipt.
    """
    selected: list[dict[str, Any]] = []
    excluded: dict[str, int] = {}
    connections: dict[str, Any] = {}
    try:
        for family in heldout:
            rows = sorted(
                (row for row in tasks if row.get("data", {}).get("db_name") == family),
                key=lambda row: row["task_id"],
            )
            family_selected: list[dict[str, Any]] = []
            family_excluded = 0
            connection = connections.setdefault(
                family, open_read_only(database_dir / f"{family}.sqlite")
            )
            for row in rows:
                gold_path = gold_dir / f"{row['task_id']}.json"
                try:
                    gold_payload = json.loads(gold_path.read_text(encoding="utf-8"))
                    gold_sql = gold_payload["gold_sql"]
                    execute_read_only(connection, gold_sql)
                except Exception:
                    family_excluded += 1
                    continue
                family_selected.append(row)
                if len(family_selected) == per_family:
                    break
            if len(family_selected) != per_family:
                raise ValueError(
                    f"heldout family lacks enough evaluator-eligible tasks: "
                    f"{family} selected={len(family_selected)} excluded={family_excluded}"
                )
            selected.extend(family_selected)
            excluded[family] = family_excluded
    finally:
        for connection in connections.values():
            connection.close()
    return selected, excluded


def prompt_for(task: dict[str, Any], schema: str, arm: str, library: str) -> str:
    extra = ""
    if arm == "formatting_placebo":
        extra = "\nReturn only one SQL statement in a ```sql``` block."
    elif arm == "trace_validated_artifact_library":
        extra = "\nUse this independently validated trace-artifact library only for compatible structural patterns. Compose a new query for the target task; do not copy a complete source query.\n\n" + library
    return "You are a careful SQLite text-to-SQL solver. Do not use tools or the network. Return exactly one read-only SELECT or WITH statement and nothing else." + extra + "\n\nTarget schema:\n" + schema + "\nTarget question:\n" + str(task.get("prompt", ""))


def run(*, harness_root: Path, tasks_path: Path, schema_dir: Path, gold_dir: Path, database_dir: Path, heldout: list[str], source_families: list[str], per_family: int, source_per_family: int, model: str, workdir: Path, timeout: float, output: Path, raw_output: Path) -> dict[str, Any]:
    tasks = load_rows(tasks_path)
    selected, excluded_gold_tasks = choose_eligible_tasks(
        tasks, heldout, per_family, database_dir, gold_dir
    )
    library, artifact_count, source_counts = build_library(harness_root.resolve(), source_families, source_per_family)
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
                response, ok, elapsed_ms = call_codex(prompt_for(task, schema, arm, library), model, workdir, timeout)
                candidate = sql_candidate(response)
                outcome = "model_error" if not ok else "unparseable" if candidate is None else "candidate_execution_error"
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
        "schema_version": "frankengate-bird-sql-trace-mined-factorial-v1",
        "protocol": {"arms": list(ARMS), "heldout_families": heldout, "source_families": source_families, "tasks_per_family": per_family, "source_artifacts_per_family": source_per_family, "validated_trace_artifact_count": artifact_count, "source_artifact_counts": source_counts, "task_count": len(selected), "excluded_gold_ineligible_tasks": excluded_gold_tasks, "model": model, "harness": "codex-cli-subscription", "library_sha256": sha256_text(library), "gold_hidden_from_proposer": True, "source_target_families_disjoint": not set(heldout) & set(source_families), "raw_output": str(raw_output)},
        "summary": {arm: dict(sorted(values.items())) for arm, values in aggregate.items()},
        "episodes": rows,
        "claim_boundary": {"independent_family_disjoint_run": True, "trace_artifacts_independently_validated": True, "causal_artifact_utility_confirmed": False, "automatic_promotion_authorized": False, "reason": "This is a public BIRD family-disjoint frontier replay using trace-mined artifacts; promotion still requires independent verification, repeated seeds, changed-system replay, cost/negative-transfer gates, and enterprise labels."},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    raw_output.parent.mkdir(parents=True, exist_ok=True)
    raw_output.write_text(json.dumps(raw_rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--harness-root", type=Path, required=True); parser.add_argument("--tasks", type=Path, required=True); parser.add_argument("--schema-dir", type=Path, required=True); parser.add_argument("--gold-dir", type=Path, required=True); parser.add_argument("--database-dir", type=Path, required=True)
    parser.add_argument("--heldout-family", action="append", required=True); parser.add_argument("--source-family", action="append", required=True); parser.add_argument("--tasks-per-family", type=int, default=5); parser.add_argument("--source-artifacts-per-family", type=int, default=4); parser.add_argument("--model", default="gpt-5.6-luna"); parser.add_argument("--workdir", type=Path, required=True); parser.add_argument("--timeout", type=float, default=180); parser.add_argument("--output", type=Path, required=True); parser.add_argument("--raw-output", type=Path, required=True)
    args = parser.parse_args()
    run(harness_root=args.harness_root, tasks_path=args.tasks, schema_dir=args.schema_dir, gold_dir=args.gold_dir, database_dir=args.database_dir, heldout=args.heldout_family, source_families=args.source_family, per_family=args.tasks_per_family, source_per_family=args.source_artifacts_per_family, model=args.model, workdir=args.workdir, timeout=args.timeout, output=args.output, raw_output=args.raw_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
