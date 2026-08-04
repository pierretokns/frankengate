#!/usr/bin/env python3
"""Verify the content-free train-only alias enrichment receipt."""

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
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    recorded = receipt.pop("result_sha256", None)
    expected = stable_hash(receipt)
    assert recorded == expected, f"result hash mismatch: {recorded} != {expected}"
    assert receipt["schema_version"] == "frankengate-nl2sql-alias-enrichment-v1"
    assert receipt["dataset"]["raw_content_committed"] is False
    assert receipt["split"]["source_row_overlap"] == 0
    assert receipt["dataset"]["evaluated_cases"] == 41
    assert receipt["alias_learning"]["target_coverage"]["support1"]["covered_targets"] == 2
    assert receipt["alias_learning"]["target_coverage"]["support2"]["covered_targets"] == 17
    aggregate = receipt["aggregate"]
    assert aggregate["lexical"]["mrr"] == 0.734885
    assert aggregate["alias_support1"]["mrr"] == 0.734885
    assert aggregate["alias_support2"]["mrr"] == 0.727542
    assert receipt["claim_boundary"].startswith("Public Defog gold-SQL")
    result = {"schema_version": "frankengate-nl2sql-alias-enrichment-verification-v1", "ok": True, "receipt_sha256": expected, "aggregate": aggregate}
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
