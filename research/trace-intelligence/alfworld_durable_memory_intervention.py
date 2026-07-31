#!/usr/bin/env python3
"""Test a released cross-episode memory on held-out ALFWorld tasks.

The memory is derived from a separate successful task family member and is
injected with a provenance hash.  Only aggregate outcomes are written to the
requested output; model content remains in the external raw receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from alfworld_skill_intervention import call_chat, choose_action  # noqa: E402


MEMORY_TEXT = (
    "Released memory from a prior successful look-at-object-in-light episode: "
    "when the goal requires an object to be viewed in a light, first navigate "
    "using only admissible actions, then activate the required lamp before the "
    "final look/inspection action. Re-read the observation after every action."
)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def run_episode(base_env: Any, task_path: str, arm: str, model: str, endpoint: str, max_steps: int, timeout: float) -> dict[str, Any]:
    base_env.game_files = [task_path]
    base_env.num_games = 1
    env = base_env.init_env(batch_size=1)
    try:
        obs, infos = env.reset()
        done = [False]
        steps = 0
        invalid = 0
        api_calls = 0
        while steps < max_steps and not done[0]:
            observation = obs[0][0]
            admissible = list(infos.get("admissible_commands", [[]])[0])
            system = "You are an ALFWorld agent. Return one action only."
            if arm == "released_memory":
                system += "\n" + MEMORY_TEXT
            prompt = (
                observation
                + "\nAdmissible actions:\n- "
                + "\n- ".join(admissible)
                + "\nChoose exactly one admissible action."
            )
            try:
                response = call_chat(endpoint, model, system, prompt, timeout)
                api_calls += 1
            except Exception:
                response = ""
            action, valid = choose_action(response, admissible)
            if not valid:
                invalid += 1
            obs, _, done, infos = env.step([action])
            steps += 1
        return {
            "task_hash": sha256_text(task_path),
            "arm": arm,
            "model": model,
            "harness": "ollama-native-api" if endpoint.endswith("/api/chat") else "ollama-openai-compatible",
            "won": bool(infos.get("won", [False])[0]),
            "steps": steps,
            "invalid_action_count": invalid,
            "api_calls": api_calls,
        }
    finally:
        env.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--alfworld-data", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--source-task", required=True)
    parser.add_argument("--task", action="append", required=True)
    parser.add_argument("--model", action="append", required=True)
    parser.add_argument("--endpoint", action="append", required=True)
    parser.add_argument("--max-steps", type=int, default=20)
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    import os
    os.environ["ALFWORLD_DATA"] = str(args.alfworld_data.resolve(strict=True))
    import yaml
    from alfworld.agents.environment.alfred_tw_env import AlfredTWEnv

    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    config["dataset"]["num_eval_games"] = 1
    config["general"]["use_cuda"] = False
    base = AlfredTWEnv(config, "eval_out_of_distribution")
    arms = ["no_memory", "released_memory"]
    rows: list[dict[str, Any]] = []
    for model in args.model:
        for endpoint in args.endpoint:
            for task in args.task:
                for arm in arms:
                    rows.append(run_episode(base, task, arm, model, endpoint, args.max_steps, args.timeout))
    summary: dict[str, Any] = {}
    for row in rows:
        key = f"{row['model']}|{row['harness']}|{row['arm']}"
        bucket = summary.setdefault(key, {"episodes": 0, "wins": 0, "invalid_actions": 0, "steps": 0})
        bucket["episodes"] += 1
        bucket["wins"] += int(row["won"])
        bucket["invalid_actions"] += row["invalid_action_count"]
        bucket["steps"] += row["steps"]
    for bucket in summary.values():
        bucket["win_rate"] = bucket["wins"] / bucket["episodes"]
        bucket["mean_steps"] = bucket["steps"] / bucket["episodes"]
    result = {
        "schema_version": "frankengate-alfworld-durable-memory-intervention-v1",
        "study": "cross-episode released memory on held-out look-at-object-in-light tasks",
        "dataset": {"source": "zhangdw/alfworld", "split": "valid_unseen", "task_count": len(args.task), "task_hashes": sorted(sha256_text(t) for t in args.task)},
        "memory_release": {"source_task_hash": sha256_text(args.source_task), "memory_sha256": sha256_text(MEMORY_TEXT), "memory_kind": "provenance-bound procedural summary", "future_outcomes_in_memory": False},
        "protocol": {"arms": arms, "models": args.model, "harnesses": ["ollama-native-api", "ollama-openai-compatible"], "max_steps": args.max_steps, "episodes": len(rows), "raw_receipt": str(args.output.with_suffix('.raw.json'))},
        "summary": summary,
        "claim_boundary": {"durable_memory_intervention_executed": True, "causal_memory_benefit_confirmed": False, "automatic_memory_promotion_authorized": False, "reason": "Small held-out family slice; release provenance is fixed and future outcomes are excluded, but promotion requires larger family-disjoint cohorts and independent labels."},
        "raw_model_content_committed": False,
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "summary": summary}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
