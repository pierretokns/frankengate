#!/usr/bin/env python3
"""Run a larger family-disjoint ALFWorld trace-skill comparison.

This runner deliberately keeps model text outside the research worktree.  It
selects deterministic held-out task paths, verifies each path has an expert
solution within the configured horizon, then reuses the audited intervention
runner for paired no-skill/candidate episodes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from alfworld_skill_intervention import run_episode  # noqa: E402


FAMILIES = (
    "look_at_obj_in_light",
    "pick_and_place_simple",
    "pick_clean_then_place_in_recep",
    "pick_heat_then_place_in_recep",
)
# Formatting placebo is a required control for separating a useful procedure
# from merely changing the output contract. Existing receipts remain
# two-arm-compatible; new runs may opt into this third arm.
ARMS = ("no_skill", "formatting_placebo", "trace_mined_procedure_v2")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def expert_steps(config: dict[str, Any], task: str) -> tuple[int, bool]:
    """Return the environment-provided expert-plan length and success."""
    from alfworld.agents.environment.alfred_tw_env import AlfredTWEnv

    base = AlfredTWEnv(config, "eval_out_of_distribution")
    base.train_eval = "train"
    base.game_files = [task]
    base.num_games = 1
    env = base.init_env(1)
    try:
        _, infos = env.reset()
        actions = 0
        for _ in range(300):
            if infos.get("won", [False])[0]:
                return actions, True
            action = infos.get("extra.expert_plan", [["look"]])[0][0]
            actions += 1
            _, _, _, infos = env.step([action])
        return actions, bool(infos.get("won", [False])[0])
    finally:
        env.close()


def select_tasks(
    root: Path,
    config: dict[str, Any],
    per_family: int,
    max_steps: int,
    excluded_hashes: set[str],
) -> tuple[list[str], list[dict[str, Any]]]:
    selected: list[str] = []
    controls: list[dict[str, Any]] = []
    for family in FAMILIES:
        candidates = sorted(root.glob(f"{family}-*/**/game.tw-pddl"))
        family_count = 0
        for task_path in candidates:
            task = str(task_path)
            task_hash = sha256_text(task)
            if task_hash in excluded_hashes:
                continue
            steps, won = expert_steps(config, task)
            if not won or steps > max_steps:
                continue
            selected.append(task)
            controls.append(
                {
                    "family": family,
                    "task_hash": task_hash,
                    "expert_steps": steps,
                    "expert_won": won,
                }
            )
            family_count += 1
            if family_count >= per_family:
                break
        if family_count < per_family:
            raise RuntimeError(
                f"only selected {family_count}/{per_family} eligible tasks for {family}"
            )
    return selected, controls


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--alfworld-data", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--model", action="append", required=True)
    parser.add_argument("--endpoint", action="append", required=True)
    parser.add_argument("--tasks-per-family", type=int, default=2)
    parser.add_argument("--task", action="append", default=[], help="Explicit task path(s); bypass deterministic selection")
    parser.add_argument("--exclude-hash", action="append", default=[])
    parser.add_argument("--arm", action="append", choices=ARMS, default=None)
    parser.add_argument("--max-steps", type=int, default=35)
    parser.add_argument("--timeout", type=float, default=60)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--raw-output", type=Path, required=True)
    parser.add_argument("--record-actions", action="store_true", help="Retain executed environment actions for independent replay")
    args = parser.parse_args()
    arms = args.arm or list(ARMS)

    os.environ["ALFWORLD_DATA"] = str(args.alfworld_data.resolve(strict=True))
    import yaml
    from alfworld.agents.environment.alfred_tw_env import AlfredTWEnv

    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    config["dataset"]["num_eval_games"] = 1
    config["general"]["use_cuda"] = False
    root = args.alfworld_data / "json_2.1.1" / "valid_unseen"
    if args.task:
        tasks = [str(Path(task).resolve(strict=True)) for task in args.task]
        controls = []
        for task in tasks:
            steps, won = expert_steps(config, task)
            if not won or steps > args.max_steps:
                raise RuntimeError(f"explicit task is not expert-solvable within horizon: {task}")
            family = next((name for name in FAMILIES if f"/{name}-" in task), "unknown")
            controls.append({"family": family, "task_hash": sha256_text(task), "expert_steps": steps, "expert_won": won})
    else:
        tasks, controls = select_tasks(
            root,
            config,
            args.tasks_per_family,
            args.max_steps,
            set(args.exclude_hash),
        )
    base = AlfredTWEnv(config, "eval_out_of_distribution")
    rows: list[dict[str, Any]] = []
    for model in args.model:
        for endpoint in args.endpoint:
            for task in tasks:
                for arm in arms:
                    rows.append(
                        run_episode(
                            base,
                            task,
                            arm,
                            model,
                            endpoint,
                            args.max_steps,
                            args.timeout,
                            args.record_actions,
                        )
                    )

    summary: dict[str, Any] = {}
    for row in rows:
        key = f"{row['model']}|{row['harness']}|{row['arm']}"
        bucket = summary.setdefault(
            key,
            {"episodes": 0, "wins": 0, "invalid_actions": 0, "steps": 0, "elapsed_ms": 0.0},
        )
        bucket["episodes"] += 1
        bucket["wins"] += int(row["won"])
        bucket["invalid_actions"] += row["invalid_action_count"]
        bucket["steps"] += row["steps"]
        bucket["elapsed_ms"] += row.get("elapsed_ms", 0.0)
    for bucket in summary.values():
        bucket["win_rate"] = bucket["wins"] / bucket["episodes"]
        bucket["mean_steps"] = bucket["steps"] / bucket["episodes"]
        bucket["mean_elapsed_ms"] = bucket["elapsed_ms"] / bucket["episodes"]

    # The raw receipt contains only aggregate episode rows, never model text.
    args.raw_output.parent.mkdir(parents=True, exist_ok=True)
    args.raw_output.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result = {
        "schema_version": "frankengate-alfworld-family-disjoint-powered-v1",
        "study": "larger family-disjoint trace-derived skill comparison",
        "dataset": {
            "source": "zhangdw/alfworld",
            "split": "valid_unseen",
            "families": list(FAMILIES),
            "task_count": len(tasks),
            "task_hashes": [sha256_text(task) for task in tasks],
            "excluded_hashes": sorted(set(args.exclude_hash)),
        },
        "protocol": {
            "arms": arms,
            "models": args.model,
            "endpoints": args.endpoint,
            "harnesses": sorted({
                "ollama-native-api" if endpoint.endswith("/api/chat") else "ollama-openai-compatible"
                for endpoint in args.endpoint
            }),
            "tasks_per_family": args.tasks_per_family,
            "max_steps": args.max_steps,
            "expert_horizon_covers_all_tasks": all(item["expert_steps"] <= args.max_steps for item in controls),
            "controls": controls,
            "raw_receipt": str(args.raw_output),
            "action_sequences_recorded": args.record_actions,
        },
        "summary": summary,
        "comparison": {
            "semantic_success_delta_by_model_harness": {},
            "causal_skill_benefit_confirmed": False,
            "automatic_promotion_authorized": False,
        },
        "claim_boundary": {
            "family_disjoint_semantic_intervention_executed": True,
            "independent_outcome_verifier": "environment won flag plus expert horizon preflight; independent verifier still required",
            "reason": "This receipt expands the held-out task count but remains a bounded local study; promotion requires sealed outcome recomputation and a preregistered powered threshold.",
        },
    }
    for key, bucket in summary.items():
        parts = key.split("|")
        model_harness = "|".join(parts[:2])
        if parts[-1] == "no_skill":
            result["comparison"]["semantic_success_delta_by_model_harness"].setdefault(model_harness, {})[
                "no_skill_win_rate"
            ] = bucket["win_rate"]
        elif parts[-1] == "trace_mined_procedure_v2":
            result["comparison"]["semantic_success_delta_by_model_harness"].setdefault(model_harness, {})[
                "trace_mined_win_rate"
            ] = bucket["win_rate"]
        elif parts[-1] == "formatting_placebo":
            result["comparison"]["semantic_success_delta_by_model_harness"].setdefault(model_harness, {})[
                "formatting_placebo_win_rate"
            ] = bucket["win_rate"]
    for values in result["comparison"]["semantic_success_delta_by_model_harness"].values():
        if {"no_skill_win_rate", "trace_mined_win_rate"} <= values.keys():
            values["win_rate_delta"] = values["trace_mined_win_rate"] - values["no_skill_win_rate"]

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "task_count": len(tasks), "summary": summary}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
