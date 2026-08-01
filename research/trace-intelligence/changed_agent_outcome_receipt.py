#!/usr/bin/env python3
"""Independently recompute a trace-derived procedure's future-task outcome.

The source BIRD factorial already sealed task hashes, exact execution outcomes,
and per-call latency.  This adapter recomputes paired arm metrics from that
receipt without reading prompts, SQL, or model responses.  It is evidence that
an independently evaluated changed agent was measured—not evidence of a
general skill benefit or enterprise transfer.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-changed-agent-outcome-receipt-v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bootstrap(deltas: list[float], seed: int = 20260802, samples: int = 20_000) -> list[float]:
    if not deltas:
        return [0.0, 0.0]
    rng = random.Random(seed)
    means = sorted(
        statistics.mean(deltas[rng.randrange(len(deltas))] for _ in deltas)
        for _ in range(samples)
    )
    return [means[int(0.025 * (samples - 1))], means[int(0.975 * (samples - 1))]]


def sign_pvalue(deltas: list[float]) -> float:
    nonzero = [delta for delta in deltas if delta]
    if not nonzero:
        return 1.0
    wins = sum(delta > 0 for delta in nonzero)
    n = len(nonzero)
    smaller = min(wins, n - wins)
    return min(1.0, 2.0 * sum(math.comb(n, k) for k in range(smaller + 1)) / (2**n))


def _paired(episodes: list[dict[str, Any]], candidate: str, control: str) -> list[dict[str, Any]]:
    by_task: dict[str, dict[str, dict[str, Any]]] = {}
    for row in episodes:
        if not isinstance(row, dict) or row.get("arm") not in {candidate, control}:
            continue
        task = row.get("task_hash")
        if not isinstance(task, str):
            raise ValueError("episode task_hash is required")
        by_task.setdefault(task, {})[str(row["arm"])] = row
    rows: list[dict[str, Any]] = []
    for task, arms in sorted(by_task.items()):
        if candidate not in arms or control not in arms:
            continue
        left, right = arms[candidate], arms[control]
        candidate_score = 1.0 if left.get("exact") is True else 0.0
        control_score = 1.0 if right.get("exact") is True else 0.0
        rows.append({
            "task_hash": task,
            "candidate_score": candidate_score,
            "control_score": control_score,
            "delta": candidate_score - control_score,
            "candidate_elapsed_ms": float(left["elapsed_ms"]),
            "control_elapsed_ms": float(right["elapsed_ms"]),
        })
    if not rows:
        raise ValueError(f"no paired rows for {candidate!r} vs {control!r}")
    return rows


def _effect(rows: list[dict[str, Any]]) -> dict[str, Any]:
    deltas = [row["delta"] for row in rows]
    sd = statistics.stdev(deltas) if len(deltas) > 1 else 0.0
    mean_delta = statistics.mean(deltas)
    required = (
        math.ceil(((1.96 + 0.84) * sd / abs(mean_delta)) ** 2)
        if mean_delta and sd
        else None
    )
    return {
        "pairs": len(rows),
        "candidate_wins": sum(delta > 0 for delta in deltas),
        "candidate_losses": sum(delta < 0 for delta in deltas),
        "ties": sum(delta == 0 for delta in deltas),
        "mean_delta": mean_delta,
        "paired_sd": sd,
        "bootstrap_95ci": bootstrap(deltas),
        "exact_two_sided_sign_pvalue": sign_pvalue(deltas),
        "estimated_pairs_for_80pct_normal_power": required,
    }


def build_receipt(result_path: Path, verifier_path: Path) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    verifier = json.loads(verifier_path.read_text(encoding="utf-8"))
    if not verifier.get("claim_boundary", {}).get("verification_passed"):
        raise ValueError("independent verifier did not pass")
    episodes = result.get("episodes")
    if not isinstance(episodes, list) or not episodes:
        raise ValueError("sealed factorial episodes are required")
    protocol = result.get("protocol", {})
    candidate = "trace_mined_procedure"
    control = "no_skill"
    rows = _paired(episodes, candidate, control)
    candidate_rows = [row for row in episodes if row.get("arm") == candidate]
    control_rows = [row for row in episodes if row.get("arm") == control]
    candidate_latency = statistics.mean(float(row["elapsed_ms"]) for row in candidate_rows)
    control_latency = statistics.mean(float(row["elapsed_ms"]) for row in control_rows)
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment": "bird-sql-trace-derived-procedure-changed-agent",
        "source": {
            "factorial_receipt": result_path.name,
            "factorial_receipt_sha256": sha256(result_path),
            "independent_verifier": verifier_path.name,
            "independent_verifier_sha256": sha256(verifier_path),
            "raw_model_content_committed": False,
        },
        "protocol": {
            "dataset": protocol.get("heldout_families"),
            "family_disjoint": True,
            "heldout_task_count": len(rows),
            "candidate_arm": candidate,
            "control_arm": control,
            "model": protocol.get("model"),
            "harness": protocol.get("harness"),
            "gold_hidden_from_proposer": protocol.get("gold_hidden_from_proposer"),
            "independent_evaluator": verifier.get("independent_evaluator"),
        },
        "outcome": {
            "exact_execution": _effect(rows),
            "candidate_mean_elapsed_ms": candidate_latency,
            "control_mean_elapsed_ms": control_latency,
            "latency_delta_ms": candidate_latency - control_latency,
            "latency_ratio": candidate_latency / control_latency if control_latency else None,
            "paired_rows": rows,
        },
        "claim_boundary": {
            "changed_agent_future_task_outcome_measured": True,
            "independent_replay_and_evaluator": True,
            "causal_skill_benefit_confirmed": False,
            "cross_user_enterprise_transfer_measured": False,
            "automatic_frankengate_promotion_authorized": False,
            "reason": "This is a family-disjoint changed-agent outcome receipt. The 20-task cohort is descriptive and requires broader powered replication before causal or enterprise claims.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--verifier", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = build_receipt(args.result, args.verifier)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt["outcome"]["exact_execution"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
