#!/usr/bin/env python3
"""Run a small family-disjoint frontier-model skill factorial for BIRD-SQL.

The proposer sees only the task and schema. Gold SQL and gold results stay in
the evaluator process and are never passed to Codex. Only hashes and aggregate
outcomes are written.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from bird_sql_trace_replay import (
    execute_read_only,
    open_read_only,
    row_key,
    sql_candidate,
    unordered_key,
)


ARMS = ("no_skill", "formatting_placebo", "trace_mined_procedure")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def call_codex(prompt: str, model: str, workdir: Path, timeout: float) -> tuple[str, bool, float]:
    with tempfile.TemporaryDirectory(prefix="frankengate-bird-sql-") as temp:
        output = Path(temp) / "last_message.txt"
        command = [
            "codex", "exec", "--json", "--ephemeral", "--skip-git-repo-check",
            "--sandbox", "read-only", "--cd", str(workdir), "--model", model,
            "--output-last-message", str(output), "-",
        ]
        started = time.monotonic()
        try:
            process = subprocess.run(
                command, input=prompt, text=True, capture_output=True,
                timeout=timeout, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return "", False, (time.monotonic() - started) * 1000
        response = output.read_text(encoding="utf-8", errors="replace").strip() if output.exists() else ""
        if not response:
            for line in process.stdout.splitlines():
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "item.completed":
                    item = event.get("item", {}) or {}
                    if item.get("type") == "agent_message":
                        response = str(item.get("text", ""))
        return response, process.returncode == 0 and bool(response), (time.monotonic() - started) * 1000


def prompt_for(task: dict[str, Any], schema: str, arm: str, procedure: str) -> str:
    extra = ""
    if arm == "formatting_placebo":
        extra = "\nReturn only one SQL statement in a ```sql``` block."
    elif arm == "trace_mined_procedure":
        extra = "\nApply this frozen trace-mined procedure:\n" + procedure
    return (
        "You are a careful SQLite text-to-SQL solver. Do not use tools or the network. "
        "Return exactly one read-only SELECT or WITH statement and nothing else."
        + extra
        + "\n\nSchema:\n" + schema
        + "\nQuestion:\n" + str(task.get("prompt", ""))
    )


def choose_tasks(tasks: list[dict[str, Any]], heldout: list[str], per_family: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    for family in heldout:
        rows = sorted((row for row in tasks if row.get("data", {}).get("db_name") == family), key=lambda row: row["task_id"])
        selected.extend(rows[:per_family])
    if len(selected) != len(heldout) * per_family:
        raise ValueError("heldout family lacks enough tasks")
    return selected


def run(*, tasks_path: Path, schema_dir: Path, gold_dir: Path, database_dir: Path,
        procedure_path: Path, heldout: list[str], per_family: int, model: str,
        workdir: Path, timeout: float) -> dict[str, Any]:
    tasks = [json.loads(line) for line in tasks_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    selected = choose_tasks(tasks, heldout, per_family)
    procedure = procedure_path.read_text(encoding="utf-8")
    procedure_hash = sha256_text(procedure)
    connections: dict[str, Any] = {}
    rows: list[dict[str, Any]] = []
    aggregate: dict[str, Counter[str]] = {arm: Counter() for arm in ARMS}
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
            response, ok, elapsed_ms = call_codex(
                prompt_for(task, schema, arm, procedure), model, workdir, timeout
            )
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
            rows.append({
                "arm": arm,
                "family": family,
                "task_hash": sha256_text(task["task_id"]),
                "model": model,
                "response_sha256": sha256_text(response),
                "outcome": outcome,
                "exact": exact,
                "unordered": unordered,
                "elapsed_ms": round(elapsed_ms, 3),
            })
    for connection in connections.values():
        connection.close()
    return {
        "schema_version": "frankengate-bird-sql-skill-factorial-v1",
        "protocol": {
            "arms": list(ARMS),
            "heldout_families": heldout,
            "tasks_per_family": per_family,
            "task_count": len(selected),
            "model": model,
            "harness": "codex-cli-subscription",
            "procedure_sha256": procedure_hash,
            "gold_hidden_from_proposer": True,
        },
        "summary": {arm: dict(sorted(values.items())) for arm, values in aggregate.items()},
        "episodes": rows,
        "claim_boundary": {
            "independent_family_disjoint_run": True,
            "causal_skill_benefit_confirmed": False,
            "automatic_promotion_authorized": False,
            "reason": "Six-task pilot; a powered gate requires at least 20 held-out tasks across four families and paired confidence intervals.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--schema-dir", type=Path, required=True)
    parser.add_argument("--gold-dir", type=Path, required=True)
    parser.add_argument("--database-dir", type=Path, required=True)
    parser.add_argument("--procedure", type=Path, required=True)
    parser.add_argument("--heldout-family", action="append", required=True)
    parser.add_argument("--tasks-per-family", type=int, default=2)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--workdir", type=Path, default=Path("/tmp"))
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(
        tasks_path=args.tasks, schema_dir=args.schema_dir, gold_dir=args.gold_dir,
        database_dir=args.database_dir, procedure_path=args.procedure,
        heldout=args.heldout_family, per_family=args.tasks_per_family,
        model=args.model, workdir=args.workdir, timeout=args.timeout,
    )
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
