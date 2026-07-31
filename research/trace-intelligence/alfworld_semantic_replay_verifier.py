#!/usr/bin/env python3
"""Independently replay aggregate ALFWorld action receipts.

The verifier never calls a model. It resolves task hashes against the pinned
environment, executes the recorded admissible actions in a fresh environment,
and recomputes the terminal outcome and step count.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def task_index(root: Path) -> dict[str, str]:
    return {sha256_text(str(path)): str(path) for path in root.rglob("game.tw-pddl")}


def replay_row(config: dict[str, Any], task: str, actions: list[str]) -> dict[str, Any]:
    from alfworld.agents.environment.alfred_tw_env import AlfredTWEnv

    base = AlfredTWEnv(config, "eval_out_of_distribution")
    base.game_files = [task]
    base.num_games = 1
    env = base.init_env(batch_size=1)
    try:
        _, infos = env.reset()
        done = [False]
        steps = 0
        for action in actions:
            if done[0]:
                break
            _, _, done, infos = env.step([action])
            steps += 1
        return {"won": bool(infos.get("won", [False])[0]), "steps": steps}
    finally:
        env.close()


def verify(receipt_path: Path, raw_path: Path, alfworld_data: Path, config_path: Path) -> dict[str, Any]:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    if not receipt.get("protocol", {}).get("action_sequences_recorded"):
        raise ValueError("receipt does not attest recorded action sequences")
    if not isinstance(raw, list) or not raw:
        raise ValueError("raw action receipt must be a non-empty list")
    import yaml

    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    config["dataset"]["num_eval_games"] = 1
    config["general"]["use_cuda"] = False
    os.environ["ALFWORLD_DATA"] = str(alfworld_data.resolve(strict=True))
    index = task_index(alfworld_data / "json_2.1.1" / "valid_unseen")
    mismatches: list[dict[str, Any]] = []
    for row in raw:
        task_hash = row.get("task_hash")
        task = index.get(task_hash)
        actions = row.get("action_sequence")
        if task is None:
            raise ValueError(f"task hash not found in pinned split: {task_hash}")
        if not isinstance(actions, list) or not all(isinstance(item, str) for item in actions):
            raise ValueError("row is missing a string action sequence")
        replayed = replay_row(config, task, actions)
        expected = {"won": bool(row.get("won")), "steps": int(row.get("steps", -1))}
        if replayed != expected:
            mismatches.append({"task_hash": task_hash, "arm": row.get("arm"), "model": row.get("model"), "harness": row.get("harness"), "expected": expected, "replayed": replayed})
    return {
        "schema_version": "frankengate-alfworld-semantic-replay-verification-v1",
        "all_passed": not mismatches,
        "receipt": receipt_path.name,
        "raw": raw_path.name,
        "raw_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
        "rows_verified": len(raw),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "verifier": "fresh ALFWorld environment replay; no model calls",
        "raw_content_policy": "environment action sequences only; no prompts or model responses",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--alfworld-data", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.receipt, args.raw, args.alfworld_data, args.config)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("all_passed", "rows_verified", "mismatch_count")}, sort_keys=True))
    return 0 if result["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
