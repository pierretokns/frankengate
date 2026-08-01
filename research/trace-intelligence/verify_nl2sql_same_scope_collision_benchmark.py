#!/usr/bin/env python3
"""Verify the focused same-scope collision benchmark receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from nl2sql_same_scope_collision_benchmark import _aggregate_collision, _metrics, candidate_fingerprint, candidate_key, stable_hash


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(raw_path: Path, result_path: Path, raw_dir: Path) -> dict[str, Any]:
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result["dataset"]["raw_sha256"] != file_sha256(raw_path):
        raise ValueError("raw cohort hash mismatch")
    by_id = {case["case_id"]: case for case in raw["cases"]}
    rows = result["per_case"]
    if len(rows) != result["frontier_calls"]["completed"]:
        raise ValueError("per-case and frontier completion counts differ")
    checked = 0
    for row in rows:
        case = by_id.get(row["case_id"])
        if case is None:
            raise ValueError(f"unknown case {row['case_id']}")
        if row["candidate_fingerprints"] != [candidate_fingerprint(item) for item in case["candidates"]]:
            raise ValueError(f"candidate fingerprints mismatch: {row['case_id']}")
        if row["target_fingerprints"] != [candidate_fingerprint(item) for item in case["target_objects"]]:
            raise ValueError(f"target fingerprints mismatch: {row['case_id']}")
        for arm, order in row["orders"].items():
            if sorted(order) != list(range(len(case["candidates"]))):
                raise ValueError(f"invalid order: {row['case_id']} / {arm}")
            expected = _metrics(case, order)
            if row["metrics"][arm] != expected:
                raise ValueError(f"metric mismatch: {row['case_id']} / {arm}")
        model_path = raw_dir / f"case-{checked:03d}.json"
        model_record = json.loads(model_path.read_text(encoding="utf-8"))
        structured = model_record.get("structured_output")
        if not isinstance(structured, dict):
            raise ValueError(f"missing structured output: {model_path}")
        scores = structured.get("scores", [])
        observed = [index for index, _ in sorted(((int(item["index"]), int(item["relevance"])) for item in scores), key=lambda item: (item[1], -item[0]), reverse=True)]
        if observed != row["orders"]["frontier_scope"]:
            raise ValueError(f"frontier order mismatch: {row['case_id']}")
        if structured.get("decision") != row["frontier_decision"]:
            raise ValueError(f"frontier decision mismatch: {row['case_id']}")
        checked += 1
    for arm, values in result["aggregate"].items():
        expected = _aggregate_collision([row["metrics"][arm] for row in rows])
        if expected != values:
            raise ValueError(f"aggregate mismatch: {arm}")
    unsigned = dict(result)
    expected_hash = unsigned.pop("result_sha256")
    if stable_hash(unsigned) != expected_hash:
        raise ValueError("result hash mismatch")
    return {"status": "verified", "cases": checked, "raw_sha256": file_sha256(raw_path), "result_sha256": expected_hash}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.raw, args.result, args.raw_dir), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
