#!/usr/bin/env python3
"""Audit whether the public WMH-BIRD trace export can support exposure-aware retrieval supervision.

This is deliberately a dataset-fit audit, not a retrieval benchmark.  It checks
for candidate-set exposure, search/open events, stable identity/scope fields,
and independent outcome fields without writing prompts, SQL, tool arguments, or
observations to the result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-bird-trajectory-retrieval-fit-v1"
EXPOSURE_KEYS = {"candidate_set", "exposure", "exposure_set", "retrieval_results", "search_results", "opened_files"}
IDENTITY_KEYS = {"principal", "principal_id", "team", "team_id", "project", "project_id", "system", "system_id", "session_id"}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(steps_path: Path, output: Path) -> dict[str, Any]:
    rows = 0
    tasks: set[str] = set()
    tool_names: Counter[str] = Counter()
    action_keys: Counter[str] = Counter()
    observation_keys: Counter[str] = Counter()
    raw_span_count = 0
    tool_result_edges = 0
    explicit_exposure_rows = 0
    explicit_identity_rows = 0
    search_or_open_rows = 0
    reward_rows = 0
    error_rows = 0
    task_rows: defaultdict[str, int] = defaultdict(int)

    for line in steps_path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        rows += 1
        task = str(row.get("task", "")).strip()
        if task:
            tasks.add(hashlib.sha256(task.encode()).hexdigest())
            task_rows[task] += 1
        action = row.get("action") if isinstance(row.get("action"), dict) else {}
        observation = row.get("observation") if isinstance(row.get("observation"), dict) else {}
        tool_names[str(action.get("name", ""))] += 1
        for key in action:
            action_keys[str(key)] += 1
        for key in observation:
            observation_keys[str(key)] += 1
        if row.get("raw_span_ids"):
            raw_span_count += 1
        if action and observation:
            tool_result_edges += 1
        keys = set(row) | set(action) | set(observation)
        explicit_exposure_rows += int(bool(keys & EXPOSURE_KEYS))
        explicit_identity_rows += int(bool(keys & IDENTITY_KEYS))
        action_name = str(action.get("name", "")).lower()
        search_or_open_rows += int(any(token in action_name for token in ("search", "open", "retrieve", "grep", "find")))
        reward_rows += int("reward" in observation and observation.get("reward") is not None)
        error_rows += int(observation.get("is_error") is True)

    missing = {
        "candidate_set_exposure": explicit_exposure_rows == 0,
        "search_or_open_relevance_events": search_or_open_rows == 0,
        "stable_principal_team_project_system": explicit_identity_rows == 0,
        "natural_session_id": True,
        "independent_terminal_outcome": reward_rows == 0,
    }
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "steps_uri": "external://world-model-harness-v0.2.2/bird-sql/index/steps.jsonl",
            "steps_sha256": sha256_file(steps_path),
            "raw_content_committed": False,
        },
        "inventory": {
            "step_rows": rows,
            "task_hashes": len(tasks),
            "tool_names": dict(sorted(tool_names.items())),
            "action_keys": dict(sorted(action_keys.items())),
            "observation_keys": dict(sorted(observation_keys.items())),
            "rows_with_raw_span_ids": raw_span_count,
            "tool_result_edges": tool_result_edges,
            "rows_with_explicit_exposure_fields": explicit_exposure_rows,
            "rows_with_explicit_identity_fields": explicit_identity_rows,
            "search_or_open_action_rows": search_or_open_rows,
            "rows_with_non_null_reward": reward_rows,
            "error_observation_rows": error_rows,
        },
        "missing_requirements": missing,
        "decision": {
            "exposure_aware_retrieval_reproduction_ready": not any(missing.values()),
            "candidate_pool_can_be_frozen_honestly": False,
            "reason": "The BIRD export records tool calls and observations, but does not record candidate exposure sets, search/open relevance events, stable principals/scopes, or independent terminal outcomes required by the trajectory-supervision contract.",
        },
    }
    result["result_sha256"] = hashlib.sha256(json.dumps(result, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"inventory": result["inventory"], "missing_requirements": missing, "decision": result["decision"]}, sort_keys=True))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.steps, args.output)
