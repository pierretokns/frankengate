#!/usr/bin/env python3
"""Verify the modern vocabulary NL2SQL receipt without reading raw text."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    checks = {
        "schema": receipt.get("schema_version") == "frankengate-nl2sql-modern-vocabulary-benchmark-v1",
        "database_folds": len(receipt.get("folds", [])) >= 2,
        "targets_positive": receipt.get("aggregate", {}).get("target_count", 0) > 0,
        "counts_consistent": receipt.get("aggregate", {}).get("termhood_targets", 0) <= receipt.get("aggregate", {}).get("target_count", 0),
        "claim_boundary": receipt.get("claim_boundary", {}).get("semantic_alias_truth_established") is False,
        "hash": receipt.get("result_sha256") == stable_hash({key: value for key, value in receipt.items() if key != "result_sha256"}),
    }
    result = {"schema_version": "frankengate-nl2sql-modern-vocabulary-verification-v1", "all_passed": all(checks.values()), "checks": checks}
    result["receipt_sha256"] = hashlib.sha256(args.receipt.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0 if result["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
