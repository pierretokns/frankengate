#!/usr/bin/env python3
"""Content-free verifier for the Trace Commons domain-adapter receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SCHEMA_VERSION = "frankengate-trace-commons-domain-adapter-verification-v1"


def verify(receipt: Path) -> dict:
    data = json.loads(receipt.read_text(encoding="utf-8"))
    rows = data["aggregate"]
    checks = {
        "schema": data.get("schema_version") == "frankengate-trace-commons-domain-adapter-v1",
        "arms_present": set(rows) == {"prompt", "identifier", "combined"},
        "leave_one_project_out": data["claim_boundary"]["leave_one_project_out"],
        "bounds": all(0 <= row["baseline_mrr"] <= 1 and 0 <= row["adapter_mrr"] <= 1 and row["evaluated_sessions"] >= 0 for row in rows.values()),
        "claim_boundary": not data["claim_boundary"]["enterprise_quality_established"] and not data["claim_boundary"]["cross_user_skill_gain_established"],
        "raw_content_external": data["source"]["raw_content_committed"] is False,
    }
    return {"schema_version": SCHEMA_VERSION, "all_passed": all(checks.values()), "checks": checks, "receipt_sha256": hashlib.sha256(receipt.read_bytes()).hexdigest()}


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
