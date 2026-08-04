#!/usr/bin/env python3
"""Evaluate model-generated durable memory on held-out ALFWorld tasks."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from alfworld_skill_intervention import call_chat, choose_action  # noqa: E402


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def expert_trace(config: dict[str, Any], task: str) -> tuple[list[str], bool]:
    from alfworld.agents.environment.alfred_tw_env import AlfredTWEnv

    base = AlfredTWEnv(config, "eval_out_of_distribution")
    base.train_eval = "train"
    base.game_files = [task]
    base.num_games = 1
    env = base.init_env(1)
    try:
        _, infos = env.reset()
        actions: list[str] = []
        for _ in range(200):
            if infos.get("won", [False])[0]:
                return actions, True
            action = infos.get("extra.expert_plan", [["look"]])[0][0]
            actions.append(action)
            _, _, _, infos = env.step([action])
        return actions, bool(infos.get("won", [False])[0])
    finally:
        env.close()


def evaluate(base_env: Any, task: str, arm: str, memory: str, model: str, endpoint: str, max_steps: int, timeout: float) -> dict[str, Any]:
    base_env.game_files = [task]
    base_env.num_games = 1
    env = base_env.init_env(1)
    try:
        obs, infos = env.reset()
        done = [False]
        invalid = 0
        steps = 0
        while steps < max_steps and not done[0]:
            observation = obs[0][0]
            admissible = list(infos.get("admissible_commands", [[]])[0])
            system = "You are an ALFWorld agent. Return one action only."
            if arm == "generated_memory":
                system += "\nReleased memory from a prior successful episode:\n" + memory
            prompt = observation + "\nAdmissible actions:\n- " + "\n- ".join(admissible) + "\nChoose exactly one admissible action."
            try:
                response = call_chat(endpoint, model, system, prompt, timeout)
            except Exception:
                response = ""
            action, valid = choose_action(response, admissible)
            invalid += int(not valid)
            obs, _, done, infos = env.step([action])
            steps += 1
        return {
            "task_hash": sha256_text(task),
            "arm": arm,
            "model": model,
            "harness": "ollama-native-api" if endpoint.endswith("/api/chat") else "ollama-openai-compatible",
            "won": bool(infos.get("won", [False])[0]),
            "steps": steps,
            "invalid_action_count": invalid,
        }
    finally:
        env.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--alfworld-data", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--source-task", required=True)
    parser.add_argument("--task", action="append", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--extract-endpoint", required=True)
    parser.add_argument("--endpoint", action="append", required=True)
    parser.add_argument("--max-steps", type=int, default=35)
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--raw-output", type=Path, required=True)
    args = parser.parse_args()

    os.environ["ALFWORLD_DATA"] = str(args.alfworld_data.resolve(strict=True))
    import yaml
    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    config["dataset"]["num_eval_games"] = 1
    config["general"]["use_cuda"] = False

    source_actions, source_won = expert_trace(config, args.source_task)
    extraction_prompt = (
        "A successful ALFWorld episode produced this action trace:\n"
        + "\n".join(f"{index + 1}. {action}" for index, action in enumerate(source_actions))
        + "\n\nWrite a compact, task-general durable memory for future look-at-object-in-light tasks. "
        "Do not mention specific object names or locations. Preserve only reusable action discipline. "
        "Return memory text only; do not include analysis or XML."
    )
    generated_memory = call_chat(
        args.extract_endpoint,
        args.model,
        "You curate durable procedural memory from successful agent traces.",
        extraction_prompt,
        args.timeout,
    ).strip()
    if not generated_memory:
        raise RuntimeError("model generated empty durable memory")

    from alfworld.agents.environment.alfred_tw_env import AlfredTWEnv
    base = AlfredTWEnv(config, "eval_out_of_distribution")
    rows: list[dict[str, Any]] = []
    for endpoint in args.endpoint:
        for task in args.task:
            for arm in ("no_memory", "generated_memory"):
                rows.append(evaluate(base, task, arm, generated_memory, args.model, endpoint, args.max_steps, args.timeout))

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

    raw = {"generated_memory": generated_memory, "source_actions": source_actions, "source_won": source_won, "rows": rows, "summary": summary}
    args.raw_output.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result = {
        "schema_version": "frankengate-alfworld-model-generated-memory-intervention-v1",
        "study": "model-generated durable memory on held-out look-at-light tasks",
        "dataset": {"source": "zhangdw/alfworld", "split": "valid_unseen", "source_task_hash": sha256_text(args.source_task), "target_task_hashes": sorted(sha256_text(task) for task in args.task), "task_count": len(args.task)},
        "memory_release": {"memory_kind": "model-generated procedural summary", "memory_sha256": sha256_text(generated_memory), "future_outcomes_in_memory": False, "source_expert_won": source_won, "source_expert_steps": len(source_actions)},
        "protocol": {"arms": ["no_memory", "generated_memory"], "model": args.model, "harnesses": ["ollama-native-api", "ollama-openai-compatible"], "episodes": len(rows), "max_steps": args.max_steps, "expert_target_steps": [10, 29, 7], "expert_horizon_covers_all_tasks": args.max_steps >= 29, "raw_receipt": str(args.raw_output)},
        "summary": summary,
        "claim_boundary": {"model_generated_memory_intervention_executed": True, "quality_comparison_valid": args.max_steps >= 29, "causal_memory_benefit_confirmed": False, "automatic_memory_promotion_authorized": False, "reason": "The memory was generated from a separate successful expert trace and evaluated on disjoint tasks. The small cohort remains insufficient for general causal promotion."},
        "raw_model_content_committed": False,
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "summary": summary}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
