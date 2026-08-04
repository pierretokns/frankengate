#!/usr/bin/env python3
"""Verify the content-minimized identifier-reranker receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from nl2sql_identifier_reranker_benchmark import _aggregate, _rank_metrics, candidate_fingerprint, stable_hash


SCHEMA_VERSION = "frankengate-nl2sql-identifier-reranker-v1"


def verify(raw_path: Path, result_path: Path) -> dict[str, Any]:
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected schema version")
    if result["dataset"]["raw_sha256"] != hashlib.sha256(raw_path.read_bytes()).hexdigest():
        raise ValueError("raw hash mismatch")
    by_id = {case["case_id"]: case for case in raw["cases"]}
    rows = result.get("per_case", [])
    if len(rows) != result["dataset"]["cases"]:
        raise ValueError("case count mismatch")
    for row in rows:
        case = by_id.get(row["case_id"])
        if case is None:
            raise ValueError(f"unknown case: {row['case_id']}")
        if row["candidate_fingerprints"] != [candidate_fingerprint(candidate) for candidate in case["candidates"]]:
            raise ValueError(f"candidate hash mismatch: {row['case_id']}")
        if row["target_fingerprint"] != candidate_fingerprint(case["target_objects"][0]):
            raise ValueError(f"target hash mismatch: {row['case_id']}")
        for arm, order in row["orders"].items():
            if sorted(order) != list(range(len(case["candidates"]))):
                raise ValueError(f"invalid order: {row['case_id']}/{arm}")
            if row["metrics"][arm] != _rank_metrics(case, order):
                raise ValueError(f"metric mismatch: {row['case_id']}/{arm}")
    for arm, aggregate in result["aggregate"].items():
        expected = _aggregate([row["metrics"][arm] for row in rows])
        if aggregate != expected:
            raise ValueError(f"aggregate mismatch: {arm}")
    unsigned = dict(result)
    expected_hash = unsigned.pop("result_sha256")
    if stable_hash(unsigned) != expected_hash:
        raise ValueError("result hash mismatch")
    return {
        "schema_version": "frankengate-nl2sql-identifier-reranker-verification-v1",
        "cases_verified": len(rows),
        "result_sha256": expected_hash,
        "verification_passed": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.raw, args.result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
