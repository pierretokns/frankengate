#!/usr/bin/env python3
"""Create a content-free, reproducible Recovery-Bench failure-set manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


def _hash_files(paths: List[Path], root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
        digest.update(b"\n")
    return digest.hexdigest()


def build_manifest(runs_root: Path) -> Dict[str, Any]:
    result_files = sorted(runs_root.rglob("result.json"))
    failures: List[Dict[str, Any]] = []
    missing_reward: List[Dict[str, Any]] = []
    for result_path in result_files:
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            continue
        reward_path = result_path.parent / "verifier" / "reward.txt"
        try:
            reward = reward_path.read_text(encoding="utf-8").strip()
        except OSError:
            missing_reward.append({"result": str(result_path.relative_to(runs_root))})
            continue
        if reward != "0":
            continue
        task_id = result.get("task_id") if isinstance(result.get("task_id"), dict) else {}
        task_name = result.get("task_name")
        if not task_name or not task_id.get("path"):
            continue
        trajectory_path = result_path.parent / "agent" / "trajectory.json"
        failures.append(
            {
                "task_name": str(task_name),
                "task_path": str(task_id["path"]),
                "task_checksum": str(result.get("task_checksum", "")),
                "trajectory": str(trajectory_path.relative_to(runs_root))
                if trajectory_path.exists()
                else None,
                "initial_result": str(result_path.relative_to(runs_root)),
            }
        )
    failures.sort(key=lambda item: item["task_name"])
    return {
        "schema": "frankengate.recovery_bench_failure_manifest.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_revision": _hash_files(result_files, runs_root),
        "result_file_count": len(result_files),
        "failure_count": len(failures),
        "missing_reward_count": len(missing_reward),
        "missing_reward_records": missing_reward,
        "failures": failures,
        "raw_trace_content_included": False,
        "next_experiment": {
            "arms": ["no_context", "full_context", "summary_context", "reviewed_skill", "formatting_placebo"],
            "task_disjointness": "Use this exact failure set for the recovery treatment; reserve a separate task set for final confirmation.",
            "outcomes": ["verifier_reward", "repair_regression", "tool_calls", "latency", "cost"],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = build_manifest(args.runs_root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"failure_count": manifest["failure_count"], "source_revision": manifest["source_revision"]}))


if __name__ == "__main__":
    main()
