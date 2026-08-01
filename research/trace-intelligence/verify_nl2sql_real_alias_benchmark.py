#!/usr/bin/env python3
"""Verify the content-minimized real NL2SQL alias benchmark receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-nl2sql-real-alias-benchmark-v1"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(result_path: Path, raw_dir: Path) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected real alias benchmark schema")
    calls = result.get("frontier_calls", {})
    receipts = calls.get("receipts", [])
    if calls.get("failures") != 0 or calls.get("completed") != calls.get("requested") or len(receipts) != calls.get("completed"):
        raise ValueError("frontier calls are incomplete")
    if result.get("protocol", {}).get("frontier_sees_gold_targets") is not False:
        raise ValueError("frontier prompt was allowed to see gold targets")
    for receipt in receipts:
        path = raw_dir / f"case-{int(receipt['case']):03d}.json"
        if not path.exists() or _sha(path) != receipt.get("raw_sha256"):
            raise ValueError(f"raw hash mismatch for case {receipt['case']}")
    per_case = result.get("per_case", [])
    if len(per_case) != calls.get("completed"):
        raise ValueError("per-case receipt count mismatch")
    decisions: Counter[tuple[str, str]] = Counter(
        (str(row["category"]), str(row["frontier_decision"])) for row in per_case
    )
    nil_total = sum(count for (category, _), count in decisions.items() if category == "scope_swapped_nil")
    nil_abstain = decisions["scope_swapped_nil", "abstain"]
    return {
        "schema_version": "frankengate-nl2sql-real-alias-verification-v1",
        "source_result_sha256": _sha(result_path),
        "cases_verified": len(per_case),
        "raw_hashes_match": True,
        "frontier_decisions_by_category": {
            category: dict(sorted({decision: count for (observed_category, decision), count in decisions.items() if observed_category == category}.items()))
            for category in sorted({category for category, _ in decisions})
        },
        "scope_swapped_nil_abstention": round(nil_abstain / nil_total, 6) if nil_total else None,
        "content_minimized": True,
        "verification_passed": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = verify(args.result, args.raw_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
