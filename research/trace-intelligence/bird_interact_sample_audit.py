#!/usr/bin/env python3
"""Audit the small public BIRD-Interact ADK sample receipts."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-bird-interact-sample-audit-v1"


def stable_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(paths: list[Path], output: Path) -> dict[str, Any]:
    modes: dict[str, dict[str, Any]] = {}
    total_samples = 0
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        mode = str(payload.get("mode", path.stem))
        samples = payload.get("samples") or []
        phase1 = sum(bool(row.get("phase1_passed")) for row in samples)
        phase2 = sum(bool(row.get("phase2_passed")) for row in samples)
        rewards = [float(row.get("total_reward", 0.0)) for row in samples]
        trajectory_counts = [
            len(row.get("tool_trajectory") or row.get("dialogue_history") or [])
            for row in samples
        ]
        follow_up_count = sum(bool(row.get("has_follow_up")) for row in samples)
        modes[mode] = {
            "source_sha256": sha256(path),
            "samples": len(samples),
            "phase1_passes": phase1,
            "phase2_passes": phase2,
            "phase1_rate": round(phase1 / len(samples), 6) if samples else 0.0,
            "phase2_rate": round(phase2 / len(samples), 6) if samples else 0.0,
            "follow_up_samples": follow_up_count,
            "reward_sum": round(sum(rewards), 6),
            "reward_mean": round(sum(rewards) / len(rewards), 6) if rewards else 0.0,
            "trajectory_count_min": min(trajectory_counts) if trajectory_counts else 0,
            "trajectory_count_max": max(trajectory_counts) if trajectory_counts else 0,
            "budget_used_present": sum("budget_used" in row for row in samples),
        }
        total_samples += len(samples)
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "repository": "bird-bench/BIRD-Interact",
            "revision": "451fe2c3518ee1cf908d8139e2913483bd519381",
            "sample_files": [str(path) for path in paths],
            "raw_content_committed": False,
        },
        "aggregate": {"modes": modes, "samples": total_samples},
        "claim_boundary": {
            "public_trajectory_schema_audited": True,
            "full_benchmark_quality_established": False,
            "clarification_causal_effect_established": False,
            "enterprise_user_behavior_established": False,
            "reason": "Twenty public ADK examples expose trajectories and rewards, but they are a tiny curated sample and do not substitute for the withheld 600-task evaluator bundle.",
        },
    }
    receipt["result_sha256"] = hashlib.sha256(stable_json(receipt)).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt["aggregate"], sort_keys=True))
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit([path.resolve(strict=True) for path in args.input], args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
