#!/usr/bin/env python3
"""Verify the content-free acronym stability receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-acronym-cross-cohort-stability-verification-v1"


def digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result: dict[str, Any] = json.loads(args.input.read_text(encoding="utf-8"))
    expected = result.get("result_sha256")
    unsigned = dict(result)
    unsigned.pop("result_sha256", None)
    checks = {
        "schema": result.get("schema_version") == "frankengate-acronym-cross-cohort-stability-v1",
        "result_hash": expected == digest(unsigned),
        "content_free": all(not row.get("raw_content_committed", True) for row in result.get("cohorts", {}).values()),
        "cohort_count": len(result.get("cohorts", {})) >= 2,
        "pairwise_complete": len(result.get("pairwise", {})) == len(result.get("cohorts", {})) * (len(result.get("cohorts", {})) - 1) // 2,
        "claim_boundary": result.get("claim_boundary", {}).get("alias_quality") is False,
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
