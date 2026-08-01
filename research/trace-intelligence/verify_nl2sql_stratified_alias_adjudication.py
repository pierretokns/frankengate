#!/usr/bin/env python3
"""Verify the content-minimized stratified alias adjudication receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-nl2sql-stratified-alias-adjudication-v1"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(result_path: Path, raw_dir: Path) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected stratified alias schema")
    if result.get("cases", {}).get("ground_truth") != "public synthetic construction-time labels; not SME truth":
        raise ValueError("ground-truth boundary missing")
    arms = result.get("arms", [])
    if len(arms) != 2:
        raise ValueError("two independent adjudication arms required")
    for arm in arms:
        score = arm.get("score", {})
        for field in ("surface_accuracy", "candidate_accuracy", "wrong_system_accuracy", "nil_unclear_abstention"):
            if score.get(field) != 1.0:
                raise ValueError(f"unexpected capability-gate failure: {arm['role']} {field}")
    inter = result.get("inter_judge", {})
    if inter.get("prompt_hashes_distinct") is not True or inter.get("surface_agreement") != 1.0 or inter.get("candidate_agreement") != 1.0:
        raise ValueError("independent adjudicators did not agree")
    receipts = inter.get("raw_receipts", [])
    if len(receipts) != 2:
        raise ValueError("raw receipt count mismatch")
    for index, receipt in enumerate(receipts, start=1):
        raw_path = raw_dir / f"adjudication-{index:02d}.json"
        if not raw_path.exists() or _sha(raw_path) != receipt.get("raw_sha256"):
            raise ValueError(f"raw hash mismatch for arm {index}")
    return {
        "schema_version": "frankengate-nl2sql-stratified-alias-verification-v1",
        "source_result_sha256": _sha(result_path),
        "arms_verified": 2,
        "raw_hashes_match": True,
        "synthetic_only": True,
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
