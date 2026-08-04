#!/usr/bin/env python3
"""Offline outcome-conditioned procedure retrieval over pinned MATM traces.

This is a predictive transfer study, not an agent intervention. It asks
whether successful public trajectories can identify useful nearby procedures
for an unseen model, using only information available before the held-out
outcome. Raw goals, actions, task IDs, and trajectories stay outside Git.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from matm_pilot import (
    DATASET_ID,
    DATASET_REVISION,
    SOURCE_FILE,
    SOURCE_SHA256,
    sha256_file,
)


SCHEMA_VERSION = "frankengate-matm-trace-skill-retrieval.v1"
STOPWORDS = frozenset(
    "a an and are at by for from in into of on or the to with you".split()
)


def _stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_value(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _tokens(value: str) -> frozenset[str]:
    return frozenset(
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if token not in STOPWORDS and len(token) > 1
    )


def _action_template(value: str) -> str:
    value = value.lower()
    value = re.sub(r"\b\d+\b", "N", value)
    value = re.sub(r"\b(?:the|a|an)\b", "", value)
    return " ".join(value.split())


def _row_features(row: Mapping[str, Any]) -> tuple[frozenset[str], frozenset[str]]:
    goal = _tokens(str(row.get("goal", "")))
    try:
        trajectory = json.loads(str(row.get("trajectory", "[]")))
    except json.JSONDecodeError:
        trajectory = []
    actions = tuple(
        _action_template(str(step.get("action", "")))
        for step in trajectory
        if isinstance(step, Mapping) and step.get("action")
    )
    return goal, frozenset(actions[:12])


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def _similarity(
    query: tuple[frozenset[str], frozenset[str]],
    candidate: tuple[frozenset[str], frozenset[str]],
) -> float:
    goal, actions = query
    candidate_goal, candidate_actions = candidate
    return 0.75 * _jaccard(goal, candidate_goal) + 0.25 * _jaccard(
        actions, candidate_actions
    )


def _auc(scores: Sequence[float], labels: Sequence[bool]) -> float | None:
    positives = [score for score, label in zip(scores, labels) if label]
    negatives = [score for score, label in zip(scores, labels) if not label]
    if not positives or not negatives:
        return None
    wins = sum(
        1.0 if positive > negative else 0.5 if positive == negative else 0.0
        for positive in positives
        for negative in negatives
    )
    return wins / (len(positives) * len(negatives))


def _brier(scores: Sequence[float], labels: Sequence[bool]) -> float:
    return sum((score - float(label)) ** 2 for score, label in zip(scores, labels)) / len(labels)


def _metrics(scores: Sequence[float], labels: Sequence[bool]) -> dict[str, Any]:
    if not labels:
        raise ValueError("empty evaluation slice")
    order = sorted(range(len(scores)), key=lambda index: (scores[index], -index), reverse=True)
    top_n = max(1, math.ceil(len(order) * 0.10))
    top = [labels[index] for index in order[:top_n]]
    threshold = 0.5
    predicted = [score >= threshold for score in scores]
    return {
        "n": len(labels),
        "successes": sum(labels),
        "success_rate": sum(labels) / len(labels),
        "auc": _auc(scores, labels),
        "brier": _brier(scores, labels),
        "accuracy_at_0_5": sum(predicted[index] == labels[index] for index in range(len(labels))) / len(labels),
        "top_10_percent_n": top_n,
        "top_10_percent_success_rate": sum(top) / len(top),
    }


def _bootstrap_ci(values: Sequence[float], *, seed: int = 20260802) -> list[float]:
    if not values:
        return [0.0, 0.0]
    rng = random.Random(seed)
    samples = []
    for _ in range(4000):
        draw = [values[rng.randrange(len(values))] for _ in values]
        samples.append(sum(draw) / len(draw))
    samples.sort()
    return [samples[80], samples[3920]]


def _load_rows(path: Path) -> list[dict[str, Any]]:
    try:
        import pyarrow.parquet as parquet
    except ImportError as exc:  # pragma: no cover - environment gate
        raise RuntimeError("pyarrow is required for the MATM retrieval study") from exc
    rows = parquet.read_table(path).to_pylist()
    if len(rows) != 2130:
        raise ValueError(f"unexpected MATM row count: {len(rows)}")
    return [dict(row) for row in rows]


def _model_fold(rows: Sequence[Mapping[str, Any]], held_out_model: str, k: int) -> dict[str, Any]:
    train = [row for row in rows if row.get("model") != held_out_model]
    test = [row for row in rows if row.get("model") == held_out_model]
    if not train or not test:
        raise ValueError("model fold is empty")
    train_features = [_row_features(row) for row in train]
    train_successes = [bool(row.get("success")) for row in train]
    global_prior = sum(train_successes) / len(train_successes)
    by_task_type: dict[str, list[bool]] = {}
    for row in train:
        by_task_type.setdefault(str(row.get("task_type", "")), []).append(bool(row.get("success")))
    all_scores: list[float] = []
    success_scores: list[float] = []
    task_scores: list[float] = []
    labels: list[bool] = []
    for row in test:
        query_features = _row_features(row)
        ranked = sorted(
            (
                _similarity(query_features, candidate),
                index,
            )
            for index, candidate in enumerate(train_features)
        )[-k:]
        neighbor_indices = [index for _, index in reversed(ranked)]
        all_scores.append(sum(train_successes[index] for index in neighbor_indices) / len(neighbor_indices))
        successful_ranked = [
            (score, index)
            for score, index in sorted(
                (
                    _similarity(query_features, candidate),
                    index,
                )
                for index, candidate in enumerate(train_features)
                if train_successes[index]
            )[-k:]
        ]
        success_scores.append(
            sum(score for score, _ in reversed(successful_ranked))
            / len(successful_ranked)
            if successful_ranked
            else 0.0
        )
        task_history = by_task_type.get(str(row.get("task_type", "")), [])
        task_scores.append(sum(task_history) / len(task_history) if task_history else global_prior)
        labels.append(bool(row.get("success")))
    return {
        "held_out_model": held_out_model,
        "train_rows": len(train),
        "test_rows": len(test),
        "train_success_rate": global_prior,
        "all_trace_neighbor": _metrics(all_scores, labels),
        "successful_trace_neighbor": _metrics(success_scores, labels),
        "task_type_prior": _metrics(task_scores, labels),
    }


def run(path: Path, *, k: int = 8) -> dict[str, Any]:
    observed_sha = sha256_file(path)
    if observed_sha != SOURCE_SHA256:
        raise ValueError("MATM source hash does not match the pinned manifest")
    rows = _load_rows(path)
    models = sorted({str(row.get("model")) for row in rows})
    folds = [_model_fold(rows, model, k) for model in models]
    aggregate: dict[str, dict[str, float]] = {}
    for method in ("all_trace_neighbor", "successful_trace_neighbor", "task_type_prior"):
        aggregate[method] = {
            metric: sum(float(fold[method][metric]) for fold in folds if fold[method][metric] is not None) / sum(fold[method][metric] is not None for fold in folds)
            for metric in ("auc", "brier", "accuracy_at_0_5", "top_10_percent_success_rate")
        }
    top10_deltas = [
        fold["successful_trace_neighbor"]["top_10_percent_success_rate"]
        - fold["all_trace_neighbor"]["top_10_percent_success_rate"]
        for fold in folds
    ]
    auc_deltas = [
        fold["successful_trace_neighbor"]["auc"]
        - fold["all_trace_neighbor"]["auc"]
        for fold in folds
        if fold["successful_trace_neighbor"]["auc"] is not None
        and fold["all_trace_neighbor"]["auc"] is not None
    ]
    aggregate["contrast"] = {
        "successful_minus_all_top_10_percent_success_rate_mean": sum(top10_deltas) / len(top10_deltas),
        "successful_minus_all_top_10_percent_success_rate_ci95": _bootstrap_ci(top10_deltas),
        "successful_minus_all_auc_mean": sum(auc_deltas) / len(auc_deltas),
        "successful_minus_all_auc_ci95": _bootstrap_ci(auc_deltas, seed=20260803),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "study": "outcome_conditioned_trace_procedure_retrieval",
        "dataset": {
            "id": DATASET_ID,
            "revision": DATASET_REVISION,
            "source_file": SOURCE_FILE,
            "source_sha256": observed_sha,
            "rows": len(rows),
            "models": len(models),
        },
        "protocol": {
            "split": "leave-one-model-out",
            "held_out_models": len(models),
            "neighbor_k": k,
            "goal_and_action_features_only": True,
            "outcome_used_for_candidate_training": True,
            "raw_content_committed": False,
        },
        "aggregate": aggregate,
        "folds": folds,
        "claim_boundary": {
            "offline_predictive_transfer_measured": True,
            "causal_skill_benefit_confirmed": False,
            "agent_intervention_executed": False,
            "automatic_promotion_authorized": False,
            "reason": "Success labels evaluate recommendation quality across held-out models; no model was rerun with the retrieved procedure.",
        },
        "result_sha256": _sha256_value({"dataset": observed_sha, "folds": folds, "aggregate": aggregate}),
    }


def render(result: Mapping[str, Any]) -> str:
    aggregate = result["aggregate"]
    lines = [
        "# MATM outcome-conditioned trace procedure retrieval",
        "",
        "This is an offline leave-one-model-out recommendation study over the pinned MATM ALFWorld shard. It does not rerun an agent or claim causal skill improvement.",
        "",
        f"- Dataset rows: {result['dataset']['rows']}; held-out model folds: {result['protocol']['held_out_models']}; k={result['protocol']['neighbor_k']}.",
        "- Features: goal tokens and normalized action templates; task outcomes are never available to the held-out query, only to training candidates.",
        "",
        "| Method | mean AUC | mean Brier | mean accuracy | top-10% success rate |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    labels = {
        "all_trace_neighbor": "all-trace neighbor",
        "successful_trace_neighbor": "outcome-conditioned successful neighbor",
        "task_type_prior": "task-type prior",
    }
    for method, label in labels.items():
        row = aggregate[method]
        lines.append(
            f"| {label} | {row['auc']:.3f} | {row['brier']:.3f} | {row['accuracy_at_0_5']:.3f} | {row['top_10_percent_success_rate']:.3f} |"
        )
    lines.extend(
        [
            "",
            f"The successful-neighbor recommendation precision lift over the all-trace neighbor at the top 10% cutoff was {aggregate['contrast']['successful_minus_all_top_10_percent_success_rate_mean']:.3f} (bootstrap 95% CI {aggregate['contrast']['successful_minus_all_top_10_percent_success_rate_ci95'][0]:.3f} to {aggregate['contrast']['successful_minus_all_top_10_percent_success_rate_ci95'][1]:.3f}); its mean AUC contrast was {aggregate['contrast']['successful_minus_all_auc_mean']:.3f} (95% CI {aggregate['contrast']['successful_minus_all_auc_ci95'][0]:.3f} to {aggregate['contrast']['successful_minus_all_auc_ci95'][1]:.3f}). These are recommendation metrics, not changed-agent outcomes.",
            "The successful-neighbor arm tests whether outcome-conditioned traces identify a useful procedure candidate for an unseen model. A positive predictive result is not an intervention effect: the agent was not rerun with the candidate, and no skill is releasable from this study.",
            "",
            f"Machine-readable receipt: `experiments/results/matm-trace-skill-retrieval-2026-08-02.json`.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--neighbor-k", type=int, default=8)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    args = parser.parse_args()
    if args.neighbor_k < 1:
        raise SystemExit("--neighbor-k must be positive")
    result = run(args.input, k=args.neighbor_k)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.summary.write_text(render(result), encoding="utf-8")
    print(json.dumps({"result_sha256": result["result_sha256"], "rows": result["dataset"]["rows"], "folds": result["protocol"]["held_out_models"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
