#!/usr/bin/env python3
"""Content-free verifier for the BIRD trace-artifact reuse receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-bird-trace-artifact-reuse-verification-v1"


def verify(receipt_path: Path) -> dict[str, Any]:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    aggregate = receipt["aggregate"]
    checks = {
        "schema": receipt.get("schema_version") == "frankengate-bird-trace-artifact-reuse-v1",
        "trace_counts": (
            aggregate["trace_sql_executed"]
            == aggregate["trace_sql_gold_result_match"] + aggregate["trace_sql_semantic_mismatch"]
        ),
        "validated_count": aggregate["validated_artifacts"] == aggregate["trace_sql_gold_result_match"],
        "natural_bounds": (
            0 <= aggregate["natural_leave_one_out_result_matches"]
            <= aggregate["natural_leave_one_out_targets"]
        ),
        "controlled_bounds": (
            0 <= aggregate["controlled_parameterized_artifact_result_matches"]
            <= aggregate["controlled_parameter_targets"]
            and aggregate["controlled_exact_artifact_result_matches"]
            <= aggregate["controlled_parameter_targets"]
        ),
        "claim_boundary": (
            receipt["claim_boundary"]["trace_artifacts_independently_validated"]
            and not receipt["claim_boundary"]["enterprise_quality_established"]
        ),
        "raw_content_external": receipt["source"]["raw_content_committed"] is False,
    }
    result = {
        "schema_version": SCHEMA_VERSION,
        "all_passed": all(checks.values()),
        "checks": checks,
        "receipt_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.receipt.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0 if result["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
