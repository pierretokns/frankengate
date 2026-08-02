#!/usr/bin/env python3
"""Verify the content-free same-user DataClaw support receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-dataclaw-same-user-artifact-support-verification-v1"


def digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result: dict[str, Any] = json.loads(args.input.read_text(encoding="utf-8"))
    unsigned = dict(result)
    expected = unsigned.pop("result_sha256", None)
    checks = {
        "schema": result.get("schema_version") == "frankengate-dataclaw-same-user-artifact-support-v1",
        "result_hash": expected == digest(unsigned),
        "users_present": len(result.get("users", {})) >= 1,
        "tier_fields_present": all(
            set(row.get("support_tiers", {})) == {
                "support_at_least_two_sessions",
                "support_at_least_five_sessions",
                "support_at_least_two_projects",
                "support_at_least_three_projects",
                "cross_project_and_friction_adjacent",
                "repeated_and_friction_adjacent",
            }
            for row in result.get("users", {}).values()
        ),
        "rate_bounded": all(0 <= row.get("occurrence_totals", {}).get("friction_context_rate", -1) <= 1 for row in result.get("users", {}).values()),
        "raw_content_absent": result.get("raw_content_committed") is False and all(row.get("raw_content_committed") is False for row in result.get("users", {}).values()),
        "claim_boundary": result.get("claim_boundary", {}).get("promotion_authorized") is False,
    }
    verification = {
        "schema_version": SCHEMA_VERSION,
        "passed": all(checks.values()),
        "checks": checks,
        "result_sha256": expected,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(verification, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(verification, sort_keys=True))
    return 0 if verification["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
