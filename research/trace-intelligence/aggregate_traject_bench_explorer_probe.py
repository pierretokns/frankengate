#!/usr/bin/env python3
"""Aggregate repeated separate-explorer receipts without pooling raw text."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-traject-bench-explorer-probe-aggregate-v1"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def selected_indices(raw_dir: Path, index: int) -> set[int]:
    raw = json.loads((raw_dir / f"case-{index:03d}.json").read_text(encoding="utf-8"))
    value = raw.get("structured_output")
    if not isinstance(value, dict) or not isinstance(value.get("selected_indices"), list):
        raise ValueError(f"missing explorer output for case {index}")
    return {int(item) for item in value["selected_indices"]}


def run(result_paths: list[Path], raw_dirs: list[Path], output: Path) -> dict[str, Any]:
    if len(result_paths) != 2 or len(raw_dirs) != 2:
        raise ValueError("the aggregate requires exactly two runs")
    results = [json.loads(path.read_text(encoding="utf-8")) for path in result_paths]
    if any(result.get("failures") != 0 for result in results):
        raise ValueError("cannot aggregate incomplete runs")
    row_counts = [len(result.get("rows", [])) for result in results]
    if row_counts != [8, 8]:
        raise ValueError("the aggregate requires two complete eight-case runs")
    for result in results:
        if result.get("schema_version") != "frankengate-traject-bench-explorer-probe-v1":
            raise ValueError("unexpected component schema")
    overlaps: list[float] = []
    exact = 0
    for index in range(8):
        left = selected_indices(raw_dirs[0], index)
        right = selected_indices(raw_dirs[1], index)
        union = left | right
        overlaps.append(len(left & right) / len(union) if union else 1.0)
        exact += int(left == right)
    explorer_arms = [result["arms"]["explorer"] for result in results]
    aggregate = {
        "candidate_coverage": round(sum(float(arm["candidate_coverage"]) for arm in explorer_arms) / 2, 6),
        "mrr": round(sum(float(arm["mrr"]) for arm in explorer_arms) / 2, 6),
        "recall_at_1": round(sum(float(arm["recall_at_1"]) for arm in explorer_arms) / 2, 6),
        "recall_at_5": round(sum(float(arm["recall_at_5"]) for arm in explorer_arms) / 2, 6),
        "recall_at_10": round(sum(float(arm["recall_at_10"]) for arm in explorer_arms) / 2, 6),
        "selected_count": round(sum(float(arm["selected_count"]) for arm in explorer_arms) / 2, 6),
    }
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source": {"result_sha256": [file_hash(path) for path in result_paths], "raw_content_committed": False},
        "runs": 2,
        "cases_per_run": 8,
        "explorer_mean": aggregate,
        "stability": {"selected_set_jaccard_mean": round(sum(overlaps) / len(overlaps), 6), "exact_selected_set_agreements": exact, "case_jaccards": [round(value, 6) for value in overlaps]},
        "lexical_control": results[0]["arms"]["lexical_name"],
        "claim_boundary": {"repeated_explorer_measured": True, "validated_artifact_utility_measured": False, "enterprise_skill_transfer_measured": False, "reason": "Repeated public tool-selection proxy; no tool endpoints, authority, principal, changed-system replay, or enterprise utility labels."},
    }
    result["result_sha256"] = stable_hash(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"explorer_mean": aggregate, "stability": result["stability"]}, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", action="append", type=Path, required=True)
    parser.add_argument("--raw-dir", action="append", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.result, args.raw_dir, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
