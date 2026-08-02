#!/usr/bin/env python3
"""Verify the separate-protocol skill replay synthesis receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SCHEMA_VERSION = "frankengate-skill-replay-evidence-synthesis-v1"


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def verify(input_path: Path, output_path: Path) -> dict[str, object]:
    result = json.loads(input_path.read_text(encoding="utf-8"))
    expected = result.get("result_sha256")
    copy = dict(result)
    copy.pop("result_sha256", None)
    comparisons = result.get("comparisons", {})
    checks = {
        "schema_version": result.get("schema_version") == SCHEMA_VERSION,
        "result_hash": expected == digest(copy),
        "four_comparisons": set(comparisons) == {"skilllearn_changed_data", "bird_family_disjoint", "changed_system_subplan", "alfworld_skillopt"},
        "adoption_present": isinstance(result.get("adoption"), dict),
        "datasets_not_pooled": result.get("claim_boundary", {}).get("datasets_pooled") is False,
        "promotion_not_authorized": result.get("claim_boundary", {}).get("automatic_promotion_authorized") is False,
        "source_receipts_present": len(result.get("source_receipts", {})) == 4,
    }
    receipt = {"schema_version": "frankengate-skill-replay-evidence-synthesis-verification-v1", "passed": all(checks.values()), "checks": checks, "result_sha256": expected}
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
