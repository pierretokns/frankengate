#!/usr/bin/env python3
"""Build a paired, independently graded RHO efficacy receipt.

The raw upstream runs stay outside this repository.  This receipt deliberately
keeps task IDs and scalar grades only, then reports paired deltas, a deterministic
sign test, and a bootstrap interval.  It does not turn a small result into a
universal method claim; the integration boundary remains a separate gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-rho-powered-receipt-v1"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def grades(path: Path) -> dict[str, float]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{path}: expected a non-empty grade list")
    result: dict[str, float] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"{path}: grade row must be an object")
        task_id = row.get("task_id")
        score = row.get("score")
        if not isinstance(task_id, str) or not isinstance(score, (int, float)):
            raise ValueError(f"{path}: task_id and numeric score are required")
        if task_id in result:
            raise ValueError(f"{path}: duplicate task {task_id}")
        result[task_id] = float(score)
    return result


def bootstrap_interval(deltas: list[float], *, seed: int, samples: int = 20_000) -> list[float]:
    rng = random.Random(seed)
    means = []
    for _ in range(samples):
        draw = [deltas[rng.randrange(len(deltas))] for _ in deltas]
        means.append(sum(draw) / len(draw))
    means.sort()
    return [means[int(0.025 * (samples - 1))], means[int(0.975 * (samples - 1))]]


def exact_sign_pvalue(deltas: list[float]) -> float:
    nonzero = [delta for delta in deltas if delta != 0]
    if not nonzero:
        return 1.0
    wins = sum(delta > 0 for delta in nonzero)
    n = len(nonzero)
    numerator = sum(__import__("math").comb(n, k) for k in range(0, min(wins, n - wins) + 1))
    return min(1.0, 2.0 * numerator / (2**n))


def build_receipt(candidate_run: Path, baseline_run: Path, *, upstream_commit: str, dataset: Path) -> dict[str, Any]:
    candidate_path = candidate_run / "reports/final_val_grades.json"
    baseline_path = baseline_run / "reports/final_val_grades.json"
    candidate = grades(candidate_path)
    baseline = grades(baseline_path)
    candidate_summary = json.loads((candidate_run / "reports/summary.json").read_text(encoding="utf-8"))
    baseline_summary_path = baseline_run / "reports/summary.json"
    baseline_summary = json.loads(baseline_summary_path.read_text(encoding="utf-8"))
    if candidate_summary.get("initial_harness_id") != baseline_summary.get("initial_harness_id"):
        raise ValueError(
            "candidate and baseline initial harnesses differ: "
            f"candidate={candidate_summary.get('initial_harness_id')!r}, "
            f"baseline={baseline_summary.get('initial_harness_id')!r}"
        )
    if set(candidate) != set(baseline):
        raise ValueError(
            "candidate and baseline held-out task sets differ: "
            f"candidate_only={sorted(set(candidate) - set(baseline))}, "
            f"baseline_only={sorted(set(baseline) - set(candidate))}"
        )
    rows = [
        {
            "task_id": task_id,
            "baseline_score": baseline[task_id],
            "candidate_score": candidate[task_id],
            "delta": candidate[task_id] - baseline[task_id],
        }
        for task_id in sorted(candidate)
    ]
    deltas = [row["delta"] for row in rows]
    baseline_mean = sum(row["baseline_score"] for row in rows) / len(rows)
    candidate_mean = sum(row["candidate_score"] for row in rows) / len(rows)
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": "rho-frontier-locomo-powered",
        "source": {
            "upstream_repository": "wbopan/retro-harness",
            "upstream_commit": upstream_commit,
            "dataset_sha256": sha256_file(dataset),
            "candidate_grades_sha256": sha256_file(candidate_path),
            "baseline_grades_sha256": sha256_file(baseline_path),
            "candidate_summary_sha256": sha256_file(candidate_run / "reports/summary.json"),
            "baseline_summary_sha256": sha256_file(baseline_summary_path),
        },
        "protocol": {
            "dataset": "LOCOMO locomo10.json",
            "model": "gpt-5.6-luna",
            "reasoning_effort": "high",
            "candidate": "one upstream RHO diagnosis round, one optimizer sample",
            "baseline": "upstream empty harness with zero evolution rounds",
            "independent_heldout_grader": "upstream LOCOMO score_qa",
            "heldout_tasks": len(rows),
            "heldout_task_ids": sorted(candidate),
            "candidate_initial_harness_id": candidate_summary.get("initial_harness_id"),
            "candidate_final_harness_id": candidate_summary.get("final_harness_id"),
            "candidate_rounds": len(candidate_summary.get("rounds", [])),
            "candidate_round_accepted": [
                bool(round_info.get("accepted"))
                for round_info in candidate_summary.get("rounds", [])
            ],
            "baseline_initial_harness_id": baseline_summary.get("initial_harness_id"),
            "baseline_final_harness_id": baseline_summary.get("final_harness_id"),
        },
        "outcome": {
            "baseline_mean_score": baseline_mean,
            "candidate_mean_score": candidate_mean,
            "mean_delta": candidate_mean - baseline_mean,
            "candidate_better_tasks": sum(delta > 0 for delta in deltas),
            "candidate_regressed_tasks": sum(delta < 0 for delta in deltas),
            "candidate_tied_tasks": sum(delta == 0 for delta in deltas),
            "paired_rows": rows,
            "bootstrap_mean_delta_95ci": bootstrap_interval(deltas, seed=20260802),
            "exact_two_sided_sign_pvalue": exact_sign_pvalue(deltas),
        },
        "claim_boundary": {
            "matched_no_harness_control": True,
            "independent_heldout_replay": True,
            "candidate_accessed_heldout_gold": False,
            "causal_rho_utility_confirmed": False,
            "automatic_frankengate_promotion_authorized": False,
            "reason": "This receipt strengthens the powered paired estimate; promotion still requires a positive, independently graded outcome and a separate integration replay.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-run", type=Path, required=True)
    parser.add_argument("--baseline-run", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--upstream-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = build_receipt(args.candidate_run, args.baseline_run, upstream_commit=args.upstream_commit, dataset=args.dataset)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output["outcome"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
