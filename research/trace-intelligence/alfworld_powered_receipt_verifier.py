#!/usr/bin/env python3
"""Verify aggregate projections for the powered family-disjoint ALFWorld run."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def stable(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def verify(receipt_path: Path, raw_path: Path) -> dict[str, Any]:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("raw powered receipt must be a list")
    if receipt.get("schema_version") != "frankengate-alfworld-family-disjoint-powered-v1":
        raise ValueError("unexpected powered receipt schema")
    expected_tasks = set(receipt["dataset"]["task_hashes"])
    if set(row.get("task_hash") for row in raw) != expected_tasks:
        raise ValueError("raw task set does not match receipt")
    expected_summary: dict[str, dict[str, Any]] = {}
    for row in raw:
        if not {"model", "harness", "arm", "won", "steps", "invalid_action_count"} <= row.keys():
            raise ValueError("raw row is missing aggregate fields")
        key = f"{row['model']}|{row['harness']}|{row['arm']}"
        bucket = expected_summary.setdefault(
            key, {"episodes": 0, "wins": 0, "invalid_actions": 0, "steps": 0, "elapsed_ms": 0.0}
        )
        bucket["episodes"] += 1
        bucket["wins"] += int(row["won"])
        bucket["invalid_actions"] += int(row["invalid_action_count"])
        bucket["steps"] += int(row["steps"])
        bucket["elapsed_ms"] += float(row.get("elapsed_ms", 0.0))
    for bucket in expected_summary.values():
        bucket["win_rate"] = bucket["wins"] / bucket["episodes"]
        bucket["mean_steps"] = bucket["steps"] / bucket["episodes"]
        bucket["mean_elapsed_ms"] = bucket["elapsed_ms"] / bucket["episodes"]
    if stable(expected_summary) != stable(receipt.get("summary")):
        raise ValueError("receipt summary does not match raw aggregate")
    return {
        "schema_version": "frankengate-alfworld-powered-receipt-verification-v1",
        "all_passed": True,
        "receipt": receipt_path.name,
        "raw": raw_path.name,
        "raw_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
        "rows_verified": len(raw),
        "task_count_verified": len(expected_tasks),
        "summary_keys_verified": len(expected_summary),
        "raw_content_policy": "aggregate episode fields only; no model text",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.receipt, args.raw)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
