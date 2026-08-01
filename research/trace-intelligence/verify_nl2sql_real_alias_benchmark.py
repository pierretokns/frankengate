#!/usr/bin/env python3
"""Independently verify a content-free real NL2SQL retrieval receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from nl2sql_real_alias_benchmark import _aggregate, _case_metrics, candidate_fingerprint, candidate_key, stable_hash


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(raw_path: Path, result_path: Path, raw_dir: Path) -> dict[str, Any]:
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result["dataset"]["raw_sha256"] != file_sha256(raw_path):
        raise ValueError("raw cohort hash mismatch")
    by_id = {case["case_id"]: case for case in raw["cases"]}
    rows = result.get("per_case", [])
    if len(rows) != result["frontier_calls"]["completed"]:
        raise ValueError("per-case count does not match frontier completion count")
    checked = 0
    for row in rows:
        case = by_id.get(row["case_id"])
        if case is None:
            raise ValueError(f"unknown case: {row['case_id']}")
        expected_candidates = [candidate_fingerprint(candidate) for candidate in case["candidates"]]
        if row["candidate_fingerprints"] != expected_candidates:
            raise ValueError(f"candidate fingerprints mismatch: {row['case_id']}")
        expected_targets = [candidate_fingerprint(candidate) for candidate in case.get("target_objects", [])]
        if row["target_fingerprints"] != expected_targets:
            raise ValueError(f"target fingerprints mismatch: {row['case_id']}")
        for arm, order in row["orders"].items():
            if sorted(order) != list(range(len(case["candidates"]))):
                raise ValueError(f"invalid order for {row['case_id']} / {arm}")
            expected_metrics = _case_metrics(case, order)
            observed_metrics = row["metrics"][arm]
            # Older receipts include the diagnostic `top1_is_any_candidate`
            # field; the benchmark's canonical metric helper intentionally
            # omits that convenience field.  Verify every canonical metric
            # while allowing additive receipt fields for compatibility.
            if any(observed_metrics.get(key) != value for key, value in expected_metrics.items()):
                raise ValueError(f"metric mismatch for {row['case_id']} / {arm}")
        raw_model_path = raw_dir / f"case-{checked:03d}.json"
        if not raw_model_path.exists():
            raise ValueError(f"missing raw model receipt: {raw_model_path}")
        raw_model = json.loads(raw_model_path.read_text(encoding="utf-8"))
        structured = raw_model.get("structured_output")
        if structured is None:
            # Codex runner receipts keep the model's JSON on stdout and
            # reserve the wrapper object for process metadata.
            stdout = raw_model.get("stdout", "")
            try:
                structured = json.loads(stdout.strip().splitlines()[0])
            except (json.JSONDecodeError, IndexError, AttributeError) as exc:
                raise ValueError(f"invalid structured stdout: {raw_model_path}") from exc
        if not isinstance(structured, dict):
            raise ValueError(f"missing structured output: {raw_model_path}")
        scores = structured.get("scores", [])
        observed_order = [index for index, _ in sorted(((int(item["index"]), int(item["relevance"])) for item in scores), key=lambda item: (item[1], -item[0]), reverse=True)]
        if observed_order != row["orders"]["frontier_scope"]:
            raise ValueError(f"frontier order mismatch: {row['case_id']}")
        if structured.get("decision") != row["frontier_decision"]:
            raise ValueError(f"frontier decision mismatch: {row['case_id']}")
        checked += 1
    for arm, values in result["aggregate"].items():
        recomputed = _aggregate([row["metrics"][arm] for row in rows])
        if any(values.get(key) != value for key, value in recomputed.items()):
            raise ValueError(f"aggregate mismatch: {arm}")
    decision_rows = result["frontier_decision"]
    accuracy = sum(row["frontier_decision_correct"] for row in rows) / len(rows)
    targeted = [row for row in rows if row["category"] != "scope_swapped_nil"]
    nil = [row for row in rows if row["category"] == "scope_swapped_nil"]
    expected_decision = {
        "accuracy": round(accuracy, 6),
        "targeted_retrieve_rate": round(sum(row["frontier_decision"] == "retrieve" for row in targeted) / max(1, len(targeted)), 6),
        "nil_abstention_rate": round(sum(row["frontier_decision"] == "abstain" for row in nil) / max(1, len(nil)), 6),
    }
    if decision_rows != expected_decision:
        raise ValueError("frontier decision aggregate mismatch")
    unsigned = dict(result)
    expected_hash = unsigned.pop("result_sha256")
    if stable_hash(unsigned) != expected_hash:
        raise ValueError("result hash mismatch")
    return {"status": "verified", "cases": checked, "result_sha256": expected_hash, "raw_sha256": file_sha256(raw_path)}


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
