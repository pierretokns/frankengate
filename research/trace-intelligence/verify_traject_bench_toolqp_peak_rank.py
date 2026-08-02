#!/usr/bin/env python3
"""Verify a content-minimized ToolQP peak-rank receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-traject-bench-toolqp-peak-rank-v1"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(result_path: Path, raw_dir: Path) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected peak-rank schema")
    selected = int(result.get("dataset", {}).get("selected_cases", 0))
    if selected <= 0:
        raise ValueError("no cases selected")
    protocol = result.get("protocol", {})
    if protocol.get("planner_sees_gold_targets") is not False or protocol.get("planner_sees_tool_outputs") is not False:
        raise ValueError("planner visibility violation")
    if protocol.get("planner_training_reproduced") is not False:
        raise ValueError("training claim boundary changed")
    receipts = result.get("raw_receipts", [])
    if len(receipts) != selected:
        raise ValueError("raw receipt count mismatch")
    for receipt in receipts:
        index = int(receipt["case_index"])
        path = raw_dir / f"case-{index:03d}.json"
        if not path.exists() or file_hash(path) != receipt.get("raw_sha256"):
            raise ValueError(f"raw receipt hash mismatch for case {index}")
    expected_arms = {"baseline", "union", "peak_rank"}
    if set(result.get("arms", {})) != expected_arms:
        raise ValueError("unexpected arms")
    for arm_name, arm in result["arms"].items():
        if int(arm.get("records", 0)) != selected:
            raise ValueError(f"incomplete arm: {arm_name}")
        for metric in ("candidate_coverage", "mrr", "recall_at_1", "recall_at_5", "recall_at_10"):
            value = arm.get(metric)
            if not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"invalid metric {arm_name}.{metric}")
    return {
        "schema_version": "traject-bench-toolqp-peak-rank-verification-v1",
        "source_result_sha256": file_hash(result_path),
        "cases_verified": selected,
        "raw_hashes_match": True,
        "training_boundary_verified": True,
        "verification_passed": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verification = verify(args.result, args.raw_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(verification, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(verification, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
