#!/usr/bin/env python3
"""Content-free verifier for the BIRD trace retrieval cascade receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-bird-trace-retrieval-cascade-verification-v1"
ARMS = ("lexical", "identifier", "dense", "hybrid")


def verify(receipt_path: Path) -> dict[str, Any]:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    aggregates = receipt["aggregate"]
    targets = receipt["cohort"]["validated_artifacts"]
    checks = {
        "schema": receipt.get("schema_version") == "frankengate-bird-trace-retrieval-cascade-v1",
        "all_arms_present": set(aggregates) == set(ARMS),
        "target_counts": all(values.get("targets") == targets for values in aggregates.values()),
        "metric_bounds": all(
            0 <= values.get("result_match_at_1", -1) <= values["targets"]
            and values.get("result_match_at_1", -1) <= values.get("result_match_at_5", -1) <= values.get("result_match_at_10", -1)
            and 0 <= values.get("same_template_at_1", -1) <= values.get("same_template_at_5", -1) <= values["targets"]
            for values in aggregates.values()
        ),
        "claim_boundary": (
            receipt["claim_boundary"]["outcome_backed_candidate_retrieval_measured"]
            and not receipt["claim_boundary"]["dense_authority_established"]
            and not receipt["claim_boundary"]["enterprise_quality_established"]
        ),
        "raw_content_external": receipt["source"]["raw_content_committed"] is False,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "all_passed": all(checks.values()),
        "checks": checks,
        "receipt_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
    }


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
