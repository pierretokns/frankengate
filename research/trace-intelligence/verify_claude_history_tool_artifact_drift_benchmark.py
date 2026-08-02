#!/usr/bin/env python3
"""Verify the content-minimized chronological artifact-drift receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SCHEMA_VERSION = "frankengate-claude-history-tool-artifact-drift-v1"


def digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def verify(input_path: Path, output_path: Path) -> dict[str, object]:
    result = json.loads(input_path.read_text(encoding="utf-8"))
    expected = result.get("result_sha256")
    copy = dict(result)
    copy.pop("result_sha256", None)
    exact = result.get("exact_buckets", {})
    parameterized = result.get("parameterized_buckets", {})
    coverage = result.get("coverage", {})
    checks = {
        "schema_version": result.get("schema_version") == SCHEMA_VERSION,
        "result_hash": expected == digest(copy),
        "raw_content_not_committed": result.get("source", {}).get("raw_content_committed") is False,
        "claim_boundary_present": isinstance(result.get("claim_boundary"), dict),
        "frozen_protocol": result.get("protocol", {}).get("late_priors_updated") is False,
        "required_exact_buckets": {
            "no_early_prior_success",
            "early_same_project_success",
            "early_other_project_success_only",
        }.issubset(exact),
        "required_parameterized_buckets": {
            "no_early_prior_keyshape_success",
            "early_same_project_keyshape_success",
            "early_other_project_keyshape_success_only",
        }.issubset(parameterized),
        "category_buckets_present": len(result.get("category_buckets", {})) >= 3,
        "nonempty_early_and_late": coverage.get("early_paired_call_count", 0) > 0 and coverage.get("late_paired_call_count", 0) > 0,
    }
    receipt = {
        "schema_version": "frankengate-claude-history-tool-artifact-drift-verification-v1",
        "passed": all(checks.values()),
        "checks": checks,
        "result_sha256": expected,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if verify(args.input, args.output)["passed"] else 1)
