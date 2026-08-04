#!/usr/bin/env python3
"""Materialize a privacy-minimized receipt for an independent RHO run.

The RHO run and its matched no-harness validation run stay outside the
repository.  This script records only hashes, task IDs, scalar scores, and
the claim boundary needed to distinguish RHO's self-preference gate from
independent held-out utility.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-rho-frontier-reproduction-v1"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def grades(path: Path) -> list[dict[str, Any]]:
    rows = read_json(path)
    if not isinstance(rows, list):
        raise ValueError(f"{path}: expected a JSON list")
    result: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"{path}: grade row is not an object")
        details = row.get("details")
        if not isinstance(details, dict):
            raise ValueError(f"{path}: grade details are required")
        task_id = row.get("task_id")
        score = row.get("score")
        if not isinstance(task_id, str) or not isinstance(score, (int, float)):
            raise ValueError(f"{path}: task_id and numeric score are required")
        result.append({"task_id": task_id, "score": float(score)})
    return result


def baseline_grades_from_traces(
    run_dir: Path, candidate_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Grade baseline final messages when the upstream CLI omits a report."""
    from rho.datasets.locomo.scoring import extract_answer, score_qa

    # Candidate grade details are passed through a sidecar by the caller; this
    # function only needs task metadata and the baseline trajectory messages.
    task_metadata = {
        row["task_id"]: (row["category"], row["gold"])
        for row in candidate_rows
    }
    result: list[dict[str, Any]] = []
    for meta_path in sorted((run_dir / "trajectories").glob("*/meta.json")):
        meta = read_json(meta_path)
        task_id = meta["task_id"]
        if task_id not in task_metadata:
            continue
        final_message = (meta_path.parent / "final_message.txt").read_text(encoding="utf-8")
        category, gold = task_metadata[task_id]
        result.append(
            {
                "task_id": task_id,
                "score": float(score_qa(extract_answer(final_message), gold, category)),
            }
        )
    if len(result) != len(task_metadata):
        raise ValueError(
            f"{run_dir}: expected {len(task_metadata)} baseline trajectories, got {len(result)}"
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-run", type=Path, required=True)
    parser.add_argument("--baseline-run", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--upstream-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    candidate_summary_path = args.candidate_run / "reports" / "summary.json"
    candidate_grades_path = args.candidate_run / "reports" / "final_val_grades.json"
    baseline_grades_path = args.baseline_run / "reports" / "final_val_grades.json"
    candidate_summary = read_json(candidate_summary_path)
    candidate = grades(candidate_grades_path)
    candidate_grade_rows = read_json(candidate_grades_path)
    if baseline_grades_path.exists():
        baseline = grades(baseline_grades_path)
    else:
        baseline = baseline_grades_from_traces(
            args.baseline_run,
            [
                {
                    "task_id": row["task_id"],
                    "category": row["details"]["category"],
                    "gold": row["details"]["gold"],
                }
                for row in candidate_grade_rows
            ],
        )
    candidate_ids = {row["task_id"] for row in candidate}
    baseline_ids = {row["task_id"] for row in baseline}
    if candidate_ids != baseline_ids:
        raise ValueError(
            "candidate and baseline held-out task sets differ: "
            f"candidate_only={sorted(candidate_ids - baseline_ids)}, "
            f"baseline_only={sorted(baseline_ids - candidate_ids)}"
        )

    candidate_by_id = {row["task_id"]: row["score"] for row in candidate}
    baseline_by_id = {row["task_id"]: row["score"] for row in baseline}
    task_rows = [
        {
            "task_id": task_id,
            "baseline_score": baseline_by_id[task_id],
            "candidate_score": candidate_by_id[task_id],
            "delta": candidate_by_id[task_id] - baseline_by_id[task_id],
        }
        for task_id in sorted(candidate_ids)
    ]
    baseline_mean = sum(row["baseline_score"] for row in task_rows) / len(task_rows)
    candidate_mean = sum(row["candidate_score"] for row in task_rows) / len(task_rows)
    round_info = candidate_summary["rounds"][0]
    output = {
        "schema_version": SCHEMA_VERSION,
        "experiment": "rho-frontier-locomo-bounded",
        "source": {
            "upstream_repository": "wbopan/retro-harness",
            "upstream_commit": args.upstream_commit,
            "dataset_sha256": sha256_file(args.dataset),
            "candidate_summary_sha256": sha256_file(candidate_summary_path),
            "candidate_grades_sha256": sha256_file(candidate_grades_path),
            "baseline_grades_sha256": (
                sha256_file(baseline_grades_path)
                if baseline_grades_path.exists()
                else None
            ),
            "baseline_trajectory_meta_sha256": sorted(
                sha256_file(path)
                for path in (args.baseline_run / "trajectories").glob("*/meta.json")
            ),
        },
        "protocol": {
            "dataset": "LOCOMO locomo10.json",
            "optimizer": "RHO diagnosis strategy",
            "model": "gpt-5.6-luna",
            "reasoning_effort": "high",
            "rounds": 1,
            "optimize_samples": 1,
            "optimize_trajectories_per_task": 3,
            "train_tasks": 2,
            "heldout_tasks": len(task_rows),
            "heldout_task_ids": sorted(candidate_ids),
            "candidate_harness_id": candidate_summary["final_harness_id"],
            "baseline_harness_id": "h_empty",
            "candidate_accepted_by_self_preference": bool(round_info["accepted"]),
            "self_preference_mean_score": float(round_info["mean_score"]),
            "independent_heldout_grader": "upstream LOCOMO score_qa",
        },
        "outcome": {
            "baseline_mean_score": baseline_mean,
            "candidate_mean_score": candidate_mean,
            "mean_delta": candidate_mean - baseline_mean,
            "task_rows": task_rows,
            "candidate_better_tasks": sum(row["delta"] > 0 for row in task_rows),
            "candidate_regressed_tasks": sum(row["delta"] < 0 for row in task_rows),
            "candidate_tied_tasks": sum(row["delta"] == 0 for row in task_rows),
        },
        "claim_boundary": {
            "independent_heldout_replay": True,
            "matched_no_harness_control": True,
            "candidate_accessed_heldout_gold": False,
            "causal_rho_utility_confirmed": False,
            "automatic_frankengate_promotion_authorized": False,
            "reason": (
                "RHO accepted the candidate from self-preference (mean 1.0), "
                "but the matched independent held-out replay regressed on this "
                "two-task slice. The sample is too small for a general efficacy "
                "claim, and the negative delta blocks integration."
            ),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output["outcome"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
