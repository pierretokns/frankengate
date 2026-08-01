#!/usr/bin/env python3
"""Create a privacy-minimized receipt for the Codex-adapted ReasoningBank run."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-reasoningbank-codex-frontier-reproduction-v1"


def read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--baseline-receipt", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--upstream-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    summary_path = args.run_dir / "reports" / "summary.json"
    eval_path = args.run_dir / "reports" / "final_val_grades.json"
    memory_path = args.run_dir / "reasoningbank" / "memory.jsonl"
    summary = read(summary_path)
    baseline = read(args.baseline_receipt)
    eval_rows = read(eval_path)
    eval_ids = {row["task_id"] for row in eval_rows}
    baseline_ids = set(baseline["protocol"]["heldout_task_ids"])
    if eval_ids != baseline_ids:
        raise ValueError(f"held-out task mismatch: {sorted(eval_ids ^ baseline_ids)}")
    candidate_mean = float(summary["eval"]["mean_score"])
    baseline_mean = float(baseline["outcome"]["baseline_mean_score"])
    result = {
        "schema_version": SCHEMA_VERSION,
        "experiment": "reasoningbank-locomo-codex-frontier-bounded",
        "source": {
            "upstream_repository": "wbopan/retro-harness",
            "upstream_commit": args.upstream_commit,
            "dataset_sha256": sha256(args.dataset),
            "run_summary_sha256": sha256(summary_path),
            "eval_grades_sha256": sha256(eval_path),
            "memory_store_sha256": sha256(memory_path),
            "baseline_receipt_sha256": sha256(args.baseline_receipt),
        },
        "protocol": {
            "dataset": "LOCOMO locomo10.json",
            "model": "gpt-5.6-luna",
            "memory_judge": "Codex subscription adapter",
            "embedding_provider": "local FastEmbed ONNX",
            "embedding_model": "BAAI/bge-small-en-v1.5",
            "embedding_dimensions": 384,
            "eval_variant": "frozen",
            "train_tasks": 2,
            "heldout_tasks": 2,
            "heldout_task_ids": sorted(eval_ids),
            "memory_entries": int(summary["memory_entry_count"]),
            "memory_judge_calls": 4,
            "memory_extraction_calls": 4,
        },
        "outcome": {
            "baseline_mean_score": baseline_mean,
            "reasoningbank_mean_score": candidate_mean,
            "mean_delta": candidate_mean - baseline_mean,
            "candidate_regressed_tasks": sum(
                float(row["score"]) < next(
                    item["baseline_score"]
                    for item in baseline["outcome"]["task_rows"]
                    if item["task_id"] == row["task_id"]
                )
                for row in eval_rows
            ),
            "candidate_tied_tasks": sum(
                float(row["score"]) == next(
                    item["baseline_score"]
                    for item in baseline["outcome"]["task_rows"]
                    if item["task_id"] == row["task_id"]
                )
                for row in eval_rows
            ),
            "task_scores": [
                {"task_id": row["task_id"], "score": float(row["score"])}
                for row in eval_rows
            ],
        },
        "claim_boundary": {
            "upstream_runner_unchanged": True,
            "independent_heldout_replay": True,
            "matched_no_harness_control": True,
            "codex_provider_substitution_explicit": True,
            "causal_memory_utility_confirmed": False,
            "automatic_frankengate_promotion_authorized": False,
            "reason": (
                "The Codex-adapted ReasoningBank arm scored below the matched "
                "no-harness control on this two-task slice. This is a bounded "
                "negative result under explicit provider substitutions, not a "
                "universal claim about ReasoningBank."
            ),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["outcome"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
