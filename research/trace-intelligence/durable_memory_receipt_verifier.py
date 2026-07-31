#!/usr/bin/env python3
"""Verify aggregate-only durable-memory receipts against external raw summaries."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any


def verify(receipt: Path, raw: Path) -> dict[str, Any]:
    committed = json.loads(receipt.read_text(encoding="utf-8"))
    observed = json.loads(raw.read_text(encoding="utf-8"))
    if committed.get("claim_boundary", {}).get("causal_memory_benefit_confirmed") is not False:
        raise ValueError("causal memory boundary must remain false")
    expected = committed.get("summary", {})
    actual = observed.get("summary", {})
    mismatches = []
    for key, fields in expected.items():
        if key not in actual:
            mismatches.append(f"missing {key}")
            continue
        for field in ("episodes", "wins", "invalid_actions", "mean_steps", "steps"):
            left, right = fields.get(field), actual[key].get(field)
            if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                equal = math.isclose(float(left), float(right), rel_tol=1e-9, abs_tol=1e-6)
            else:
                equal = left == right
            if not equal:
                mismatches.append(f"{key}.{field}")
    if mismatches:
        raise ValueError("receipt mismatch: " + ", ".join(mismatches))
    return {"receipt": receipt.name, "raw": raw.name, "summary_keys_verified": len(expected), "all_passed": True, "raw_content_committed": False}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = {"schema_version": "frankengate-durable-memory-verification-v1", "check": verify(args.receipt, args.raw), "all_passed": True}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
