#!/usr/bin/env python3
"""Verify the synthetic query-expansion mechanics receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    recorded = receipt.pop("result_sha256")
    expected = stable_hash(receipt)
    aggregate = receipt["aggregate"]
    checks = {
        "schema": receipt["schema_version"] == "frankengate-query-expansion-probe-v1",
        "fixture": receipt["fixture"]["documents"] == 6 and receipt["fixture"]["cases"] == 12,
        "no_model_calls": receipt["protocol"]["no_model_calls"] is True,
        "gold_only_scoring": receipt["protocol"]["gold_targets_used_only_for_scoring"] is True,
        "hash": recorded == expected,
        "keyword_lift": aggregate["querygym_keyword"]["mrr"] == 0.958333,
        "feedback_no_lift": aggregate["querygym_corpus_feedback"] == aggregate["lexical"],
        "conversation_rewrite": receipt["by_kind"]["convgqr_rewrite"]["conversation"]["recall_at_1"] == 1.0,
        "not_overclaimed": "Synthetic retrieval mechanics only" in receipt["claim_boundary"],
    }
    result = {"schema_version": "frankengate-query-expansion-verification-v1", "all_passed": all(checks.values()), "checks": checks, "receipt_sha256": hashlib.sha256(args.receipt.read_bytes()).hexdigest()}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0 if result["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
