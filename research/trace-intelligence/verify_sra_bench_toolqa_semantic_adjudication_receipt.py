#!/usr/bin/env python3
"""Verify the two-pass ToolQA semantic-adjudication receipt."""

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
    expected = {
        "no_skill": (4, 2, 1, 6, 7),
        "bge_top1": (7, 3, 0, 10, 10),
        "bge_top5": (6, 1, 0, 7, 7),
        "bge_progressive": (7, 2, 1, 9, 10),
        "gold_oracle": (7, 1, 0, 8, 8),
    }
    checks = {"schema": data.get("schema_version") == "frankengate-sra-bench-toolqa-semantic-adjudication-v1", "task_count": data.get("dataset", {}).get("tasks") == 14, "arms_present": set(data.get("arms", {})) == set(expected), "counts_reconcile": all((arm["strict_terminal_correct"], arm["accepted_consensus_on_strict_failures"], arm["judge_disagreements_on_strict_failures"], arm["conservative_accepted_lower_bound"], arm["adjudication_accepted_upper_bound"]) == values for name, values in expected.items() for arm in [data["arms"][name]]), "bounds_ordered": all(arm["conservative_accepted_lower_bound"] <= arm["adjudication_accepted_upper_bound"] <= 14 for arm in data["arms"].values()), "raw_external": data.get("protocol", {}).get("raw_judgments_committed") is False, "promotion_blocked": data.get("protocol", {}).get("promotion_authorized") is False, "claim_boundary": bool(data.get("claim_boundary"))}
    result = {"schema_version": "frankengate-sra-bench-toolqa-semantic-adjudication-verification-v1", "source_receipt_sha256": hashlib.sha256(args.receipt.read_bytes()).hexdigest(), "checks": checks, "verification_passed": all(checks.values())}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0 if result["verification_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
