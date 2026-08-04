#!/usr/bin/env python3
"""Compare the Replit-style facet/cluster loop with Frankengate baseline.

Replit describes compact, evidence-grounded trace facets, embeddings, density
clustering, online A/B measurement, and a trace-cluster -> eval/improvement
loop.  This experiment tests the first and most measurable part locally:

* deterministic event-first wiki-gap miner (Frankengate baseline)
* raw-question lexical clustering
* compact-facet lexical clustering
* raw-question MiniLM embedding clustering
* compact-facet MiniLM embedding clustering
* combined baseline + cluster lineage

The labeled cohort is synthetic and intentionally includes hard controls that
reuse the exact text of a positive query but have successful wiki evidence.
That prevents raw-text clustering from receiving an unfairly easy test.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.feature_extraction.text import TfidfVectorizer

from wiki_gap_labeled_experiment import NOW, POSITIVE_STRATA, build_cohort, evaluate
from wiki_gap_miner import mine_gap_candidates


SCHEMA_VERSION = "frankengate-replit-claims-factorial-v1"
DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def _event(event_id: str, event_type: str, query_id: str, user_id: str, **values: Any) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "event_type": event_type,
        "query_id": query_id,
        "session_id": f"session-{query_id}",
        "user_id": user_id,
        "timestamp": "2026-08-03T00:00:00Z",
        **values,
    }


def add_collision_controls(
    events: list[dict[str, Any]], gold: list[dict[str, Any]], *, count: int
) -> None:
    """Add successful and unobserved queries with a positive query's exact text."""
    for index in range(count):
        query_id = f"collision-success-{index:03d}"
        user_id = f"collision-user-{index:03d}"
        events.extend(
            [
                _event(f"{query_id}-q", "question", query_id, user_id, text="How do I rotate the mantle key?"),
                _event(f"{query_id}-r", "retrieval", query_id, user_id, page_ids=["page-current"], wiki_search_attempted=True),
                _event(f"{query_id}-a", "answer", query_id, user_id, answerable=True, confidence=0.95),
                _event(f"{query_id}-o", "outcome", query_id, user_id, status="success"),
            ]
        )
        gold.append({"query_id": query_id, "stratum": "success_collision", "gold_gap": False})
    for index in range(count):
        query_id = f"collision-unobserved-{index:03d}"
        user_id = f"unobserved-user-{index:03d}"
        events.extend(
            [
                _event(f"{query_id}-q", "question", query_id, user_id, text="How do I rotate the mantle key?"),
                _event(f"{query_id}-o", "outcome", query_id, user_id, status="success"),
            ]
        )
        gold.append({"query_id": query_id, "stratum": "unobserved_collision", "gold_gap": False})


def build_factorial_cohort(per_stratum: int, collision_count: int) -> tuple[list[dict[str, Any]], list[Any], list[dict[str, Any]]]:
    events, pages, gold = build_cohort(per_stratum)
    add_collision_controls(events, gold, count=collision_count)
    return events, pages, gold


def query_records(events: Iterable[dict[str, Any]], gold: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        grouped[str(event.get("query_id", ""))].append(event)
    records: list[dict[str, Any]] = []
    for row in gold:
        query_id = str(row["query_id"])
        query_events = grouped[query_id]
        question = next(event for event in query_events if event.get("event_type") == "question")
        retrievals = [event for event in query_events if event.get("event_type") == "retrieval"]
        answers = [event for event in query_events if event.get("event_type") == "answer"]
        signals: list[str] = []
        wiki_observed = any(
            event.get("event_type") in {"retrieval", "answer", "wiki_search"}
            or event.get("wiki_search_attempted") is True
            for event in query_events
        )
        if not wiki_observed:
            signals.append("wiki_unobserved")
        if retrievals and not any(event.get("page_ids") for event in retrievals):
            signals.append("retrieval_empty")
        if any(event.get("external") is True for event in query_events):
            signals.append("external_fallback")
        if any(event.get("event_type") == "feedback" for event in query_events):
            signals.append("correction")
        if any(str(event.get("status", "")).casefold() in {"failure", "failed", "rollback"} for event in query_events):
            signals.append("failure")
        if any(
            event.get("event_type") == "answer"
            and (event.get("answerable") is False or float(event.get("confidence", 1.0)) < 0.4)
            for event in answers
        ):
            signals.append("weak_answer")
        if any(event.get("event_type") == "wiki_scope" and event.get("scope_status") == "out_of_scope" for event in query_events):
            signals.append("out_of_scope")
        query_text = str(question.get("text", ""))
        records.append(
            {
                "query_id": query_id,
                "user_id": str(question.get("user_id", "")),
                "text": query_text,
                "stratum": str(row["stratum"]),
                "gold_gap": bool(row["gold_gap"]),
                "signals": tuple(sorted(signals)),
                "signal_strength": sum(signal not in {"wiki_unobserved", "out_of_scope"} for signal in signals),
                "events": query_events,
            }
        )
    return records


def facet_text(record: dict[str, Any], *, include_structured: bool) -> str:
    if not include_structured:
        return str(record["text"])
    signals = " ".join(f"signal_{signal}" for signal in record["signals"])
    return f"intent {record['text']} {signals}".strip()


def cluster_metrics(records: list[dict[str, Any]], labels: np.ndarray, *, arm: str, elapsed_ms: float) -> dict[str, Any]:
    grouped: dict[int, list[int]] = defaultdict(list)
    for index, label in enumerate(labels.tolist()):
        if label >= 0:
            grouped[int(label)].append(index)
    actionable: list[list[int]] = []
    for members in grouped.values():
        users = {records[index]["user_id"] for index in members}
        positive_signals = sum(records[index]["signal_strength"] > 0 for index in members)
        signal_ratio = positive_signals / len(members) if members else 0.0
        # A Replit-style issue cluster must recur across users and have a
        # majority of evidence-bearing failure/fallback signals.
        if len(members) >= 2 and len(users) >= 2 and signal_ratio >= 0.5:
            actionable.append(members)
    covered = {records[index]["query_id"] for members in actionable for index in members}
    covered_positive = {query_id for query_id in covered if next(record for record in records if record["query_id"] == query_id)["gold_gap"]}
    contaminated = {query_id for query_id in covered if not next(record for record in records if record["query_id"] == query_id)["gold_gap"]}
    positive_ids = {record["query_id"] for record in records if record["gold_gap"]}
    action_member_count = sum(len(members) for members in actionable)
    purity = len(covered_positive) / action_member_count if action_member_count else 1.0
    replayable_candidates = 0
    for members in actionable:
        representative = max(members, key=lambda index: (records[index]["signal_strength"], records[index]["query_id"]))
        representative_events = records[representative]["events"]
        if mine_gap_candidates(representative_events):
            replayable_candidates += 1
    return {
        "arm": arm,
        "cluster_count": len(grouped),
        "noise_count": int(sum(labels < 0)),
        "actionable_cluster_count": len(actionable),
        "actionable_query_count": action_member_count,
        "positive_coverage": len(covered_positive) / len(positive_ids) if positive_ids else 0.0,
        "control_contamination_rate": len(contaminated) / action_member_count if action_member_count else 0.0,
        "actionable_cluster_purity": purity,
        "eval_candidate_count": len(actionable),
        "lineage_query_count": sum(len(set(records[index]["query_id"] for index in members)) for members in actionable),
        "eval_candidate_replayable_count": replayable_candidates,
        "eval_candidate_replay_rate": replayable_candidates / len(actionable) if actionable else 0.0,
        "encoding_and_clustering_ms": round(elapsed_ms, 3),
    }


def dbscan(vectors: np.ndarray, *, eps: float) -> np.ndarray:
    return DBSCAN(eps=eps, min_samples=2, metric="cosine", n_jobs=1).fit_predict(vectors)


def typed_signal_matrix(records: list[dict[str, Any]], weight: float) -> np.ndarray:
    categories = sorted({signal for record in records for signal in record["signals"]})
    return np.asarray(
        [[weight * float(category in record["signals"]) for category in categories] for record in records],
        dtype=np.float32,
    )


def run_arm(
    records: list[dict[str, Any]],
    *,
    arm: str,
    model: Any | None = None,
    typed_weight: float = 2.0,
) -> dict[str, Any]:
    started = time.perf_counter()
    if arm == "raw_lexical":
        texts = [facet_text(record, include_structured=False) for record in records]
        vectors = TfidfVectorizer(lowercase=True, ngram_range=(1, 2), min_df=1).fit_transform(texts).toarray()
        labels = dbscan(vectors, eps=0.35)
    elif arm == "facet_lexical":
        texts = [facet_text(record, include_structured=True) for record in records]
        vectors = TfidfVectorizer(lowercase=True, ngram_range=(1, 2), min_df=1).fit_transform(texts).toarray()
        labels = dbscan(vectors, eps=0.35)
    elif arm == "facet_typed_lexical":
        texts = [facet_text(record, include_structured=False) for record in records]
        text_vectors = TfidfVectorizer(lowercase=True, ngram_range=(1, 2), min_df=1).fit_transform(texts).toarray()
        vectors = np.hstack([text_vectors, typed_signal_matrix(records, typed_weight)])
        labels = dbscan(vectors, eps=0.30)
    elif arm == "raw_dense":
        if model is None:
            raise ValueError("dense arms require a sentence-transformers model")
        texts = [facet_text(record, include_structured=False) for record in records]
        vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        labels = dbscan(np.asarray(vectors), eps=0.30)
    elif arm == "facet_dense":
        if model is None:
            raise ValueError("dense arms require a sentence-transformers model")
        texts = [facet_text(record, include_structured=True) for record in records]
        vectors = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        labels = dbscan(np.asarray(vectors), eps=0.30)
    elif arm == "facet_typed_dense":
        if model is None:
            raise ValueError("dense arms require a sentence-transformers model")
        texts = [facet_text(record, include_structured=False) for record in records]
        text_vectors = np.asarray(model.encode(texts, normalize_embeddings=True, show_progress_bar=False))
        vectors = np.hstack([text_vectors, typed_signal_matrix(records, typed_weight)])
        labels = dbscan(vectors, eps=0.30)
    else:
        raise ValueError(f"unknown arm: {arm}")
    return cluster_metrics(records, labels, arm=arm, elapsed_ms=(time.perf_counter() - started) * 1000)


def baseline_metrics(events: list[dict[str, Any]], pages: list[Any], gold: list[dict[str, Any]]) -> dict[str, Any]:
    result = evaluate(events, pages, gold)
    return {
        "precision": result["precision"],
        "recall": result["recall"],
        "f1": result["f1"],
        "candidate_count": result["candidate_count"],
        "false_positive_count": result["false_positive_count"],
        "false_negative_count": result["false_negative_count"],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-stratum", type=int, default=20)
    parser.add_argument("--collision-count", type=int, default=20)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--typed-weight", type=float, default=2.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    events, pages, gold = build_factorial_cohort(args.per_stratum, args.collision_count)
    records = query_records(events, gold)
    model_started = time.perf_counter()
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(args.model)
    model_load_ms = (time.perf_counter() - model_started) * 1000
    arms = [
        run_arm(records, arm="raw_lexical"),
        run_arm(records, arm="facet_lexical"),
        run_arm(records, arm="facet_typed_lexical", typed_weight=args.typed_weight),
        run_arm(records, arm="raw_dense", model=model),
        run_arm(records, arm="facet_dense", model=model),
        run_arm(records, arm="facet_typed_dense", model=model, typed_weight=args.typed_weight),
    ]
    baseline = baseline_metrics(events, pages, gold)
    dense_dimension = int(model.get_sentence_embedding_dimension())
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "protocol": {
            "cohort": "wiki-gap-labeled-experiment-v1 plus exact-text success/unobserved controls",
            "per_stratum": args.per_stratum,
            "collision_count_each": args.collision_count,
            "clusterer": "DBSCAN cosine distance, min_samples=2",
            "raw_eps": 0.30,
            "facet_eps": 0.30,
            "typed_signal_weight": args.typed_weight,
            "actionable_cluster_rule": "at least 2 members, at least 2 users, and at least 50% evidence-bearing signals",
            "dense_model": args.model,
            "dense_dimension": dense_dimension,
        },
        "cohort_counts": {
            "event_count": len(events),
            "query_count": len(records),
            "positive_query_count": sum(record["gold_gap"] for record in records),
            "control_query_count": sum(not record["gold_gap"] for record in records),
        },
        "frankengate_deterministic_baseline": baseline,
        "replit_style_arms": arms,
        "model_load_ms": round(model_load_ms, 3),
        "interpretation": "The deterministic miner is the authoritative per-query detector. Replit-style facet clustering is evaluated as an issue-discovery and eval-candidate layer; it is not allowed to replace event-level evidence or make unsupported wiki-gap claims.",
        "claim_boundary": {
            "production_user_utility": False,
            "replit_internal_metrics_reproduced": False,
            "cluster_mechanics_measured": True,
            "compact_facet_ablation_measured": True,
            "candidate_lineage_measured": True,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
