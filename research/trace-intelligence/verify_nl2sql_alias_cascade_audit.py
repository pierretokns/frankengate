#!/usr/bin/env python3
"""Verify the content-minimized same-cohort alias cascade audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SCHEMA_VERSION = "frankengate-nl2sql-alias-cascade-audit-v1"


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def verify(input_path: Path, output_path: Path) -> dict[str, object]:
    result = json.loads(input_path.read_text(encoding="utf-8"))
    expected = result.get("result_sha256")
    copy = dict(result)
    copy.pop("result_sha256", None)
    arms = result.get("arms", {})
    required = {"lexical_scope", "exact_scope", "dense_scope", "frontier_scope"}
    checks = {
        "schema_version": result.get("schema_version") == SCHEMA_VERSION,
        "result_hash": expected == digest(copy),
        "raw_content_not_committed": result.get("inputs", {}).get("raw_content_committed") is False,
        "all_same_cohort_arms": set(arms) == required,
        "same_cohort_nonempty": result.get("same_cohort", {}).get("selected_cases", 0) > 0,
        "stratified_categories_present": {"explicit_target", "implicit_target", "scope_swapped_nil"}.issubset(result.get("stratified", {})),
        "synthetic_gate_present": isinstance(result.get("synthetic_gate"), dict),
        "claim_boundary_present": isinstance(result.get("claim_boundary"), dict),
        "interpretation_present": len(result.get("interpretation", {})) >= 3,
    }
    receipt = {
        "schema_version": "frankengate-nl2sql-alias-cascade-audit-verification-v1",
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
