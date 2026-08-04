#!/usr/bin/env python3
"""Join same-corpus MATM retrieval receipts without pooling incomparable metrics."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(embedding: Path, outcome: Path) -> dict[str, Any]:
    dense = json.loads(embedding.read_text(encoding="utf-8"))
    model = json.loads(outcome.read_text(encoding="utf-8"))
    dense_dataset = dense.get("dataset", {})
    model_dataset = model.get("dataset", {})
    if dense_dataset.get("revision") != model_dataset.get("revision"):
        raise ValueError("MATM dataset revisions differ")
    dense_actions = dense.get("results", {}).get("actions", {})
    comparisons = {
        item["metric"]: {
            "mean_delta": item["mean_delta"],
            "bootstrap_ci95": item["bootstrap_ci95"],
            "folds": item["folds"],
        }
        for item in dense.get("comparisons", [])
        if item.get("left") == "actions"
        and item.get("right") == "lexical_actions"
    }
    model_aggregate = model.get("aggregate", {})
    model_contrast = model_aggregate.get("contrast", {})
    return {
        "schema_version": "matm-embedding-model-cascade-audit-v1",
        "dataset": {
            "id": dense_dataset.get("id") or model_dataset.get("id"),
            "revision": dense_dataset.get("revision"),
            "rows": dense_dataset.get("rows"),
            "embedding_result_sha256": sha256(embedding),
            "outcome_result_sha256": sha256(outcome),
        },
        "embedding_candidate_recall": {
            "eligible_models": dense_actions.get("eligible_models"),
            "eligible_queries": dense_actions.get("eligible_queries"),
            "action_only_vs_lexical_action_only": comparisons,
        },
        "outcome_conditioned_prioritization": {
            "successful_neighbor_auc": model_aggregate.get("successful_trace_neighbor", {}).get("auc"),
            "all_neighbor_auc": model_aggregate.get("all_trace_neighbor", {}).get("auc"),
            "successful_minus_all_auc": model_contrast.get("successful_minus_all_auc_mean"),
            "successful_minus_all_auc_ci95": model_contrast.get("successful_minus_all_auc_ci95"),
            "successful_minus_all_top10_success_rate": model_contrast.get("successful_minus_all_top_10_percent_success_rate_mean"),
            "successful_minus_all_top10_success_rate_ci95": model_contrast.get("successful_minus_all_top_10_percent_success_rate_ci95"),
        },
        "decision": {
            "embedding_role": "candidate_generation",
            "outcome_model_role": "review_prioritization_only",
            "frontier_or_human_role": "adjudicate ambiguity and expected artifacts",
            "skill_release_authorized": False,
            "pooled_metric_claim": False,
        },
        "claim_boundary": (
            "Both receipts use the same MATM revision and leave-one-model-out folds, "
            "but relevance retrieval and outcome prediction are different targets. "
            "This audit does not claim a model reranker gain or causal skill utility."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--embedding", type=Path, required=True)
    parser.add_argument("--outcome", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.embedding, args.outcome)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
