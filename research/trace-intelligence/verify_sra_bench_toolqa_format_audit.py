#!/usr/bin/env python3
"""Verify the conservative ToolQA format audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.receipt.read_text(encoding="utf-8"))
    arms = data["arms"]
    expected = {"no_skill": (4, 4), "bge_top1": (7, 8), "bge_top5": (6, 7), "bge_progressive": (7, 8), "gold_oracle": (7, 8)}
    checks = {
        "schema": data.get("schema_version") == "frankengate-sra-bench-toolqa-format-audit-v1",
        "task_count": data.get("dataset", {}).get("tasks") == 14,
        "arms_present": set(arms) == set(expected),
        "records": all(arm.get("records") == 14 for arm in arms.values()),
        "metrics_and_recovery_counts": all(arms[name]["strict_metrics"]["correct"] == strict and arms[name]["format_recovered_correct"] == recovered for name, (strict, recovered) in expected.items()),
        "only_conservative_rules": data.get("protocol", {}).get("semantic_inference") is False,
        "promotion_blocked": data.get("protocol", {}).get("promotion_authorized") is False,
        "claim_boundary": bool(data.get("claim_boundary")),
    }
    result = {"schema_version": "frankengate-sra-bench-toolqa-format-audit-verification-v1", "source_receipt_sha256": hashlib.sha256(args.receipt.read_bytes()).hexdigest(), "checks": checks, "verification_passed": all(checks.values())}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0 if result["verification_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
