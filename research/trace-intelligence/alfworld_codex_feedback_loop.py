#!/usr/bin/env python3
"""Measure frontier self-feedback on reset ALFWorld tasks.

The first attempt is run without a skill.  The self-feedback arm gives a
frontier model only a bounded, content-minimized record of that attempt and
asks it to write guidance for a reset second attempt.  It never exposes expert
actions, expert step counts, or future outcomes.  Controls repeat the task
without feedback or with a formatting-only placebo.  Prompts and responses are
not written; only aggregate outcomes, action sequences, and candidate hashes
are retained for independent replay.
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
    with tempfile.TemporaryDirectory(prefix="frankengate-codex-feedback-") as tmp:
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


def run_attempt(config: dict[str, Any], task: str, model: str, system: str,
                max_steps: int, timeout: float, workdir: Path) -> dict[str, Any]:
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
            "won": bool(infos.get("won", [False])[0]),
            "steps": len(actions),
            "invalid_action_count": invalid,
            "api_calls": calls,
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
            "action_sequence": actions,
        }
    finally:
        env.close()


def feedback_candidate(first: dict[str, Any], task: str, model: str,
                       workdir: Path, timeout: float) -> tuple[str, bool]:
    # The trajectory is intentionally bounded to action names and aggregate
    # outcome.  The model does not receive the task path, gold plan, or future
    # state.  This is a feedback-loop intervention, not expert trace mining.
    compact = {
        "attempt_won": first["won"],
        "steps": first["steps"],
        "invalid_action_count": first["invalid_action_count"],
        "actions": first["action_sequence"],
    }
    prompt = (
        "You are evaluating an embodied agent feedback loop. Based only on the "
        "bounded prior attempt below, write concise procedural guidance for a "
        "second attempt at the same task. Do not invent hidden state, expert "
        "actions, or task facts. Preserve the rule that the agent must inspect "
        "the current observation and choose one currently admissible action. "
        "Return plain guidance text only, at most 120 words.\n\n"
        + json.dumps(compact, sort_keys=True)
    )
    return codex_text(prompt, model, workdir, timeout)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--alfworld-data", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
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
    base_system = (
        "You are an ALFWorld agent. Return exactly one action as "
        "<action>...</action>. Do not explain or use tools."
    )
    placebo_system = base_system + " Follow the output tag contract exactly."
    rows: list[dict[str, Any]] = []
    feedback_receipts: list[dict[str, Any]] = []
    for task in args.task:
        first = run_attempt(config, task, args.model, base_system,
                           args.max_steps, args.timeout, args.workdir)
        no_feedback = run_attempt(config, task, args.model, base_system,
                                   args.max_steps, args.timeout, args.workdir)
        placebo = run_attempt(config, task, args.model, placebo_system,
                              args.max_steps, args.timeout, args.workdir)
        candidate, candidate_ok = feedback_candidate(
            first, task, args.model, args.workdir, args.timeout,
        )
        feedback_system = base_system + "\n\nSelf-feedback guidance:\n" + candidate
        improved = run_attempt(config, task, args.model, feedback_system,
                               args.max_steps, args.timeout, args.workdir)
        task_hash = sha256_text(task)
        for arm, result in (("no_feedback", no_feedback),
                            ("formatting_placebo", placebo),
                            ("self_feedback", improved)):
            rows.append({
                "task_hash": task_hash,
                "arm": arm,
                "model": args.model,
                "harness": "codex-cli-subscription",
                **result,
            })
        feedback_receipts.append({
            "task_hash": task_hash,
            "first_attempt_won": first["won"],
            "first_attempt_steps": first["steps"],
            "candidate_ok": candidate_ok,
            "candidate_sha256": sha256_text(candidate),
            "candidate_word_count": len(candidate.split()),
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
        "schema_version": "frankengate-alfworld-codex-feedback-loop-v1",
        "dataset": {
            "source": "zhangdw/alfworld",
            "split": "valid_unseen",
            "task_count": len(args.task),
            "task_hashes": sorted({sha256_text(task) for task in args.task}),
        },
        "protocol": {
            "arms": ["no_feedback", "formatting_placebo", "self_feedback"],
            "model": args.model,
            "harness": "codex-cli-subscription",
            "max_steps": args.max_steps,
            "expert_actions_exposed": False,
            "future_outcomes_exposed": False,
            "reset_between_attempts": True,
            "independent_replay_required": True,
        },
        "summary": summary,
        "feedback_receipts": feedback_receipts,
        "episodes": rows,
        "claim_boundary": {
            "feedback_loop_executed": True,
            "causal_skill_benefit_confirmed": False,
            "automatic_promotion_authorized": False,
            "reason": "Small family-disjoint frontier feedback comparison; promotion requires larger preregistered cohorts and independent replay.",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "summary": summary}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
