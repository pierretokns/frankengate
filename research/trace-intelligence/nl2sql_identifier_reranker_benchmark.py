#!/usr/bin/env python3
"""Held-out database test for identifier-aware hard-negative ranking.

The input is the external same-scope collision cohort.  One database is held
out at a time; a tiny logistic ranker is trained on the other databases using
only query/candidate surface and authority features.  The hard-negative arm
upweights same-scope, same-normalized-identifier siblings during training.

This measures representation value, not semantic-alias truth: the positive is
the deterministic gold-SQL focus proxy already defined by the cohort.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression

from nl2sql_real_alias_cohort import lexical_score, normalize


SCHEMA_VERSION = "frankengate-nl2sql-identifier-reranker-v1"
TOKEN_RE = re.compile(r"[a-z0-9_]+", re.IGNORECASE)
FEATURE_NAMES = (
    "scope_match",
    "identifier_surface",
    "table_surface",
    "identifier_token_overlap",
    "table_token_overlap",
    "lexical_score",
    "same_scope_collision",
    "candidate_is_target_proxy",
)


def stable_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def candidate_key(candidate: dict[str, str]) -> tuple[str, str, str]:
    return candidate["db"], candidate["table"], candidate["identifier"]


def candidate_fingerprint(candidate: dict[str, str]) -> str:
    return stable_hash(candidate)


def _tokens(value: str) -> set[str]:
    return {token.lower() for token in TOKEN_RE.findall(value)}


def _surface(question: str, value: str) -> float:
    normalized_question = " ".join(_tokens(question))
    normalized_value = normalize(value)
    return float(normalized_value and normalized_value in normalize(question))


def _collision(candidate: dict[str, str], case: dict[str, Any]) -> float:
    if candidate["db"] != case["scope_db"]:
        return 0.0
    target = case["target_objects"][0]
    target_key = (target["table"], target["identifier"])
    target_norm = normalize(target["identifier"])
    if (candidate["table"], candidate["identifier"]) == target_key:
        return 0.0
    return float(normalize(candidate["identifier"]) == target_norm)


def feature_row(case: dict[str, Any], candidate: dict[str, str], *, include_label: bool) -> list[float]:
    question = case["question"]
    identifier_tokens = _tokens(candidate["identifier"].replace("_", " "))
    table_tokens = _tokens(candidate["table"].replace("_", " "))
    question_tokens = _tokens(question.replace("_", " "))
    target_key = candidate_key(case["target_objects"][0])
    row = [
        float(candidate["db"] == case["scope_db"]),
        _surface(question, candidate["identifier"]),
        _surface(question, candidate["table"]),
        float(len(identifier_tokens & question_tokens)) / max(1, len(identifier_tokens)),
        float(len(table_tokens & question_tokens)) / max(1, len(table_tokens)),
        lexical_score(question, candidate),
        _collision(candidate, case),
    ]
    if include_label:
        row.append(float(candidate_key(candidate) == target_key))
    return row


def _rank_metrics(case: dict[str, Any], order: list[int]) -> dict[str, float]:
    target_key = candidate_key(case["target_objects"][0])
    positions = [index + 1 for index, candidate_index in enumerate(order) if candidate_key(case["candidates"][candidate_index]) == target_key]
    first = positions[0] if positions else None
    target_norm = normalize(case["target_objects"][0]["identifier"])
    first_collision = any(
        candidate["db"] == case["scope_db"]
        and normalize(candidate["identifier"]) == target_norm
        and candidate_key(candidate) != target_key
        for candidate_index in order[: max(0, (first or len(order) + 1) - 1)]
        for candidate in [case["candidates"][candidate_index]]
    )
    return {
        "mrr": round(1.0 / first, 6) if first else 0.0,
        "recall_at_1": float(first == 1),
        "recall_at_5": float(first is not None and first <= 5),
        "same_scope_collision_before_target": float(first_collision),
    }


def _aggregate(rows: list[dict[str, float]]) -> dict[str, float]:
    return {
        "cases": len(rows),
        **{
            key: round(sum(row[key] for row in rows) / len(rows), 6) if rows else 0.0
            for key in ("mrr", "recall_at_1", "recall_at_5", "same_scope_collision_before_target")
        },
    }


def _fit(train_cases: list[dict[str, Any]], hard_negative: bool) -> LogisticRegression:
    features: list[list[float]] = []
    labels: list[int] = []
    weights: list[float] = []
    for case in train_cases:
        target_key = candidate_key(case["target_objects"][0])
        for candidate in case["candidates"]:
            features.append(feature_row(case, candidate, include_label=False))
            is_target = candidate_key(candidate) == target_key
            labels.append(int(is_target))
            weights.append(4.0 if hard_negative and not is_target and _collision(candidate, case) else 1.0)
    model = LogisticRegression(C=1.0, max_iter=1000, random_state=0)
    model.fit(np.asarray(features), np.asarray(labels), sample_weight=np.asarray(weights))
    return model


def run(raw_path: Path, result_path: Path) -> dict[str, Any]:
    payload = json.loads(raw_path.read_text(encoding="utf-8"))
    cases = payload["cases"]
    databases = sorted({case["scope_db"] for case in cases})
    arms = {"identifier_reranker": [], "hard_negative_reranker": []}
    per_case: list[dict[str, Any]] = []
    for held_out in databases:
        train = [case for case in cases if case["scope_db"] != held_out]
        test = [case for case in cases if case["scope_db"] == held_out]
        if not train or not test:
            continue
        models = {"identifier_reranker": _fit(train, False), "hard_negative_reranker": _fit(train, True)}
        for case in test:
            orders: dict[str, list[int]] = {}
            for arm, model in models.items():
                matrix = np.asarray([feature_row(case, candidate, include_label=False) for candidate in case["candidates"]])
                scores = model.predict_proba(matrix)[:, 1]
                orders[arm] = sorted(range(len(case["candidates"])), key=lambda index: (-float(scores[index]), index))
                arms[arm].append(_rank_metrics(case, orders[arm]))
            per_case.append({
                "case_id": case["case_id"],
                "held_out_database": held_out,
                "candidate_fingerprints": [candidate_fingerprint(candidate) for candidate in case["candidates"]],
                "target_fingerprint": candidate_fingerprint(case["target_objects"][0]),
                "orders": orders,
                "metrics": {arm: _rank_metrics(case, order) for arm, order in orders.items()},
            })
    result = {
        "schema_version": SCHEMA_VERSION,
        "dataset": {
            "raw_sha256": hashlib.sha256(raw_path.read_bytes()).hexdigest(),
            "cases": len(per_case),
            "databases": databases,
            "raw_content_committed": False,
        },
        "protocol": {
            "split": "leave-one-database-out",
            "features": FEATURE_NAMES,
            "hard_negative_weight": 4.0,
            "positive": "gold-SQL focus proxy, not semantic truth",
            "model": "sklearn LogisticRegression C=1 max_iter=1000 random_state=0",
        },
        "aggregate": {arm: _aggregate(values) for arm, values in arms.items()},
        "per_case": per_case,
        "claim_boundary": "Public same-scope collision proxy ranking only; no SME semantic labels, downstream task replay, or enterprise transfer claim.",
    }
    result["result_sha256"] = stable_hash(result)
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.raw, args.result)
    print(json.dumps(result["aggregate"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
