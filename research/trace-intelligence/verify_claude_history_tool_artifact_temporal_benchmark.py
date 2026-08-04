#!/usr/bin/env python3
"""Verify the content-minimized temporal artifact benchmark receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SCHEMA_VERSION = "frankengate-claude-history-tool-artifact-temporal-v1"


def digest(value: object) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def verify(input_path: Path, output_path: Path) -> dict[str, object]:
    result = json.loads(input_path.read_text(encoding="utf-8"))
    expected = result.get("result_sha256")
    copy = dict(result)
    copy.pop("result_sha256", None)
    buckets = result.get("buckets", {})
    parameter_buckets = result.get("parameter_buckets", {})
    checks = {
        "schema_version": result.get("schema_version") == SCHEMA_VERSION,
        "result_hash": expected == digest(copy),
        "raw_content_not_committed": result.get("source", {}).get("raw_content_committed") is False,
        "claim_boundary_present": isinstance(result.get("claim_boundary"), dict),
        "required_buckets_present": {"no_prior_success", "prior_same_project_success", "prior_other_project_success_only"}.issubset(buckets),
        "required_parameter_buckets_present": {"no_prior_keyshape_success", "parameter_same_project_success", "parameter_other_project_success_only"}.issubset(parameter_buckets),
        "category_buckets_present": len(result.get("category_buckets", {})) >= 3,
        "recovery_buckets_present": {"no_same_session_error", "after_same_session_error"}.issubset(result.get("recovery_buckets", {})),
        "nonempty_calls": result.get("coverage", {}).get("paired_call_count", 0) > 0,
    }
    receipt = {"schema_version": "frankengate-claude-history-tool-artifact-temporal-verification-v1", "passed": all(checks.values()), "checks": checks, "result_sha256": expected}
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
