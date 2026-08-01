#!/usr/bin/env python3
"""Verify the minimized Termolator Wisp receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def stable_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    checks = {
        "schema": receipt.get("schema_version") == "frankengate-termolator-wisp-benchmark-v1",
        "dataset_pinned": receipt.get("dataset", {}).get("dataset_revision") == "c2c90b59174318ab0b163ec9c9ac82bb879288ce",
        "full_wisp_cohort": receipt.get("dataset", {}).get("document_count") == 49,
        "split_positive": receipt.get("dataset", {}).get("foreground_count", 0) > 0 and receipt.get("dataset", {}).get("background_count", 0) > 0,
        "tool_succeeded": receipt.get("tool", {}).get("returncode") == 0,
        "candidates_positive": receipt.get("candidates", {}).get("count", 0) > 0,
        "not_overclaimed": receipt.get("claim_boundary", {}).get("enterprise_term_quality_established") is False and receipt.get("claim_boundary", {}).get("retrieval_impact_evaluated") is False,
        "hash": receipt.get("result_sha256") == stable_hash({key: value for key, value in receipt.items() if key != "result_sha256"}),
    }
    output = {"schema_version": "frankengate-termolator-wisp-verification-v1", "all_passed": all(checks.values()), "checks": checks}
    output["receipt_sha256"] = hashlib.sha256(args.receipt.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output, sort_keys=True))
    return 0 if output["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
