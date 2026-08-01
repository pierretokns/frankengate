#!/usr/bin/env python3
"""Build a paired receipt from matched upstream RHO ``rho grade`` outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-rho-matched-grade-receipt-v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _grades(path: Path) -> dict[str, float]:
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{path}: expected non-empty grade list")
    output: dict[str, float] = {}
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("task_id"), str):
            raise ValueError(f"{path}: grade task_id missing")
        score = row.get("score")
        if not isinstance(score, (int, float)) or isinstance(score, bool):
            raise ValueError(f"{path}: numeric score missing")
        if row["task_id"] in output:
            raise ValueError(f"{path}: duplicate task id")
        output[row["task_id"]] = float(score)
    return output


def _bootstrap(deltas: list[float], seed: int = 20260802, samples: int = 20_000) -> list[float]:
    rng = random.Random(seed)
    means = sorted(
        statistics.mean(deltas[rng.randrange(len(deltas))] for _ in deltas)
        for _ in range(samples)
    )
    return [means[int(0.025 * (samples - 1))], means[int(0.975 * (samples - 1))]]


def _sign_pvalue(deltas: list[float]) -> float:
    nonzero = [delta for delta in deltas if delta]
    if not nonzero:
        return 1.0
    wins = sum(delta > 0 for delta in nonzero)
    n = len(nonzero)
    tail = min(wins, n - wins)
    return min(1.0, 2 * sum(math.comb(n, k) for k in range(tail + 1)) / (2**n))


def build_receipt(
    candidate_grades: Path,
    baseline_grades: Path,
    candidate_run: Path,
    baseline_run: Path,
    dataset: Path,
    upstream_commit: str,
) -> dict[str, Any]:
    candidate = _grades(candidate_grades)
    baseline = _grades(baseline_grades)
    if set(candidate) != set(baseline):
        raise ValueError("candidate and baseline grade task sets differ")
    candidate_summary = json.loads((candidate_run / "reports/summary.json").read_text())
    baseline_summary = json.loads((baseline_run / "reports/summary.json").read_text())
    if candidate_summary.get("initial_harness_id") != baseline_summary.get("initial_harness_id"):
        raise ValueError("candidate and baseline initial harnesses differ")
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
    mean_delta = statistics.mean(deltas)
    sd = statistics.stdev(deltas) if len(deltas) > 1 else 0.0
    required = math.ceil(((1.96 + 0.84) * sd / abs(mean_delta)) ** 2) if sd and mean_delta else None
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": "rho-frontier-locomo-matched-grade-replay",
        "source": {
            "upstream_repository": "wbopan/retro-harness",
            "upstream_commit": upstream_commit,
            "dataset_sha256": sha256(dataset),
            "candidate_grades_sha256": sha256(candidate_grades),
            "baseline_grades_sha256": sha256(baseline_grades),
            "candidate_summary_sha256": sha256(candidate_run / "reports/summary.json"),
            "baseline_summary_sha256": sha256(baseline_run / "reports/summary.json"),
        },
        "protocol": {
            "dataset": "LOCOMO locomo10.json",
            "heldout_tasks": len(rows),
            "model": "gpt-5.6-luna",
            "reasoning_effort": "high",
            "candidate_harness_id": candidate_summary.get("final_harness_id"),
            "baseline_harness_id": baseline_summary.get("final_harness_id"),
            "matched_initial_harness_id": candidate_summary.get("initial_harness_id"),
            "candidate_upstream_acceptance": [
                bool(item.get("accepted")) for item in candidate_summary.get("rounds", [])
            ],
            "independent_heldout_grader": "upstream LOCOMO score_qa via rho grade",
        },
        "outcome": {
            "baseline_mean_score": statistics.mean(baseline.values()),
            "candidate_mean_score": statistics.mean(candidate.values()),
            "mean_delta": mean_delta,
            "paired_delta_sample_sd": sd,
            "candidate_better_tasks": sum(delta > 0 for delta in deltas),
            "candidate_regressed_tasks": sum(delta < 0 for delta in deltas),
            "candidate_tied_tasks": sum(delta == 0 for delta in deltas),
            "bootstrap_mean_delta_95ci": _bootstrap(deltas),
            "exact_two_sided_sign_pvalue": _sign_pvalue(deltas),
            "estimated_pairs_for_80pct_normal_power": required,
            "paired_rows": rows,
        },
        "claim_boundary": {
            "matched_initial_harness_control": True,
            "independent_heldout_replay": True,
            "candidate_accessed_heldout_gold": False,
            "causal_rho_utility_confirmed": False,
            "automatic_frankengate_promotion_authorized": False,
            "reason": "This is a larger matched grade replay; it remains descriptive until the preregistered cohort, repeated seeds, cost budget, and independent causal utility gate are complete.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-grades", type=Path, required=True)
    parser.add_argument("--baseline-grades", type=Path, required=True)
    parser.add_argument("--candidate-run", type=Path, required=True)
    parser.add_argument("--baseline-run", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--upstream-commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = build_receipt(
        args.candidate_grades, args.baseline_grades, args.candidate_run,
        args.baseline_run, args.dataset, args.upstream_commit,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt["outcome"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
