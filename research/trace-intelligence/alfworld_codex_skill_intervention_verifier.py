#!/usr/bin/env python3
"""Fresh-environment verifier for the Codex SkillOpt pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def replay(config: dict[str, Any], task: str, actions: list[str]) -> dict[str, Any]:
    from alfworld.agents.environment.alfred_tw_env import AlfredTWEnv

    base = AlfredTWEnv(config, "eval_out_of_distribution")
    base.game_files = [task]
    base.num_games = 1
    env = base.init_env(batch_size=1)
    try:
        _, infos = env.reset()
        done = [False]
        steps = 0
        invalid = 0
        for action in actions:
            if done[0]:
                break
            admissible = list(infos.get("admissible_commands", [[]])[0])
            invalid += int(action not in admissible)
            _, _, done, infos = env.step([action])
            steps += 1
        return {"won": bool(infos.get("won", [False])[0]), "steps": steps, "invalid_executed_actions": invalid}
    finally:
        env.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--alfworld-data", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    import yaml

    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    config["dataset"]["num_eval_games"] = 1
    config["general"]["use_cuda"] = False
    os.environ["ALFWORLD_DATA"] = str(args.alfworld_data.resolve(strict=True))
    index = {
        sha256_text(str(path)): str(path)
        for path in (args.alfworld_data / "json_2.1.1" / "valid_unseen").rglob("game.tw-pddl")
    }
    mismatches = []
    rows = receipt.get("episodes", [])
    for row in rows:
        task = index.get(row.get("task_hash"))
        actions = row.get("action_sequence")
        if task is None or not isinstance(actions, list):
            mismatches.append({"reason": "missing_task_or_actions", "row": row})
            continue
        actual = replay(config, task, actions)
        expected = {
            "won": bool(row.get("won")),
            "steps": int(row.get("steps", -1)),
            "invalid_executed_actions": 0,
        }
        if actual != expected:
            mismatches.append({"arm": row.get("arm"), "task_hash": row.get("task_hash"), "expected": expected, "actual": actual})
    result = {
        "schema_version": "frankengate-alfworld-codex-skillopt-verification-v1",
        "receipt": args.receipt.name,
        "rows_verified": len(rows),
        "all_passed": not mismatches,
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "all_executed_actions_admissible": not any(
            item.get("actual", {}).get("invalid_executed_actions", 0) for item in mismatches
        ),
        "verifier": "fresh ALFWorld environments; no model calls",
        "raw_content_policy": "actions and aggregate outcomes only; no prompts or model responses",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("all_passed", "rows_verified", "mismatch_count")}, sort_keys=True))
    return 0 if result["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
