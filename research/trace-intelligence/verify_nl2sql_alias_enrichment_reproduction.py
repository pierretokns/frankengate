#!/usr/bin/env python3
"""Verify the deterministic alias-enrichment reproduction receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-nl2sql-alias-enrichment-reproduction-v1"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(reproduction_path: Path, original_path: Path, output_path: Path) -> dict[str, Any]:
    reproduction = json.loads(reproduction_path.read_text(encoding="utf-8"))
    original = json.loads(original_path.read_text(encoding="utf-8"))
    if reproduction.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected reproduction schema")
    original_result_hash = original.get("result_sha256")
    rerun_hash = reproduction.get("rerun", {}).get("result_sha256")
    recorded_hash = reproduction.get("original_receipt", {}).get("result_sha256")
    if not isinstance(original_result_hash, str) or original_result_hash != rerun_hash or original_result_hash != recorded_hash:
        raise ValueError("original and rerun result hashes do not match")
    aggregate = reproduction.get("aggregate", {})
    expected = original.get("aggregate", {})
    checks = {
        "cases": expected.get("lexical", {}).get("cases") == aggregate.get("cases"),
        "lexical_mrr": expected.get("lexical", {}).get("mrr") == aggregate.get("lexical_mrr"),
        "support1_mrr": expected.get("alias_support1", {}).get("mrr") == aggregate.get("alias_support1_mrr"),
        "support2_mrr": expected.get("alias_support2", {}).get("mrr") == aggregate.get("alias_support2_mrr"),
        "semantic_alias_false": reproduction.get("claim_boundary", {}).get("semantic_alias_quality_established") is False,
    }
    if not all(checks.values()):
        raise ValueError(f"reproduction checks failed: {checks}")
    result = {
        "schema_version": "frankengate-nl2sql-alias-enrichment-reproduction-verification-v1",
        "reproduction_sha256": file_sha256(reproduction_path),
        "original_receipt_sha256": file_sha256(original_path),
        "result_hash_match": True,
        "metric_checks": checks,
        "claim_boundary_verified": True,
        "verification_passed": True,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reproduction", type=Path, required=True)
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verify(args.reproduction, args.original, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
