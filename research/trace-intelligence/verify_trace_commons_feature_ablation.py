#!/usr/bin/env python3
"""Content-free verifier for the Trace Commons feature-ablation receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SCHEMA_VERSION = "frankengate-trace-commons-feature-ablation-verification-v1"


def verify(receipt: Path) -> dict:
    data = json.loads(receipt.read_text(encoding="utf-8"))
    arms = data["arms"]
    checks = {
        "schema": data.get("schema_version") == "frankengate-trace-commons-feature-ablation-v1",
        "arms_present": {"structure", "prompt", "identifier", "combined"}.issubset(arms),
        "masked_arms_present": all(f"{name}_masked" in arms for name in ("structure", "prompt", "identifier", "combined")),
        "bounds": all(0 <= row["same_project_top1"] <= row["evaluated_sessions"] and 0 <= row["same_project_mrr"] <= 1 for row in arms.values()),
        "proxy_boundary": data["claim_boundary"]["workstream_proxy_measured"] and not data["claim_boundary"]["cross_user_identity_established"],
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
