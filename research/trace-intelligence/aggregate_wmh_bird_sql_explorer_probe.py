#!/usr/bin/env python3
"""Aggregate two independent WMH-BIRD SQL explorer receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-wmh-bird-sql-explorer-probe-aggregate-v1"


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
        raise ValueError(f"missing SQL explorer output for case {index}")
    return {int(item) for item in value["selected_indices"]}


def mean(rows: list[dict[str, Any]], key: str) -> float:
    return round(sum(float(row[key]) for row in rows) / len(rows), 6) if rows else 0.0


def run(result_paths: list[Path], raw_dirs: list[Path], output: Path) -> dict[str, Any]:
    if len(result_paths) != 2 or len(raw_dirs) != 2:
        raise ValueError("exactly two runs are required")
    results = [json.loads(path.read_text(encoding="utf-8")) for path in result_paths]
    if any(result.get("schema_version") != "frankengate-wmh-bird-sql-explorer-probe-v1" for result in results):
        raise ValueError("unexpected component schema")
    if any(result.get("failures") != 0 or len(result.get("rows", [])) != 8 for result in results):
        raise ValueError("incomplete component run")
    first_ids = [(row["db_name"], row["trace_hash"]) for row in results[0]["rows"]]
    second_ids = [(row["db_name"], row["trace_hash"]) for row in results[1]["rows"]]
    if first_ids != second_ids:
        raise ValueError("component runs selected different cases")
    overlaps: list[float] = []
    exact = 0
    for index in range(8):
        left = selected_indices(raw_dirs[0], index)
        right = selected_indices(raw_dirs[1], index)
        union = left | right
        overlaps.append(len(left & right) / len(union) if union else 1.0)
        exact += int(left == right)
    explorer = [result["arms"]["explorer"] for result in results]
    lexical = results[0]["arms"]["lexical"]
    keys = (
        "strict_mrr", "strict_recall_at_1", "strict_recall_at_5", "strict_recall_at_10",
        "compatible_mrr", "compatible_recall_at_1", "compatible_recall_at_5", "compatible_recall_at_10",
        "compatible_selected_rate", "invalid_selected_count", "selected_count",
    )
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source": {"result_sha256": [file_hash(path) for path in result_paths], "raw_content_committed": False},
        "runs": 2,
        "cases_per_run": 8,
        "explorer_mean": {key: mean(explorer, key) for key in keys},
        "lexical_control": lexical,
        "stability": {"selected_set_jaccard_mean": round(sum(overlaps) / len(overlaps), 6), "exact_selected_set_agreements": exact, "case_jaccards": [round(value, 6) for value in overlaps]},
        "claim_boundary": {"repeated_sql_explorer_measured": True, "replay_compatibility_measured": True, "semantic_alias_quality_established": False, "validated_artifact_utility_established": False, "enterprise_skill_transfer_measured": False, "reason": "Two repeated public WMH-BIRD cases with independent SQLite compatibility labels; no enterprise authorization, human intent, or changed-system outcome labels."},
    }
    result["result_sha256"] = stable_hash(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"explorer_mean": result["explorer_mean"], "stability": result["stability"]}, sort_keys=True))
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
