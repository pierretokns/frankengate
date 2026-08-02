#!/usr/bin/env python3
"""Verify the content-free DataClaw cross-user artifact receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-dataclaw-cross-user-artifact-transfer-verification-v1"


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
    user_count = len(result.get("users", {}))
    checks = {
        "schema": result.get("schema_version") == "frankengate-dataclaw-cross-user-artifact-transfer-v1",
        "result_hash": expected == digest(unsigned),
        "at_least_two_users": user_count >= 2,
        "pairwise_complete": len(result.get("pairwise", {})) == user_count * (user_count - 1) // 2,
        "raw_content_absent": result.get("raw_content_committed") is False and all(
            row.get("raw_content_committed") is False for row in result.get("users", {}).values()
        ),
        "claim_boundary": result.get("claim_boundary", {}).get("cross_user_promotion_authorized") is False,
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
