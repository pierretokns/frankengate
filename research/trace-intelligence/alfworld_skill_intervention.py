#!/usr/bin/env python3
"""Run a bounded, content-minimized ALFWorld skill intervention.

The environment and model are external, revision-pinned inputs.  This runner
keeps only aggregate episode outcomes and hashes task paths; prompts and model
responses are never written to the research worktree.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

SCHEMA_VERSION = "frankengate-alfworld-skill-intervention-v1"
TRACE_MINED_SKILL = """Trace-derived procedure candidate (mined from successful action templates):
1. Parse the goal into the object, source, destination, and required transformation.
2. Use one admissible environment action at a time; do not narrate.
3. Navigate to and open the source container, then take the target object.
4. Perform the required clean, heat, cool, or slice operation before final placement.
5. Navigate to and open the destination container when needed, then put the object.
6. After each failed action, inspect the new observation and choose another admissible action.
7. Stop only after the environment reports success.
"""
FORMAT_PLACEBO = "Respond with exactly one action enclosed in <action>...</action>."


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def call_chat(endpoint: str, model: str, system: str, user: str, timeout: float) -> str:
    if endpoint.endswith("/api/chat"):
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "stream": False,
            "think": False,
            "options": {"temperature": 0, "num_predict": 96},
        }
    else:
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "stream": False,
            "temperature": 0,
            "max_tokens": 96,
        }
    req = Request(endpoint, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=timeout) as response:
        body = json.loads(response.read().decode("utf-8"))
    if endpoint.endswith("/api/chat"):
        return str(body.get("message", {}).get("content", ""))
    choices = body.get("choices") or [{}]
    return str((choices[0].get("message") or {}).get("content", ""))


def choose_action(response: str, admissible: list[str]) -> tuple[str, bool]:
    lowered = response.lower()
    tagged = re.findall(r"<action>\s*(.*?)\s*</action>", response, flags=re.I | re.S)
    tagged.extend(re.findall(r"<\s*([^<>]+?)\s*>", response, flags=re.I | re.S))
    candidates = tagged + [response.strip().splitlines()[-1] if response.strip() else ""]
    for candidate in candidates:
        candidate = candidate.strip().strip("`* ").lower()
        for action in sorted(admissible, key=len, reverse=True):
            if candidate == action.lower() or action.lower() in candidate:
                return action, True
    for action in sorted(admissible, key=len, reverse=True):
        if action.lower() in lowered:
            return action, True
    return ("look" if "look" in admissible else admissible[0]), False


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
        started = time.monotonic()
        while steps < max_steps and not done[0]:
            observation = obs[0][0]
            admissible = list(infos.get("admissible_commands", [[]])[0])
            skill = ""
            if arm == "trace_mined_procedure":
                skill = TRACE_MINED_SKILL + "\n"
            elif arm == "formatting_placebo":
                skill = FORMAT_PLACEBO + "\n"
            prompt = (
                skill
                + observation
                + "\nAdmissible actions:\n- "
                + "\n- ".join(admissible)
                + "\nChoose exactly one admissible action."
            )
            try:
                response = call_chat(
                    endpoint,
                    model,
                    "You are an ALFWorld agent. Return one action only.",
                    prompt,
                    timeout,
                )
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
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
        }
    finally:
        env.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--alfworld-data", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--task", action="append", required=True)
    parser.add_argument("--model", action="append", required=True)
    parser.add_argument("--endpoint", action="append", required=True)
    parser.add_argument("--max-steps", type=int, default=30)
    parser.add_argument("--timeout", type=float, default=45)
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
    arms = ["no_skill", "formatting_placebo", "trace_mined_procedure"]
    rows: list[dict[str, Any]] = []
    for model in args.model:
        for endpoint in args.endpoint:
            for task in args.task:
                for arm in arms:
                    rows.append(run_episode(base, task, arm, model, endpoint, args.max_steps, args.timeout))

    summary: dict[str, Any] = {}
    for row in rows:
        key = f"{row['model']}|{row['harness']}|{row['arm']}"
        bucket = summary.setdefault(key, {"episodes": 0, "wins": 0, "invalid_actions": 0, "steps": 0, "elapsed_ms": 0.0})
        bucket["episodes"] += 1
        bucket["wins"] += int(row["won"])
        bucket["invalid_actions"] += row["invalid_action_count"]
        bucket["steps"] += row["steps"]
        bucket["elapsed_ms"] += row["elapsed_ms"]
    for bucket in summary.values():
        bucket["win_rate"] = bucket["wins"] / bucket["episodes"]
        bucket["mean_steps"] = bucket["steps"] / bucket["episodes"]
        bucket["mean_elapsed_ms"] = bucket["elapsed_ms"] / bucket["episodes"]

    result = {
        "schema_version": SCHEMA_VERSION,
        "dataset": {
            "source": "zhangdw/alfworld",
            "split": "valid_unseen",
            "task_count": len(args.task),
            "task_path_hashes": sorted(sha256_text(task) for task in args.task),
        },
        "arms": arms,
        "models": args.model,
        "harnesses": ["ollama-native-api", "ollama-openai-compatible"],
        "summary": summary,
        "episodes": rows,
        "claim_boundary": {
            "semantic_intervention_executed": True,
            "causal_skill_benefit_confirmed": False,
            "automatic_promotion_authorized": False,
            "reason": "This bounded pilot uses a small held-out task set; promotion requires a preregistered larger family-disjoint matrix and independent verifier.",
        },
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "summary": summary}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
