#!/usr/bin/env python3
"""Leakage-safe metric adaptation for MATM action-only embeddings.

This is a bounded domain-adaptation experiment, not a production model. A
fold-local logistic metric learns from repeated-work positives and sampled
hard negatives among non-held-out models, then ranks a held-out model. Raw
texts/vectors stay in the external cache; the receipt contains aggregate
metrics and hashes only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pyarrow.parquet as parquet
import requests
from sklearn.linear_model import LogisticRegression


DATASET_REVISION = "d84d6454fc5fcc337e2527533f484b79cf6f0872"
MODEL = "nomic-embed-text:latest"
STOPWORDS = frozenset("a an and are at by for from in into of on or the to with you".split())


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", value.lower()) if len(token) > 1 and token not in STOPWORDS}


def action_templates(row: Mapping[str, Any]) -> list[str]:
    try:
        trajectory = json.loads(str(row.get("trajectory", "[]")))
    except json.JSONDecodeError:
        trajectory = []
    actions = []
    for step in trajectory:
        if not isinstance(step, Mapping) or not step.get("action"):
            continue
        value = re.sub(r"\b\d+\b", "N", str(step["action"]).lower())
        value = re.sub(r"\b(?:the|a|an)\b", "", value)
        actions.append(" ".join(value.split()))
    return actions[:12]


def text_for(row: Mapping[str, Any]) -> str:
    return f"task type: {row.get('task_type', '')}; observed action templates: {'; '.join(action_templates(row))}"


def signature(row: Mapping[str, Any]) -> str:
    return f"{row.get('task_type', '')}|{str(row.get('goal', '')).strip().casefold()}"


def embed_unique(texts: list[str], endpoint: str, cache: Path, batch_size: int) -> np.ndarray:
    cache.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256("\n".join(texts).encode()).hexdigest()
    cache_file = cache / f"{key}.npz"
    if cache_file.exists():
        cached = np.load(cache_file)
        return np.asarray(cached["vectors"], dtype=np.float32)
    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        response = requests.post(
            endpoint.rstrip("/") + "/api/embed",
            json={"model": MODEL, "input": batch, "truncate": True},
            timeout=180,
        )
        response.raise_for_status()
        payload = response.json()
        batch_vectors = payload.get("embeddings")
        if not isinstance(batch_vectors, list) or len(batch_vectors) != len(batch):
            raise RuntimeError("embedding response count mismatch")
        vectors.extend(batch_vectors)
    matrix = np.asarray(vectors, dtype=np.float32)
    matrix /= np.maximum(np.linalg.norm(matrix, axis=1, keepdims=True), 1e-12)
    np.savez_compressed(cache_file, vectors=matrix)
    return matrix


def recall_metrics(ordered: list[int], query_signature: str, signatures: list[str]) -> dict[str, float]:
    relevant = [position for position, index in enumerate(ordered, 1) if signatures[index] == query_signature]
    return {
        "recall_at_20": float(any(position <= 20 for position in relevant)),
        "mrr": 1.0 / relevant[0] if relevant else 0.0,
    }


def bootstrap_ci(values: list[float], seed: int = 20260802) -> list[float]:
    if not values:
        return [0.0, 0.0]
    rng = random.Random(seed)
    means = []
    for _ in range(4000):
        sample = [values[rng.randrange(len(values))] for _ in values]
        means.append(sum(sample) / len(sample))
    means.sort()
    return [means[80], means[3920]]


def build_pairs(train: list[int], vectors: np.ndarray, signatures: list[str], rng: random.Random) -> tuple[np.ndarray, np.ndarray]:
    by_signature: dict[str, list[int]] = {}
    for index in train:
        by_signature.setdefault(signatures[index], []).append(index)
    positives: list[tuple[int, int]] = []
    for indices in by_signature.values():
        if len(indices) < 2:
            continue
        rng.shuffle(indices)
        positives.extend((left, right) for left, right in zip(indices, indices[1:]))
    if not positives:
        raise ValueError("fold has no repeated-work positive pairs")
    other_by_signature = {key: value for key, value in by_signature.items()}
    all_signatures = list(other_by_signature)
    negative_pairs: list[tuple[int, int]] = []
    for left, _ in positives:
        candidates = [index for index in train if signatures[index] != signatures[left]]
        if not candidates:
            continue
        sample = rng.sample(candidates, min(24, len(candidates)))
        right = max(sample, key=lambda index: float(np.dot(vectors[left], vectors[index])))
        negative_pairs.append((left, right))
    pairs = positives + negative_pairs
    features = np.asarray([np.abs(vectors[left] - vectors[right]) for left, right in pairs], dtype=np.float32)
    labels = np.asarray([1] * len(positives) + [0] * len(negative_pairs), dtype=np.int8)
    return features, labels


def run(dataset: Path, endpoint: str, cache: Path, batch_size: int) -> dict[str, Any]:
    source_hash = file_sha256(dataset)
    rows = [dict(row) for row in parquet.read_table(dataset).to_pylist()]
    if len(rows) != 2130:
        raise ValueError(f"unexpected MATM row count: {len(rows)}")
    models = sorted({str(row.get("model")) for row in rows})
    texts = [text_for(row) for row in rows]
    vectors = embed_unique(texts, endpoint, cache, batch_size)
    signatures = [signature(row) for row in rows]
    folds: list[dict[str, Any]] = []
    for held_out in models:
        train = [index for index, row in enumerate(rows) if str(row.get("model")) != held_out]
        train_signatures = {signatures[index] for index in train}
        test = [index for index, row in enumerate(rows) if str(row.get("model")) == held_out and signatures[index] in train_signatures]
        if not test:
            continue
        rng = random.Random(20260802 + len(folds))
        features, labels = build_pairs(train, vectors, signatures, rng)
        adapter = LogisticRegression(max_iter=300, class_weight="balanced", random_state=20260802, solver="liblinear")
        adapter.fit(features, labels)
        baseline_rows: list[dict[str, float]] = []
        adapted_rows: list[dict[str, float]] = []
        train_vectors = vectors[train]
        for query_index in test:
            cosine_scores = train_vectors @ vectors[query_index]
            baseline_order = sorted(range(len(train)), key=lambda pos: (-float(cosine_scores[pos]), pos))
            adapted_features = np.abs(train_vectors - vectors[query_index])
            adapted_scores = adapter.predict_proba(adapted_features)[:, 1]
            adapted_order = sorted(range(len(train)), key=lambda pos: (-float(adapted_scores[pos]), pos))
            baseline_rows.append(recall_metrics([train[pos] for pos in baseline_order], signatures[query_index], signatures))
            adapted_rows.append(recall_metrics([train[pos] for pos in adapted_order], signatures[query_index], signatures))
        folds.append({
            "held_out_model": held_out,
            "queries": len(test),
            "train_rows": len(train),
            "training_pairs": len(labels),
            "positive_pairs": int(labels.sum()),
            "baseline_recall_at_20": sum(row["recall_at_20"] for row in baseline_rows) / len(baseline_rows),
            "adapted_recall_at_20": sum(row["recall_at_20"] for row in adapted_rows) / len(adapted_rows),
            "baseline_mrr": sum(row["mrr"] for row in baseline_rows) / len(baseline_rows),
            "adapted_mrr": sum(row["mrr"] for row in adapted_rows) / len(adapted_rows),
        })
    deltas_recall = [fold["adapted_recall_at_20"] - fold["baseline_recall_at_20"] for fold in folds]
    deltas_mrr = [fold["adapted_mrr"] - fold["baseline_mrr"] for fold in folds]
    return {
        "schema_version": "frankengate-matm-domain-embedding-adapter-v1",
        "dataset": {"id": "toeunkim/matm-trajectories", "revision": DATASET_REVISION, "rows": len(rows), "models": len(models), "source_sha256": source_hash},
        "protocol": {
            "split": "leave-one-model-out",
            "features": "action-only embedding; goal hidden from representation",
            "training_labels": "same task_type plus normalized goal signature within fold-local training models",
            "hard_negatives": "highest base-cosine candidate among sampled different-signature training rows",
            "adapter": "fold-local logistic metric over absolute embedding differences",
            "embedding_endpoint": endpoint,
            "embedding_model": MODEL,
            "raw_texts_or_vectors_committed": False,
        },
        "aggregate": {
            "folds": len(folds),
            "eligible_queries": sum(fold["queries"] for fold in folds),
            "mean_recall_delta": sum(deltas_recall) / len(deltas_recall),
            "mean_recall_delta_bootstrap_ci95": bootstrap_ci(deltas_recall),
            "mean_mrr_delta": sum(deltas_mrr) / len(deltas_mrr),
            "mean_mrr_delta_bootstrap_ci95": bootstrap_ci(deltas_mrr, seed=20260803),
            "baseline_recall_at_20": sum(fold["baseline_recall_at_20"] for fold in folds) / len(folds),
            "adapted_recall_at_20": sum(fold["adapted_recall_at_20"] for fold in folds) / len(folds),
            "baseline_mrr": sum(fold["baseline_mrr"] for fold in folds) / len(folds),
            "adapted_mrr": sum(fold["adapted_mrr"] for fold in folds) / len(folds),
        },
        "folds": folds,
        "claim_boundary": {
            "domain_adaptation_executed": True,
            "causal_skill_utility_measured": False,
            "human_alias_labels": False,
            "custom_embedding_promotion_authorized": False,
            "reason": "Silver same-work labels and model-held-out replay measure metric adaptation only; no agent intervention or enterprise outcome is evaluated.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.dataset, args.endpoint, args.cache, args.batch_size)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["aggregate"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
