#!/usr/bin/env python3
"""Evaluate a SkillOpt candidate with the Codex subscription harness.

Only aggregate episode rows and action sequences are written. Model prompts
and responses remain outside the research checkout. This is a small, explicit
Codex arm for comparison with the existing Ollama-native/OpenAI-compatible
controls; it is not a replacement for the larger powered matrix.
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


def codex_action(prompt: str, model: str, workdir: Path, timeout: float) -> tuple[str, bool]:
    with tempfile.TemporaryDirectory(prefix="frankengate-codex-action-") as tmp:
        output = Path(tmp) / "last_message.txt"
        command = [
            "codex", "exec", "--json", "--ephemeral", "--skip-git-repo-check",
            "--sandbox", "read-only", "--cd", str(workdir), "--model", model,
            "--output-last-message", str(output), "-",
        ]
        try:
            proc = subprocess.run(
                command, input=prompt, text=True, capture_output=True,
                timeout=timeout, check=False,
            )
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
                        response = str(item.get("text", ""))
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


def run_episode(config: dict[str, Any], task_path: str, arm: str, candidate: str, model: str,
                max_steps: int, timeout: float, workdir: Path) -> dict[str, Any]:
    from alfworld.agents.environment.alfred_tw_env import AlfredTWEnv

    base_env = AlfredTWEnv(config, "eval_out_of_distribution")
    base_env.game_files = [task_path]
    base_env.num_games = 1
    env = base_env.init_env(batch_size=1)
    try:
        obs, infos = env.reset()
        done = [False]
        actions: list[str] = []
        invalid = 0
        calls = 0
        started = time.monotonic()
        while len(actions) < max_steps and not done[0]:
            observation = obs[0][0]
            admissible = list(infos.get("admissible_commands", [[]])[0])
            system = (
                "You are an ALFWorld agent. Return exactly one action as "
                "<action>...</action>. Do not explain or use tools."
            )
            if arm == "formatting_placebo":
                system += " Follow the output tag contract exactly."
            elif arm == "skillopt_candidate":
                system += "\n\nSkillOpt candidate guidance:\n" + candidate
            prompt = (
                observation + "\nAdmissible actions:\n- " + "\n- ".join(admissible)
                + "\nChoose exactly one admissible action."
            )
            response, ok = codex_action(
                system + "\n\n" + prompt, model, workdir, timeout,
            )
            calls += int(ok)
            action, valid = choose_action(response, admissible)
            invalid += int(not valid)
            obs, _, done, infos = env.step([action])
            actions.append(action)
        return {
            "task_hash": sha256_text(task_path),
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
    parser.add_argument(
        "--candidate-source",
        default="Microsoft SkillOpt published ALFWorld checkpoint",
        help="Content-free provenance label for the candidate artifact.",
    )
    parser.add_argument("--task", action="append", required=True)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--max-steps", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=90)
    parser.add_argument("--workdir", type=Path, default=Path("/private/tmp"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    os.environ["ALFWORLD_DATA"] = str(args.alfworld_data.resolve(strict=True))
    import yaml
    from alfworld.agents.environment.alfred_tw_env import AlfredTWEnv

    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    config["dataset"]["num_eval_games"] = 1
    config["general"]["use_cuda"] = False
    candidate = args.candidate.read_text(encoding="utf-8")
    arms = ["no_skill", "formatting_placebo", "skillopt_candidate"]
    # ALFWorld's Fast Downward translator is process-global and not thread-safe
    # during environment construction. Keep episodes sequential so the
    # independent state machine remains reproducible; Codex calls are still
    # isolated subprocesses.
    rows = [
        run_episode(config, task, arm, candidate, args.model,
                    args.max_steps, args.timeout, args.workdir)
        for task in args.task
        for arm in arms
    ]
    summary: dict[str, Any] = {}
    for row in rows:
        bucket = summary.setdefault(row["arm"], {"episodes": 0, "wins": 0, "invalid_actions": 0, "steps": 0, "api_calls": 0})
        bucket["episodes"] += 1
        bucket["wins"] += int(row["won"])
        bucket["invalid_actions"] += row["invalid_action_count"]
        bucket["steps"] += row["steps"]
        bucket["api_calls"] += row["api_calls"]
    for bucket in summary.values():
        bucket["win_rate"] = bucket["wins"] / bucket["episodes"]
    family_labels = {
        r["task_hash"]: Path(task).parent.parent.name.split("-", 1)[0]
        for r, task in zip(rows, [task for task in args.task for _ in arms])
    }
    result = {
        "schema_version": "frankengate-alfworld-codex-skillopt-v1",
        "dataset": {
            "source": "zhangdw/alfworld",
            "split": "valid_unseen",
            "task_hashes": sorted({r["task_hash"] for r in rows}),
            "family_labels": family_labels,
        },
        "model": args.model,
        "harness": "codex-cli-subscription",
        "candidate_sha256": sha256_text(candidate),
        "candidate_source": args.candidate_source,
        "arms": arms,
        "summary": summary,
        "episodes": rows,
        "claim_boundary": {
            "real_model_intervention_executed": True,
            "causal_skill_benefit_confirmed": False,
            "automatic_promotion_authorized": False,
            "reason": "Small bounded Codex replication; candidate and controls are compared, but this is not the preregistered powered release gate.",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "summary": summary}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
