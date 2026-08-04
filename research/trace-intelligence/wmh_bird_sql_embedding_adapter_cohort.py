#!/usr/bin/env python3
"""Evaluate a leakage-safe task-local adapter over WMH-BIRD table embeddings.

The frozen Nomic embedding is compared with a small diagonal/pairwise ranking
adapter trained only on the even half of each database's task IDs. Evaluation
uses the odd half and independent SQLite result-preserving substitutions. This
is a representation-learning diagnostic, not an enterprise embedding claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from typing import Any, Sequence
from urllib import request

from wmh_bird_equivalence_aware_retrieval import equivalent_candidates
from wmh_bird_exposure_counterfactual import execute, file_hash, load_traces
from wmh_bird_sql_explorer_probe import lexical_order, metric_row, stable_hash


SCHEMA_VERSION = "frankengate-wmh-bird-sql-embedding-adapter-cohort-v1"
EMBED_MODEL = "nomic-embed-text:latest"
MAX_SHORTLIST = 8


def cosine(left: Sequence[float], right: Sequence[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(a * a for a in right))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


def post_embed(endpoint: str, texts: Sequence[str]) -> list[list[float]]:
    payload = json.dumps({"model": EMBED_MODEL, "input": list(texts), "truncate": True}).encode()
    req = request.Request(endpoint.rstrip("/") + "/api/embed", data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with request.urlopen(req, timeout=300) as response:
        value = json.loads(response.read().decode())
    vectors = value.get("embeddings")
    if not isinstance(vectors, list) or len(vectors) != len(texts):
        raise RuntimeError("embedding response count mismatch")
    return [[float(item) for item in vector] for vector in vectors]


def cohort(traces: list[Any], db_root: Path, per_db: int) -> tuple[list[Any], list[Any]]:
    by_db: dict[str, list[Any]] = defaultdict(list)
    for trace in traces:
        db_path = db_root / trace.db_name / f"{trace.db_name}.sqlite"
        status, _ = execute(db_path, trace.sql)
        if status == "ok" and trace.used_tables & trace.exposed_tables:
            by_db[trace.db_name].append(trace)
    train: list[Any] = []
    evaluation: list[Any] = []
    for db in sorted(by_db):
        ordered = sorted(by_db[db], key=lambda item: stable_hash(item.base_task_id))
        train.extend(ordered[::2])
        evaluation.extend(ordered[1::2][:per_db])
    return train, evaluation


def feature(query: Sequence[float], candidate: Sequence[float]) -> list[float]:
    # Absolute distance plus interaction preserves both directional and
    # proximity information while keeping the adapter intentionally small.
    return [abs(a - b) for a, b in zip(query, candidate)] + [a * b for a, b in zip(query, candidate)]


def train_adapter(examples: list[tuple[list[float], list[float]]], *, epochs: int = 20, seed: int = 7) -> tuple[list[float], int]:
    if not examples:
        raise ValueError("no positive/negative training pairs")
    dimension = len(examples[0][0])
    weights = [0.0] * dimension
    rng = random.Random(seed)
    pair_count = 0
    for _ in range(epochs):
        order = list(range(len(examples)))
        rng.shuffle(order)
        for index in order:
            positive, negative = examples[index]
            diff = [a - b for a, b in zip(positive, negative)]
            margin = sum(weight * value for weight, value in zip(weights, diff))
            # Pairwise hinge ranking with a small shrinkage term.
            shrink = 0.0005
            weights = [(1.0 - shrink) * weight for weight in weights]
            if margin < 1.0:
                learning_rate = 0.03
                weights = [weight + learning_rate * value for weight, value in zip(weights, diff)]
            pair_count += 1
    norm = math.sqrt(sum(weight * weight for weight in weights))
    if norm:
        weights = [weight / norm for weight in weights]
    return weights, pair_count


def run(
    traces_path: Path,
    manifest: Path,
    db_root: Path,
    output: Path,
    *,
    endpoint: str,
    per_db: int,
    expected_evaluation_tasks: int | None = 44,
) -> dict[str, Any]:
    traces = load_traces(traces_path, manifest)
    train, evaluation = cohort(traces, db_root, per_db)
    if expected_evaluation_tasks is not None and len(evaluation) != expected_evaluation_tasks:
        raise ValueError(f"expected {expected_evaluation_tasks} evaluation tasks, got {len(evaluation)}")
    candidate_tables = sorted({table for trace in train + evaluation for table in trace.exposed_tables})
    # Embed each question and each database/table object once.
    texts: list[str] = []
    keys: list[tuple[str, str, str | None]] = []
    for trace in train + evaluation:
        texts.append(f"database {trace.db_name} question {trace.prompt}")
        keys.append(("query", trace.trace_hash, trace.db_name))
    for db in sorted({trace.db_name for trace in train + evaluation}):
        for table in sorted({table for trace in train + evaluation if trace.db_name == db for table in trace.exposed_tables}):
            texts.append(f"database {db} table {table}")
            keys.append(("candidate", table, db))
    vectors = post_embed(endpoint, texts)
    query_vectors = {key: vectors[index] for index, key in enumerate(keys) if key[0] == "query"}
    candidate_vectors = {(key[2], key[1]): vectors[index] for index, key in enumerate(keys) if key[0] == "candidate"}

    train_examples: list[tuple[list[float], list[float]]] = []
    for trace in train:
        targets = frozenset(trace.used_tables & trace.exposed_tables)
        equivalents, _, _ = equivalent_candidates(trace, db_root)
        compatible = targets | equivalents
        if not compatible:
            continue
        positives = [table for table in trace.exposed_tables if table in compatible]
        negatives = [table for table in trace.exposed_tables if table not in compatible]
        if not positives or not negatives:
            continue
        for positive in positives:
            for negative in negatives:
                train_examples.append((feature(query_vectors[("query", trace.trace_hash, trace.db_name)], candidate_vectors[(trace.db_name, positive)]), feature(query_vectors[("query", trace.trace_hash, trace.db_name)], candidate_vectors[(trace.db_name, negative)])))
    weights, pair_count = train_adapter(train_examples)
    rows: list[dict[str, Any]] = []
    for trace in evaluation:
        candidates = sorted(trace.exposed_tables)
        targets = frozenset(trace.used_tables & trace.exposed_tables)
        equivalents, _, _ = equivalent_candidates(trace, db_root)
        compatible = targets | equivalents
        query = query_vectors[("query", trace.trace_hash, trace.db_name)]
        dense_order = sorted(candidates, key=lambda table: (-cosine(query, candidate_vectors[(trace.db_name, table)]), table))[:MAX_SHORTLIST]
        adapted_order = sorted(candidates, key=lambda table: (-sum(weight * value for weight, value in zip(weights, feature(query, candidate_vectors[(trace.db_name, table)]))), table))[:MAX_SHORTLIST]
        lexical = lexical_order(trace)[:MAX_SHORTLIST]
        rows.append({
            "db_name": trace.db_name,
            "trace_hash": trace.trace_hash,
            "base_task_id_hash": hashlib.sha256(trace.base_task_id.encode()).hexdigest(),
            "candidate_count": len(candidates),
            "target_count": len(targets),
            "equivalent_count": len(equivalents),
            "lexical": metric_row(lexical, targets, compatible, len(candidates)),
            "dense": metric_row(dense_order, targets, compatible, len(candidates)),
            "adapted": metric_row(adapted_order, targets, compatible, len(candidates)),
        })
    arms: dict[str, dict[str, Any]] = {}
    for arm in ("lexical", "dense", "adapted"):
        values = [row[arm] for row in rows]
        arms[arm] = {
            "records": len(values),
            "strict_mrr": round(sum(float(row["strict_mrr"]) for row in values) / len(values), 6),
            "strict_recall_at_1": round(sum(float(row["strict_recall_at_1"]) for row in values) / len(values), 6),
            "strict_recall_at_5": round(sum(float(row["strict_recall_at_5"]) for row in values) / len(values), 6),
            "compatible_mrr": round(sum(float(row["compatible_mrr"]) for row in values) / len(values), 6),
            "compatible_recall_at_1": round(sum(float(row["compatible_recall_at_1"]) for row in values) / len(values), 6),
            "compatible_recall_at_5": round(sum(float(row["compatible_recall_at_5"]) for row in values) / len(values), 6),
            "compatible_selected_rate": round(sum(float(row["compatible_selected_rate"]) for row in values) / len(values), 6),
            "invalid_selected_count": round(sum(float(row["invalid_selected_count"]) for row in values) / len(values), 6),
            "selected_count": round(sum(float(row["selected_count"]) for row in values) / len(values), 6),
        }
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source": {"traces_sha256": file_hash(traces_path), "manifest_sha256": file_hash(manifest), "raw_content_committed": False, "sqlite_root": "external-pinned-bird-minidev"},
        "dataset": {"train_tasks": len(train), "evaluation_tasks": len(evaluation), "database_families": sorted({row["db_name"] for row in rows}), "split": "within-database deterministic even/odd task split; adapter trains on even and evaluates on odd", "positive_label": "recorded SQL tables plus independently replay-confirmed compatible substitutions"},
        "protocol": {"embedding_endpoint": endpoint, "embedding_model": EMBED_MODEL, "adapter": "pairwise hinge over absolute-difference and interaction features", "epochs": 20, "seed": 7, "training_pair_count": pair_count, "candidate_pool": "all tables exposed in each trace", "per_db": per_db, "expected_evaluation_tasks": expected_evaluation_tasks, "raw_content_committed": False},
        "arms": arms,
        "rows": rows,
        "claim_boundary": {"task_disjoint_adapter_measured": True, "custom_enterprise_embedding_established": False, "semantic_alias_quality_established": False, "validated_artifact_utility_established": False, "enterprise_skill_transfer_measured": False, "reason": "Public WMH-BIRD proxy with SQL-table labels and independent SQLite compatibility. This is a fold-local reranking diagnostic, not an enterprise embedding or causal utility result."},
    }
    result["result_sha256"] = stable_hash(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"arms": arms, "train_tasks": len(train), "evaluation_tasks": len(evaluation), "training_pair_count": pair_count}, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--traces", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--db-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--per-db", type=int, default=4)
    parser.add_argument("--expected-evaluation-tasks", type=int, default=44, help="Expected evaluation rows; use 0 to allow a variable full odd-half cohort.")
    args = parser.parse_args()
    run(args.traces, args.manifest, args.db_root, args.output, endpoint=args.endpoint, per_db=args.per_db, expected_evaluation_tasks=None if args.expected_evaluation_tasks == 0 else args.expected_evaluation_tasks)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
