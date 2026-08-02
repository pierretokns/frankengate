#!/usr/bin/env python3
"""Verify the bounded ToolQA incorporation receipt."""

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
    checks = {
        "schema": data.get("schema_version") == "frankengate-sra-bench-toolqa-incorporation-v1",
        "task_count": data.get("dataset", {}).get("tasks") == 14,
        "all_arms_have_14_records": all(arm.get("records") == 14 for arm in arms.values()),
        "all_arms_finished": all(arm.get("finished") == 14 and arm.get("halted") == 0 for arm in arms.values()),
        "strict_metrics_reconcile": arms["no_skill"]["metrics"] == {"correct": 4, "total": 14, "accuracy": 4 / 14} and arms["bge_top1"]["metrics"] == {"correct": 7, "total": 14, "accuracy": 7 / 14} and arms["gold_skill_oracle"]["metrics"] == {"correct": 7, "total": 14, "accuracy": 7 / 14},
        "retrieval_hits_reconcile": data.get("retrieval", {}).get("bge_top1_gold_skill_hits") == 6,
        "dense_lift_reconciles": arms["bge_top1"]["metrics"]["correct"] > arms["no_skill"]["metrics"]["correct"],
        "oracle_tie_reconciles": arms["bge_top1"]["metrics"]["correct"] == arms["gold_skill_oracle"]["metrics"]["correct"],
        "raw_outputs_external": data.get("protocol", {}).get("raw_outputs_committed") is False,
        "promotion_blocked": data.get("decision", {}).get("skill_release_authorized") is False and data.get("decision", {}).get("changed_system_replay_measured") is False,
        "claim_boundary": bool(data.get("claim_boundary")),
    }
    result = {"schema_version": "frankengate-sra-bench-toolqa-incorporation-verification-v1", "source_receipt_sha256": hashlib.sha256(args.receipt.read_bytes()).hexdigest(), "checks": checks, "verification_passed": all(checks.values())}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0 if result["verification_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
