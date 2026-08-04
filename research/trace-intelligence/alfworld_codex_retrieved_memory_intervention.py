#!/usr/bin/env python3
"""Evaluate retrieval-conditioned frontier memory on held-out ALFWorld tasks.

Each held-out task is paired with one family-matched successful source episode
from a disjoint valid-seen split. The source trace is retrieved by a frozen
family-key policy, distilled by the frontier model, and released only to the
corresponding held-out agent. No target task path, expert plan, or future
outcome is shown to the synthesizer or held-out agent. Controls are no-memory
and formatting-placebo; action receipts are independently replayable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from alfworld_codex_memory_intervention import (
    codex_text,
    expert_trace,
    run_episode,
    sha256_text,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--alfworld-data", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--source-task", action="append", required=True)
    parser.add_argument("--task", action="append", required=True)
    parser.add_argument("--family", action="append", required=True)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--max-steps", type=int, default=35)
    parser.add_argument("--timeout", type=float, default=90)
    parser.add_argument("--workdir", type=Path, default=Path("/private/tmp"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not (len(args.source_task) == len(args.task) == len(args.family)):
        parser.error("source-task, task, and family counts must match")

    os.environ["ALFWORLD_DATA"] = str(args.alfworld_data.resolve(strict=True))
    import yaml

    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    config["dataset"]["num_eval_games"] = 1
    config["general"]["use_cuda"] = False
    rows: list[dict[str, Any]] = []
    releases: list[dict[str, Any]] = []
    for source, target, family in zip(args.source_task, args.task, args.family):
        source_actions, source_won = expert_trace(config, source)
        if not source_won:
            raise RuntimeError(f"retrieved source expert failed for family {family}")
        prompt = (
            "You curate a task-general procedural memory from one successful "
            "retrieved ALFWorld episode. The memory will be used on a different "
            "held-out task from the same task family. Preserve only reusable "
            "action discipline and the requirement to inspect current admissible "
            "actions. Do not mention source object names, locations, target facts, "
            "expert-only actions, or future outcomes. Return plain memory text only, "
            "at most 120 words; no analysis or XML.\n\nRetrieved source family: "
            + family + "\nRetrieved source action trace:\n"
            + "\n".join(f"{i + 1}. {action}" for i, action in enumerate(source_actions))
        )
        memory, memory_ok = codex_text(
            "You curate governed retrieval-conditioned procedural memory.\n\n" +
            prompt, args.model, args.workdir, args.timeout,
        )
        if not memory_ok or not memory:
            raise RuntimeError(f"memory synthesis failed for family {family}")
        for arm in ("no_memory", "formatting_placebo", "generated_memory"):
            row = run_episode(config, target, arm, memory, args.model,
                              args.max_steps, args.timeout, args.workdir)
            row["retrieved_family"] = family
            row["source_task_hash"] = sha256_text(source)
            if arm == "generated_memory":
                row["memory_sha256"] = sha256_text(memory)
            rows.append(row)
        releases.append({
            "family": family,
            "source_task_hash": sha256_text(source),
            "target_task_hash": sha256_text(target),
            "source_expert_steps": len(source_actions),
            "source_expert_won": source_won,
            "memory_sha256": sha256_text(memory),
            "memory_synthesis_succeeded": memory_ok,
        })

    summary: dict[str, Any] = {}
    for row in rows:
        bucket = summary.setdefault(row["arm"], {
            "episodes": 0, "wins": 0, "invalid_actions": 0,
            "steps": 0, "api_calls": 0,
        })
        bucket["episodes"] += 1
        bucket["wins"] += int(row["won"])
        bucket["invalid_actions"] += row["invalid_action_count"]
        bucket["steps"] += row["steps"]
        bucket["api_calls"] += row["api_calls"]
    for bucket in summary.values():
        bucket["win_rate"] = bucket["wins"] / bucket["episodes"]
    result = {
        "schema_version": "frankengate-alfworld-codex-retrieved-memory-v1",
        "dataset": {
            "source": "zhangdw/alfworld",
            "source_split": "valid_seen",
            "target_split": "valid_unseen",
            "families": args.family,
            "source_task_hashes": [sha256_text(x) for x in args.source_task],
            "target_task_hashes": [sha256_text(x) for x in args.task],
            "task_count": len(args.task),
        },
        "retrieval_policy": {
            "kind": "frozen family-key source selection",
            "source_and_target_disjoint": True,
            "target_details_exposed_to_synthesizer": False,
            "future_outcomes_exposed": False,
        },
        "protocol": {
            "arms": ["no_memory", "formatting_placebo", "generated_memory"],
            "model": args.model,
            "harness": "codex-cli-subscription",
            "max_steps": args.max_steps,
            "independent_replay_required": True,
            "raw_model_text_committed": False,
        },
        "releases": releases,
        "summary": summary,
        "episodes": rows,
        "claim_boundary": {
            "retrieval_conditioned_memory_intervention_executed": True,
            "causal_retrieval_memory_benefit_confirmed": False,
            "automatic_promotion_authorized": False,
            "reason": "Small four-family retrieval-conditioned memory comparison; promotion requires larger source pools and held-out cohorts.",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "summary": summary}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
