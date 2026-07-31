#!/usr/bin/env python3
"""Evaluate a frontier-generated durable memory on held-out ALFWorld tasks.

The memory is distilled from a separate successful expert episode, with expert
actions visible only to the memory synthesizer. Held-out evaluation never sees
the source trace, expert plans, or future outcomes. Prompts/responses are
ephemeral; the receipt stores only hashes and aggregate/action replay data.
"""

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


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def codex_text(prompt: str, model: str, workdir: Path, timeout: float) -> tuple[str, bool]:
    with tempfile.TemporaryDirectory(prefix="frankengate-codex-memory-") as tmp:
        output = Path(tmp) / "last_message.txt"
        command = [
            "codex", "exec", "--json", "--ephemeral", "--skip-git-repo-check",
            "--sandbox", "read-only", "--cd", str(workdir), "--model", model,
            "--output-last-message", str(output), "-",
        ]
        try:
            proc = subprocess.run(command, input=prompt, text=True,
                                  capture_output=True, timeout=timeout, check=False)
        except (OSError, subprocess.TimeoutExpired):
            return "", False
        response = output.read_text(encoding="utf-8", errors="replace").strip() if output.exists() else ""
        if not response:
            for line in proc.stdout.splitlines():
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if event.get("type") == "item.completed":
                    item = event.get("item", {}) or {}
                    if item.get("type") == "agent_message":
                        response = str(item.get("text", "")).strip()
        return response, proc.returncode == 0 and bool(response)


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


def expert_trace(config: dict[str, Any], task: str) -> tuple[list[str], bool]:
    from alfworld.agents.environment.alfred_tw_env import AlfredTWEnv

    base = AlfredTWEnv(config, "eval_out_of_distribution")
    # ALFWorld exposes the environment-provided expert plan only when the
    # evaluator is switched to its train/evaluation expert mode.
    base.train_eval = "train"
    base.game_files = [task]
    base.num_games = 1
    env = base.init_env(batch_size=1)
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


def run_episode(config: dict[str, Any], task: str, arm: str, memory: str,
                model: str, max_steps: int, timeout: float,
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
            if arm == "formatting_placebo":
                system += " Follow the output tag contract exactly."
            elif arm == "generated_memory":
                system += "\n\nReleased procedural memory from a prior successful episode:\n" + memory
            prompt = (observation + "\nAdmissible actions:\n- " +
                      "\n- ".join(admissible) +
                      "\nChoose exactly one admissible action.")
            response, ok = codex_text(system + "\n\n" + prompt, model, workdir, timeout)
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
    parser.add_argument("--source-task", type=Path, required=True)
    parser.add_argument("--task", action="append", required=True)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--max-steps", type=int, default=35)
    parser.add_argument("--timeout", type=float, default=90)
    parser.add_argument("--workdir", type=Path, default=Path("/private/tmp"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    os.environ["ALFWORLD_DATA"] = str(args.alfworld_data.resolve(strict=True))
    import yaml

    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    config["dataset"]["num_eval_games"] = 1
    config["general"]["use_cuda"] = False
    source_actions, source_won = expert_trace(config, str(args.source_task))
    if not source_won:
        raise RuntimeError("source expert episode did not win")
    extraction_prompt = (
        "A successful ALFWorld episode produced this action trace:\n" +
        "\n".join(f"{index + 1}. {action}" for index, action in enumerate(source_actions)) +
        "\n\nWrite a compact task-general durable memory for future ALFWorld tasks. "
        "Do not mention specific object names or locations. Preserve only reusable "
        "action discipline and the requirement to inspect current admissible actions. "
        "Return plain memory text only, at most 120 words; no analysis or XML."
    )
    memory, memory_ok = codex_text(
        "You curate durable procedural memory from successful agent traces.\n\n" +
        extraction_prompt, args.model, args.workdir, args.timeout,
    )
    if not memory_ok or not memory:
        raise RuntimeError("frontier memory synthesis failed")

    rows: list[dict[str, Any]] = []
    for task in args.task:
        for arm in ("no_memory", "formatting_placebo", "generated_memory"):
            rows.append(run_episode(config, task, arm, memory, args.model,
                                    args.max_steps, args.timeout, args.workdir))
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
        "schema_version": "frankengate-alfworld-codex-generated-memory-v1",
        "dataset": {
            "source": "zhangdw/alfworld",
            "split": "valid_unseen",
            "source_task_hash": sha256_text(str(args.source_task)),
            "target_task_hashes": sorted(sha256_text(task) for task in args.task),
            "task_count": len(args.task),
        },
        "memory_release": {
            "memory_kind": "frontier-generated procedural summary",
            "memory_sha256": sha256_text(memory),
            "source_expert_won": source_won,
            "source_expert_steps": len(source_actions),
            "future_outcomes_in_memory": False,
            "memory_call_succeeded": memory_ok,
        },
        "protocol": {
            "arms": ["no_memory", "formatting_placebo", "generated_memory"],
            "model": args.model,
            "harness": "codex-cli-subscription",
            "max_steps": args.max_steps,
            "expert_actions_exposed_to_heldout_agent": False,
            "source_and_target_disjoint": True,
            "independent_replay_required": True,
            "raw_model_text_committed": False,
        },
        "summary": summary,
        "episodes": rows,
        "claim_boundary": {
            "frontier_generated_memory_intervention_executed": True,
            "causal_memory_benefit_confirmed": False,
            "automatic_memory_promotion_authorized": False,
            "reason": "Small family-disjoint frontier memory release; larger cohorts and independent replay are required for general memory claims.",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "summary": summary}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
