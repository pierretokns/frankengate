#!/usr/bin/env python3
"""Frontier pairwise interaction factorial for skill and retrieved memory."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from alfworld_codex_memory_intervention import codex_text, expert_trace, sha256_text


def choose_action(response: str, admissible: list[str]) -> tuple[str, bool]:
    tagged = re.findall(r"<action>\s*(.*?)\s*</action>", response, flags=re.I | re.S)
    candidates = tagged + ([response.strip().splitlines()[-1]] if response.strip() else [])
    for candidate in candidates:
        candidate = candidate.strip().strip("`* ").lower()
        for action in sorted(admissible, key=len, reverse=True):
            if candidate == action.lower() or action.lower() in candidate:
                return action, True
    lowered = response.lower()
    for action in sorted(admissible, key=len, reverse=True):
        if action.lower() in lowered:
            return action, True
    fallback = "look" if "look" in admissible else (admissible[0] if admissible else "look")
    return fallback, False


def run_episode(config: dict[str, Any], task: str, arm: str, skill: str,
                memory: str, model: str, max_steps: int, timeout: float,
                workdir: Path) -> dict[str, Any]:
    from alfworld.agents.environment.alfred_tw_env import AlfredTWEnv

    base = AlfredTWEnv(config, "eval_out_of_distribution")
    base.game_files = [task]
    base.num_games = 1
    env = base.init_env(batch_size=1)
    actions: list[str] = []
    invalid = 0
    calls = 0
    try:
        obs, infos = env.reset()
        done = [False]
        started = time.monotonic()
        while len(actions) < max_steps and not done[0]:
            observation = obs[0][0]
            admissible = list(infos.get("admissible_commands", [[]])[0])
            system = "You are an ALFWorld agent. Return exactly one action as <action>...</action>. Do not explain."
            if arm in ("skillopt", "skillopt_plus_retrieved_memory"):
                system += "\n\nSkill guidance:\n" + skill
            if arm in ("retrieved_memory", "skillopt_plus_retrieved_memory"):
                system += "\n\nRetrieved procedural memory:\n" + memory
            prompt = (observation + "\nAdmissible actions:\n- " +
                      "\n- ".join(admissible) +
                      "\nChoose exactly one admissible action.")
            response, ok = codex_text(system + "\n\n" + prompt,
                                      model, workdir, timeout)
            calls += int(ok)
            action, valid = choose_action(response, admissible)
            invalid += int(not valid)
            obs, _, done, infos = env.step([action])
            actions.append(action)
        return {
            "task_hash": sha256_text(task),
            "arm": arm,
            "model": model,
            "harness": "codex-cli-subscription",
            "won": bool(infos.get("won", [False])[0]),
            "steps": len(actions),
            "invalid_action_count": invalid,
            "api_calls": calls,
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
            "action_sequence": actions,
        }
    finally:
        env.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--alfworld-data", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
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
    skill = args.candidate.read_text(encoding="utf-8")
    releases: list[dict[str, Any]] = []
    memories: list[str] = []
    for source, target, family in zip(args.source_task, args.task, args.family):
        source_actions, source_won = expert_trace(config, source)
        if not source_won:
            raise RuntimeError(f"source expert failed for {family}")
        memory, memory_ok = codex_text(
            "You curate a concise reusable procedural memory from a successful "
            "retrieved ALFWorld trace. Do not mention object names, locations, "
            "target facts, or future outcomes; preserve only action discipline and "
            "the need to inspect admissible actions. Return plain text under 120 "
            "words.\n\nFamily: " + family + "\nTrace:\n" +
            "\n".join(f"{i + 1}. {a}" for i, a in enumerate(source_actions)),
            args.model, args.workdir, args.timeout,
        )
        if not memory_ok or not memory:
            raise RuntimeError(f"memory synthesis failed for {family}")
        memories.append(memory)
        releases.append({
            "family": family,
            "source_task_hash": sha256_text(source),
            "target_task_hash": sha256_text(target),
            "source_expert_steps": len(source_actions),
            "memory_sha256": sha256_text(memory),
            "memory_synthesis_succeeded": memory_ok,
        })

    arms = ["no_component", "skillopt", "retrieved_memory", "skillopt_plus_retrieved_memory"]
    rows: list[dict[str, Any]] = []
    for index, task in enumerate(args.task):
        for arm in arms:
            rows.append(run_episode(config, task, arm, skill, memories[index],
                                    args.model, args.max_steps, args.timeout,
                                    args.workdir))
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
        "schema_version": "frankengate-alfworld-codex-interaction-factorial-v1",
        "dataset": {
            "source": "zhangdw/alfworld",
            "source_split": "valid_seen",
            "target_split": "valid_unseen",
            "families": args.family,
            "source_task_hashes": [sha256_text(x) for x in args.source_task],
            "target_task_hashes": [sha256_text(x) for x in args.task],
        },
        "candidates": {
            "skillopt_sha256": sha256_text(skill),
            "retrieved_memory_releases": releases,
        },
        "protocol": {
            "arms": arms,
            "model": args.model,
            "harness": "codex-cli-subscription",
            "max_steps": args.max_steps,
            "source_target_disjoint": True,
            "expert_and_future_outcomes_hidden_from_heldout_agent": True,
            "independent_replay_required": True,
            "raw_model_text_committed": False,
        },
        "summary": summary,
        "episodes": rows,
        "claim_boundary": {
            "interaction_factorial_executed": True,
            "causal_interaction_benefit_confirmed": False,
            "automatic_promotion_authorized": False,
            "reason": "Small four-family frontier interaction factorial; no integrated Frankengate implementation is implied.",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "summary": summary}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
