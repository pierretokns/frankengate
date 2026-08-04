#!/usr/bin/env python3
"""Verify a content-minimized outcome-backed BIRD query-planning receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-bird-artifact-query-planning-probe-v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(result_path: Path, raw_dir: Path) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected BIRD artifact query-planning schema")
    selected = int(result.get("cohort", {}).get("targets", 0))
    if result.get("failures") != 0:
        raise ValueError("planner calls are incomplete")
    protocol = result.get("protocol", {})
    if protocol.get("planner_sees_result_labels") is not False or protocol.get("planner_sees_target_sql") is not False:
        raise ValueError("planner visibility violation")
    receipts = result.get("raw_receipts", [])
    if len(receipts) != selected:
        raise ValueError("raw receipt count mismatch")
    for receipt in receipts:
        index = int(receipt["case_index"])
        path = raw_dir / f"case-{index:03d}.json"
        if not path.exists() or sha256(path) != receipt.get("raw_sha256"):
            raise ValueError(f"raw receipt hash mismatch for case {index}")
    rows = result.get("rows", [])
    if len(rows) != selected:
        raise ValueError("row count mismatch")
    for arm_name, arm in result.get("arms", {}).items():
        if arm_name not in {"baseline", "planned"} or int(arm.get("targets", 0)) != selected:
            raise ValueError(f"incomplete arm: {arm_name}")
        for metric in ("result_match_at_1", "result_match_at_5", "result_match_at_10"):
            value = arm.get(metric)
            if not isinstance(value, int) or value < 0 or value > selected:
                raise ValueError(f"invalid metric {arm_name}.{metric}")
    return {
        "schema_version": "bird-artifact-query-planning-verification-v1",
        "source_result_sha256": sha256(result_path),
        "targets_verified": selected,
        "raw_hashes_match": True,
        "outcomes_hidden_from_planner": True,
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
