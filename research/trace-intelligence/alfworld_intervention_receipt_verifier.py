#!/usr/bin/env python3
"""Verify content-minimized ALFWorld intervention receipts against raw runs.

Raw episode files remain outside the repository.  The verifier checks that the
committed aggregate is a faithful projection of the raw runner summary and
that negative claim boundaries cannot be accidentally relaxed.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected object")
    return value


def verify(receipt_path: Path, raw_path: Path) -> dict[str, Any]:
    receipt = _load(receipt_path)
    raw = _load(raw_path)
    if receipt.get("claim_boundary", {}).get("causal_skill_benefit_confirmed") is not False:
        raise ValueError(f"{receipt_path}: causal claim boundary is not false")
    if receipt.get("claim_boundary", {}).get("automatic_promotion_authorized") is not False:
        raise ValueError(f"{receipt_path}: promotion boundary is not false")
    raw_summary = raw.get("summary")
    committed = receipt.get("aggregate")
    if not isinstance(raw_summary, dict) or not isinstance(committed, dict):
        raise ValueError(f"{receipt_path}: missing summary/aggregate")
    mismatches: list[str] = []
    for key, expected in committed.items():
        raw_key = key.rsplit("|", 1)[0] if key.count("|") == 3 else key
        observed = raw_summary.get(raw_key)
        if observed is None:
            mismatches.append(f"missing raw key {raw_key}")
            continue
        for field in ("episodes", "wins", "invalid_actions", "mean_steps", "mean_elapsed_ms"):
            expected_value = expected.get(field)
            observed_value = observed.get(field)
            equal = expected_value == observed_value
            if isinstance(expected_value, (int, float)) and isinstance(observed_value, (int, float)):
                equal = math.isclose(float(expected_value), float(observed_value), rel_tol=1e-9, abs_tol=1e-6)
            if not equal:
                mismatches.append(f"{key}.{field}: {expected_value!r} != {observed_value!r}")
    if mismatches:
        raise ValueError(f"{receipt_path}: raw projection mismatch: {'; '.join(mismatches[:5])}")
    return {
        "receipt": receipt_path.name,
        "raw": raw_path.name,
        "aggregate_keys_verified": len(committed),
        "causal_skill_benefit_confirmed": False,
        "automatic_promotion_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pair", nargs=2, action="append", metavar=("RECEIPT", "RAW"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    checks = [verify(Path(receipt), Path(raw)) for receipt, raw in args.pair]
    result = {
        "schema_version": "frankengate-alfworld-intervention-verification-v1",
        "checks": checks,
        "all_passed": True,
        "raw_content_committed": False,
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
