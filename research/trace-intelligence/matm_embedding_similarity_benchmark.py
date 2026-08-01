#!/usr/bin/env python3
"""Compare local semantic embeddings with lexical trace similarity on MATM.

This is a same-corpus retrieval study, not an agent intervention. For each
held-out model, rows from other models are candidates. The query may only use
its goal and observed action templates; task identity and outcome are labels.
The Ollama embedding service is loopback-only and raw texts/vectors never enter
the committed receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import random
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pyarrow.parquet as parquet
import requests


DATASET_REVISION = "d84d6454fc5fcc337e2527533f484b79cf6f0872"
MODEL = "nomic-embed-text:latest"
STOPWORDS = frozenset("a an and are at by for from in into of on or the to with you".split())


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def tokens(value: str) -> set[str]:
    return {x for x in re.findall(r"[a-z0-9]+", value.lower()) if len(x) > 1 and x not in STOPWORDS}


def action_templates(row: Mapping[str, Any]) -> list[str]:
    try:
        trajectory = json.loads(str(row.get("trajectory", "[]")))
    except json.JSONDecodeError:
        trajectory = []
    out = []
    for step in trajectory:
        if not isinstance(step, Mapping) or not step.get("action"):
            continue
        value = str(step["action"]).lower()
        value = re.sub(r"\b\d+\b", "N", value)
        value = re.sub(r"\b(?:the|a|an)\b", "", value)
        out.append(" ".join(value.split()))
    return out[:12]


def lexical_similarity(left: Mapping[str, Any], right: Mapping[str, Any], *, include_goal: bool = True) -> float:
    lg, rg = tokens(str(left.get("goal", ""))), tokens(str(right.get("goal", "")))
    la, ra = set(action_templates(left)), set(action_templates(right))
    def jac(a: set[str], b: set[str]) -> float:
        union = a | b
        return len(a & b) / len(union) if union else 0.0
    return (0.75 * jac(lg, rg) + 0.25 * jac(la, ra)) if include_goal else jac(la, ra)


def text_for(row: Mapping[str, Any], arm: str) -> str:
    goal = str(row.get("goal", ""))
    task_type = str(row.get("task_type", ""))
    if arm == "goal":
        return f"task type: {task_type}; goal: {goal}"
    actions = "; ".join(action_templates(row))
    if arm == "actions":
        return f"task type: {task_type}; observed action templates: {actions}"
    return f"task type: {task_type}; goal: {goal}; observed action templates: {actions}"


def work_signature(row: Mapping[str, Any]) -> str:
    """Cross-model work label; task_id is only unique within one model."""
    return f"{row.get('task_type', '')}|{str(row.get('goal', '')).strip().casefold()}"


def embed_unique(texts: Sequence[str], endpoint: str, batch_size: int) -> dict[str, np.ndarray]:
    unique = list(dict.fromkeys(texts))
    result: dict[str, np.ndarray] = {}
    for start in range(0, len(unique), batch_size):
        batch = unique[start:start + batch_size]
        response = requests.post(
            endpoint.rstrip("/") + "/api/embed",
            json={"model": MODEL, "input": batch, "truncate": True},
            timeout=180,
        )
        response.raise_for_status()
        payload = response.json()
        vectors = payload.get("embeddings")
        if not isinstance(vectors, list) or len(vectors) != len(batch):
            raise RuntimeError("embedding response count mismatch")
        for text, vector in zip(batch, vectors):
            result[text] = np.asarray(vector, dtype=np.float32)
    return result


def cosine(left: np.ndarray, right: np.ndarray) -> float:
    denom = float(np.linalg.norm(left) * np.linalg.norm(right))
    return float(np.dot(left, right) / denom) if denom else 0.0


def bootstrap_delta(results: dict[str, dict[str, Any]], left: str, right: str, metric_path: tuple[str, ...], seed: int = 20260802) -> dict[str, Any]:
    left_folds = {fold["held_out_model"]: fold for fold in results[left]["folds"]}
    right_folds = {fold["held_out_model"]: fold for fold in results[right]["folds"]}
    models = sorted(set(left_folds) & set(right_folds))
    def value(fold: dict[str, Any]) -> float:
        current: Any = fold
        for key in metric_path:
            current = current[key]
        return float(current)
    deltas = [value(left_folds[m]) - value(right_folds[m]) for m in models]
    rng = random.Random(seed)
    draws = []
    for _ in range(4000):
        sample = [deltas[rng.randrange(len(deltas))] for _ in deltas]
        draws.append(sum(sample) / len(sample))
    draws.sort()
    return {"left": left, "right": right, "metric": ".".join(metric_path), "folds": len(deltas), "mean_delta": round(sum(deltas) / len(deltas), 6), "bootstrap_ci95": [round(draws[80], 6), round(draws[3920], 6)]}


def rank_metrics(rows: Sequence[Mapping[str, Any]], scores: Sequence[list[tuple[float, int]]]) -> dict[str, Any]:
    ks = (1, 5, 10, 20)
    recalls = {str(k): [] for k in ks}
    reciprocal: list[float] = []
    top_success: list[float] = []
    for query, ranked in zip(rows, scores):
        task_id = query.get("task_id")
        ordered = [index for _, index in sorted(ranked, key=lambda item: item[0], reverse=True)]
        relevant = [position for position, index in enumerate(ordered, start=1) if rows[index].get("task_id") == task_id]
        reciprocal.append(1.0 / relevant[0] if relevant else 0.0)
        for k in ks:
            recalls[str(k)].append(float(any(position <= k for position in relevant)))
        top_n = max(1, math.ceil(len(ordered) * 0.10))
        top_success.append(sum(bool(rows[index].get("success")) for index in ordered[:top_n]) / top_n)
    return {
        "queries": len(rows),
        "recall_at_k": {k: round(sum(v) / len(v), 6) for k, v in recalls.items()},
        "mrr": round(sum(reciprocal) / len(reciprocal), 6),
        "top_10_percent_success_rate": round(sum(top_success) / len(top_success), 6),
    }


def run(path: Path, endpoint: str, batch_size: int) -> dict[str, Any]:
    source_hash = file_sha256(path)
    table = parquet.read_table(path)
    rows = [dict(row) for row in table.to_pylist()]
    if len(rows) != 2130:
        raise ValueError(f"unexpected MATM row count: {len(rows)}")
    models = sorted({str(row.get("model")) for row in rows})
    # Parse action JSON exactly once per row; the first implementation did
    # this inside every query/candidate pair and made the 34-fold study
    # needlessly unbounded.
    lexical_features = []
    for row in rows:
        goal = tokens(str(row.get("goal", "")))
        actions = set(action_templates(row))
        lexical_features.append((goal, actions))

    def lexical_score(left_index: int, right_index: int, *, include_goal: bool = True) -> float:
        lg, la = lexical_features[left_index]
        rg, ra = lexical_features[right_index]
        def jac(a: set[str], b: set[str]) -> float:
            union = a | b
            return len(a & b) / len(union) if union else 0.0
        return (0.75 * jac(lg, rg) + 0.25 * jac(la, ra)) if include_goal else jac(la, ra)

    all_results: dict[str, dict[str, Any]] = {}
    for arm in ("lexical", "lexical_actions", "goal", "actions", "goal_actions"):
        if arm in ("lexical", "lexical_actions"):
            norm_vectors = None
        else:
            texts = [text_for(row, arm) for row in rows]
            embedded = embed_unique(texts, endpoint, batch_size)
            matrix = np.vstack([embedded[text] for text in texts]).astype(np.float32)
            norms = np.linalg.norm(matrix, axis=1, keepdims=True)
            norm_vectors = matrix / np.maximum(norms, 1e-12)
        folds = []
        for held_out in models:
            train_indices = [index for index, row in enumerate(rows) if str(row.get("model")) != held_out]
            train_signatures = {work_signature(rows[index]) for index in train_indices}
            # Most MATM task IDs are model-local. Restrict the retrieval query
            # set to signatures that actually recur across models; otherwise a
            # zero Recall@K would be a label-construction artifact.
            test_indices = [index for index, row in enumerate(rows)
                            if str(row.get("model")) == held_out
                            and work_signature(row) in train_signatures]
            if not test_indices:
                continue
            scores: list[list[tuple[float, int]]] = []
            if arm in ("lexical", "lexical_actions"):
                for query_index in test_indices:
                    scores.append([(lexical_score(query_index, candidate_index, include_goal=arm == "lexical"), fold_index)
                                   for fold_index, candidate_index in enumerate(train_indices)])
            else:
                similarity = norm_vectors[test_indices] @ norm_vectors[train_indices].T
                for query_row in similarity:
                    scores.append([(float(score), fold_index) for fold_index, score in enumerate(query_row)])
            # Compute relevance/success against train explicitly because the
            # generic helper's row list is query-only by construction.
            recalls = {str(k): [] for k in (1, 5, 10, 20)}
            reciprocal = []
            top_success = []
            for query_index, ranked in zip(test_indices, scores):
                ordered = [idx for _, idx in sorted(ranked, key=lambda x: x[0], reverse=True)]
                rel = [pos for pos, idx in enumerate(ordered, 1)
                       if work_signature(rows[train_indices[idx]]) == work_signature(rows[query_index])]
                reciprocal.append(1.0 / rel[0] if rel else 0.0)
                for k in recalls:
                    recalls[k].append(float(any(pos <= int(k) for pos in rel)))
                top_n = max(1, math.ceil(len(ordered) * 0.10))
                top_success.append(sum(bool(rows[train_indices[idx]].get("success")) for idx in ordered[:top_n]) / top_n)
            folds.append({
                "held_out_model": held_out,
                "queries": len(test_indices),
                "candidate_rows": len(train_indices),
                "recall_at_k": {k: round(sum(v) / len(v), 6) for k, v in recalls.items()},
                "mrr": round(sum(reciprocal) / len(reciprocal), 6),
                "top_10_percent_success_rate": round(sum(top_success) / len(top_success), 6),
            })
        all_results[arm] = {
            "folds": folds,
            "eligible_models": len(folds),
            "eligible_queries": sum(f["queries"] for f in folds),
            "mean_recall_at_k": {k: round(sum(f["recall_at_k"][k] for f in folds) / len(folds), 6) for k in ("1", "5", "10", "20")},
            "mean_mrr": round(sum(f["mrr"] for f in folds) / len(folds), 6),
            "mean_top_10_percent_success_rate": round(sum(f["top_10_percent_success_rate"] for f in folds) / len(folds), 6),
        }
    return {
        "schema_version": "frankengate-matm-embedding-similarity-benchmark-v1",
        "study": "cross_model_same_task_retrieval",
        "dataset": {"source": "toeunkim/matm-trajectories", "revision": DATASET_REVISION, "rows": len(rows), "models": len(models), "source_sha256": source_hash},
        "protocol": {"split": "leave-one-model-out", "relevance": "same task_type plus normalized goal signature in another model", "outcomes_used_only_for_top_success_label": True, "raw_texts_or_vectors_committed": False, "embedding_endpoint": endpoint, "embedding_model": MODEL, "arms": ["lexical", "lexical_actions", "goal", "actions", "goal_actions"], "goal_in_label_and_goal_arms": True, "actions_arm_hides_goal": True},
        "results": all_results,
        "comparisons": [
            bootstrap_delta(all_results, "actions", "lexical_actions", ("recall_at_k", "20")),
            bootstrap_delta(all_results, "actions", "lexical_actions", ("mrr",)),
            bootstrap_delta(all_results, "actions", "lexical_actions", ("top_10_percent_success_rate",)),
            bootstrap_delta(all_results, "goal_actions", "lexical", ("recall_at_k", "20")),
        ],
        "claim_boundary": {"semantic_retrieval_measured": True, "changed_agent_utility_measured": False, "custom_embedding_promotion_authorized": False, "reason": "Retrieval relevance and outcome-neighbor precision are measured; no agent was rerun with retrieved traces."},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.dataset, args.endpoint, args.batch_size)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({arm: {k: value for k, value in payload.items() if k.startswith("mean_")} for arm, payload in result["results"].items()}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
