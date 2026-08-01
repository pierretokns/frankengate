#!/usr/bin/env python3
"""Database-family-held-out hard-negative adaptation on schema collisions.

This is intentionally a small diagnostic, not a production embedding trainer.
It compares identifier-only and table-aware Nomic embeddings with deterministic
structured retrieval and a regularized linear pair adapter trained on three
database families and evaluated on the fourth.  The labels are deterministic
gold-SQL focus proxies from the same-scope collision cohort; no semantic-alias
or downstream-agent claim is made.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Sequence

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from nl2sql_real_alias_benchmark import EMBED_MODEL, cosine, exact_surface, post_embed, stable_hash
from nl2sql_real_alias_cohort import lexical_score, normalize, question_tokens


SCHEMA_VERSION = "frankengate-nl2sql-collision-embedding-adaptation-v1"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def candidate_key(candidate: dict[str, str]) -> tuple[str, str, str]:
    return (candidate["db"], candidate["table"], candidate["identifier"])


def pair_features(query: np.ndarray, candidate: np.ndarray) -> np.ndarray:
    return np.concatenate((query * candidate, np.abs(query - candidate)))


def collision_before(case: dict[str, Any], order: Sequence[int]) -> float:
    target = case["target_objects"][0]
    target_key = (target["table"], target["identifier"])
    target_norm = normalize(target["identifier"])
    positions = [pos for pos, index in enumerate(order) if candidate_key(case["candidates"][index]) == (case["scope_db"], *target_key)]
    if not positions:
        return 0.0
    first = positions[0]
    return float(any(
        case["candidates"][index]["db"] == case["scope_db"]
        and normalize(case["candidates"][index]["identifier"]) == target_norm
        and case["candidates"][index]["table"] != target["table"]
        for index in order[:first]
    ))


def metrics(case: dict[str, Any], order: Sequence[int]) -> dict[str, float]:
    target = candidate_key(case["target_objects"][0])
    positions = [pos for pos, index in enumerate(order, start=1) if candidate_key(case["candidates"][index]) == target]
    first = positions[0] if positions else None
    return {
        "mrr": round(1.0 / first, 6) if first else 0.0,
        "recall_at_1": float(first == 1),
        "recall_at_5": float(first is not None and first <= 5),
        "same_scope_collision_before_target": collision_before(case, order),
    }


def aggregate(rows: list[dict[str, float]]) -> dict[str, Any]:
    def mean(key: str) -> float:
        return round(sum(row[key] for row in rows) / len(rows), 6) if rows else 0.0
    return {"cases": len(rows), "mrr": mean("mrr"), "recall_at_1": mean("recall_at_1"), "recall_at_5": mean("recall_at_5"), "same_scope_collision_before_target": mean("same_scope_collision_before_target")}


def _rank(scores: Sequence[float]) -> list[int]:
    return sorted(range(len(scores)), key=lambda index: (-float(scores[index]), index))


def run(raw_path: Path, output: Path, *, endpoint: str, C: float) -> dict[str, Any]:
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    cases = raw["cases"]
    if not cases:
        raise ValueError("empty collision cohort")
    query_texts = [f"question {case['question']}" for case in cases]
    candidate_texts = []
    candidate_id_texts = []
    positions: list[tuple[int, int]] = []
    for case_index, case in enumerate(cases):
        for candidate_index, candidate in enumerate(case["candidates"]):
            candidate_texts.append(f"database {candidate['db']} table {candidate['table']} identifier {candidate['identifier']}")
            candidate_id_texts.append(f"identifier {candidate['identifier']}")
            positions.append((case_index, candidate_index))
    vectors = post_embed(endpoint, query_texts + candidate_texts + candidate_id_texts)
    query_vectors = vectors[:len(query_texts)]
    table_vectors = vectors[len(query_texts):len(query_texts) + len(candidate_texts)]
    id_vectors = vectors[len(query_texts) + len(candidate_texts):]
    table_by_case: dict[tuple[int, int], list[float]] = {}
    id_by_case: dict[tuple[int, int], list[float]] = {}
    for position, key in enumerate(positions):
        table_by_case[key] = table_vectors[position]
        id_by_case[key] = id_vectors[position]
    databases = sorted({case["scope_db"] for case in cases})
    fold_results: list[dict[str, Any]] = []
    for held_out in databases:
        train_indices = [index for index, case in enumerate(cases) if case["scope_db"] != held_out]
        test_indices = [index for index, case in enumerate(cases) if case["scope_db"] == held_out]
        train_x: list[np.ndarray] = []
        train_y: list[int] = []
        for case_index in train_indices:
            case = cases[case_index]
            target_key = candidate_key(case["target_objects"][0])
            for candidate_index, candidate in enumerate(case["candidates"]):
                is_target = int(candidate_key(candidate) == target_key)
                is_negative = is_target == 0 and (candidate["table"] == case["target_objects"][0]["table"] or normalize(candidate["identifier"]) == normalize(case["target_objects"][0]["identifier"]))
                if is_target or is_negative:
                    train_x.append(pair_features(np.asarray(query_vectors[case_index]), np.asarray(table_by_case[(case_index, candidate_index)])))
                    train_y.append(is_target)
        scaler = StandardScaler()
        x_scaled = scaler.fit_transform(np.asarray(train_x))
        model = LogisticRegression(C=C, class_weight="balanced", max_iter=500, random_state=0)
        model.fit(x_scaled, train_y)
        arms: dict[str, list[dict[str, float]]] = defaultdict(list)
        for case_index in test_indices:
            case = cases[case_index]
            q = np.asarray(query_vectors[case_index])
            id_scores = [cosine(q, np.asarray(id_by_case[(case_index, candidate_index)])) for candidate_index in range(len(case["candidates"]))]
            table_scores = [cosine(q, np.asarray(table_by_case[(case_index, candidate_index)])) for candidate_index in range(len(case["candidates"]))]
            structured_scores = [float(exact_surface(case["question"], candidate["identifier"])) * 10.0 + lexical_score(case["question"], candidate) for candidate in case["candidates"]]
            adapted_scores = [float(model.decision_function(scaler.transform(pair_features(q, np.asarray(table_by_case[(case_index, candidate_index)])).reshape(1, -1))[0].reshape(1, -1))[0]) for candidate_index in range(len(case["candidates"]))]
            for arm, scores in {"identifier_embedding": id_scores, "table_embedding": table_scores, "structured": structured_scores, "hard_negative_adapter": adapted_scores}.items():
                arms[arm].append(metrics(case, _rank(scores)))
        fold_results.append({"held_out_database": held_out, "train_cases": len(train_indices), "test_cases": len(test_indices), "arms": {arm: aggregate(rows) for arm, rows in arms.items()}})
    aggregate_by_arm: dict[str, dict[str, Any]] = {}
    for arm in ("identifier_embedding", "table_embedding", "structured", "hard_negative_adapter"):
        rows = [fold["arms"][arm] for fold in fold_results]
        aggregate_by_arm[arm] = {"folds": len(rows), "mean_mrr": round(sum(row["mrr"] for row in rows) / len(rows), 6), "mean_recall_at_1": round(sum(row["recall_at_1"] for row in rows) / len(rows), 6), "mean_recall_at_5": round(sum(row["recall_at_5"] for row in rows) / len(rows), 6), "mean_same_scope_collision_before_target": round(sum(row["same_scope_collision_before_target"] for row in rows) / len(rows), 6)}
    result = {
        "schema_version": SCHEMA_VERSION,
        "dataset": {"raw_sha256": file_sha256(raw_path), "cases": len(cases), "databases": databases, "raw_content_committed": False},
        "protocol": {"split": "leave-one-database-family-out", "embedding_model": EMBED_MODEL, "adapter": "regularized logistic pair scorer over query/candidate table-aware Nomic product+difference features", "hard_negative_labels": "focus target positive; same-table or same-normalized-name candidates negative", "C": C},
        "aggregate": aggregate_by_arm,
        "folds": fold_results,
        "claim_boundary": "Small database-family-held-out hard-negative diagnostic on deterministic gold-SQL focus proxies. It does not establish a generally useful corporate embedding model or downstream agent utility.",
    }
    result["result_sha256"] = stable_hash(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "aggregate": aggregate_by_arm, "result_sha256": result["result_sha256"]}, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--C", type=float, default=0.1)
    args = parser.parse_args()
    run(args.raw, args.output, endpoint=args.endpoint, C=args.C)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
