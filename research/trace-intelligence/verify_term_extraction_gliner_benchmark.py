#!/usr/bin/env python3
"""Independent content-free receipt verifier for the GLiNER term probe."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def stable_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def contains_forbidden_receipt_fields(value: Any) -> bool:
    forbidden = {"text", "content", "input", "output", "prompt", "sql"}
    if isinstance(value, dict):
        if forbidden.intersection(value):
            return True
        return any(contains_forbidden_receipt_fields(child) for child in value.values())
    if isinstance(value, list):
        return any(contains_forbidden_receipt_fields(child) for child in value)
    return False


def run(receipt_path: Path, raw_path: Path | None, output_path: Path) -> dict[str, Any]:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    checks = {
        "schema": receipt.get("schema_version") == "frankengate-term-extraction-gliner-benchmark-v2",
        "raw_not_committed": receipt.get("claim_boundary", {}).get("raw_text_committed") is False,
        "retrieval_not_overclaimed": receipt.get("claim_boundary", {}).get("retrieval_impact_evaluated") is False,
        "result_hash": receipt.get("result_sha256") == stable_hash({k: v for k, v in receipt.items() if k != "result_sha256"}),
        "dataset_count_positive": int(receipt.get("dataset", {}).get("document_count", 0)) > 0,
        "baseline_present": isinstance(receipt.get("baseline"), dict),
        "gliner_present": isinstance(receipt.get("gliner"), dict),
        "receipt_content_minimized": not contains_forbidden_receipt_fields(receipt),
    }
    if raw_path is not None:
        raw_rows = json.loads(raw_path.read_text(encoding="utf-8"))
        checks["raw_count_matches"] = len(raw_rows) == int(receipt["gliner"]["entity_count"])
        checks["raw_rows_have_no_authority_fields"] = all(
            set(row).issubset({"path_hash", "label", "text", "score"}) for row in raw_rows
        )
    result = {
        "schema_version": "frankengate-term-extraction-gliner-verification-v1",
        "receipt_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
        "checks": checks,
        "all_passed": all(checks.values()),
    }
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not result["all_passed"]:
        raise SystemExit(json.dumps(result, sort_keys=True))
    print(json.dumps(result, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--raw", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.receipt, args.raw, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
