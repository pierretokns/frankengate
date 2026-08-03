#!/usr/bin/env python3
"""Evaluate wiki-gap mining against a deterministic, labeled trace cohort.

The cohort is synthetic but operationally shaped: each case has a question,
wiki retrieval/evidence events, optional tool fallback or feedback, and a
gold gap disposition.  It is designed to test detector precision, recall,
category confusion, and fail-closed controls before using real enterprise
logs.  No model is used to create labels or score the detector.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from wiki_gap_miner import WikiPage, mine_gap_candidates


NOW = dt.datetime(2026, 8, 3, tzinfo=dt.timezone.utc)
STRATA = (
    "absent",
    "discoverability",
    "external_fallback",
    "incomplete",
    "stale",
    "contradiction",
    "success_control",
    "no_wiki_observation",
    "out_of_scope",
)
POSITIVE_STRATA = frozenset({"absent", "discoverability", "external_fallback", "incomplete", "stale", "contradiction"})


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


def build_cohort(per_stratum: int = 20, seed: int = 20260803) -> tuple[list[dict[str, Any]], list[WikiPage], list[dict[str, Any]]]:
    rng = random.Random(seed)
    events: list[dict[str, Any]] = []
    pages = [
        WikiPage("page-current", "Current procedure", NOW - dt.timedelta(days=5), ("current alias",), "gateway"),
        WikiPage("page-stale", "Old procedure", NOW - dt.timedelta(days=400), ("legacy alias",), "gateway"),
        WikiPage("page-contradiction-a", "Procedure A", NOW - dt.timedelta(days=10), (), "gateway"),
        WikiPage("page-contradiction-b", "Procedure B", NOW - dt.timedelta(days=10), (), "gateway"),
        WikiPage("page-alias", "Bedrock Federated Endpoint Key", NOW - dt.timedelta(days=5), ("BFEK",), "bedrock"),
    ]
    gold: list[dict[str, Any]] = []
    for stratum in STRATA:
        for index in range(per_stratum):
            query_id = f"{stratum}-{index:03d}"
            user_id = f"user-{rng.randrange(1, 8):02d}"
            text = {
                "absent": "How do I rotate the mantle key?",
                "discoverability": "How do I rotate a BFEK?",
                "external_fallback": "How do I inspect the mantle endpoint health?",
                "incomplete": "How do I deploy the gateway safely?",
                "stale": "How do I rotate the legacy gateway key?",
                "contradiction": "Which gateway procedure is authoritative?",
                "success_control": "Where is the current gateway runbook?",
                "no_wiki_observation": "What is the gateway maintenance window?",
                "out_of_scope": "What is the weather today?",
            }[stratum]
            events.append(_event(f"{query_id}-q", "question", query_id, user_id, text=text))
            if stratum == "no_wiki_observation":
                events.append(_event(f"{query_id}-o", "outcome", query_id, user_id, status="success"))
            elif stratum == "out_of_scope":
                events.append(_event(f"{query_id}-r", "retrieval", query_id, user_id, page_ids=[], wiki_search_attempted=True))
                events.append(_event(f"{query_id}-scope", "wiki_scope", query_id, user_id, scope_status="out_of_scope"))
            else:
                page_ids = {
                    "absent": [],
                    "discoverability": [],
                    "external_fallback": [],
                    "incomplete": ["page-current"],
                    "stale": ["page-stale"],
                    "contradiction": ["page-contradiction-a", "page-contradiction-b"],
                    "success_control": ["page-current"],
                }[stratum]
                events.append(_event(f"{query_id}-r", "retrieval", query_id, user_id, page_ids=page_ids, wiki_search_attempted=True))
                if stratum in {"absent", "discoverability", "external_fallback"}:
                    events.append(_event(f"{query_id}-a", "answer", query_id, user_id, answerable=False, confidence=0.2))
                else:
                    events.append(_event(f"{query_id}-a", "answer", query_id, user_id, answerable=True, confidence=0.9))
                if stratum == "external_fallback":
                    events.append(_event(f"{query_id}-t", "tool_call", query_id, user_id, tool="aws_cli", external=True))
                if stratum in {"stale", "contradiction"}:
                    events.append(_event(f"{query_id}-f", "feedback", query_id, user_id, kind="correction"))
                status = "failure" if stratum in POSITIVE_STRATA - {"stale", "contradiction"} else "success"
                events.append(_event(f"{query_id}-o", "outcome", query_id, user_id, status=status))
            gold.append({"query_id": query_id, "stratum": stratum, "gold_gap": stratum in POSITIVE_STRATA})

    # Explicit cross-user recurrence case, held outside the per-stratum counts.
    for suffix, user_id in (("a", "user-recurrence-a"), ("b", "user-recurrence-b")):
        query_id = f"recurring-{suffix}"
        events.extend(
            [
                _event(f"{query_id}-q", "question", query_id, user_id, text="How do I rotate the mantle key?"),
                _event(f"{query_id}-r", "retrieval", query_id, user_id, page_ids=[], wiki_search_attempted=True),
            ]
        )
        gold.append({"query_id": query_id, "stratum": "recurring", "gold_gap": True})
    return events, pages, gold


def evaluate(events: list[dict[str, Any]], pages: list[WikiPage], gold: list[dict[str, Any]]) -> dict[str, Any]:
    candidates = mine_gap_candidates(events, pages, now=NOW)
    by_query: dict[str, list[str]] = defaultdict(list)
    for candidate in candidates:
        for query_id in candidate.query_ids:
            by_query[query_id].append(candidate.gap_type)
    labels = {row["query_id"]: row for row in gold}
    predicted_positive = {query_id for query_id, types in by_query.items() if types}
    actual_positive = {query_id for query_id, row in labels.items() if row["gold_gap"]}
    true_positive = predicted_positive & actual_positive
    false_positive = predicted_positive - actual_positive
    false_negative = actual_positive - predicted_positive
    precision = len(true_positive) / len(predicted_positive) if predicted_positive else 0.0
    recall = len(true_positive) / len(actual_positive) if actual_positive else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    category_recall: dict[str, float] = {}
    for stratum in STRATA:
        expected = {query_id for query_id, row in labels.items() if row["stratum"] == stratum}
        observed = expected & predicted_positive
        category_recall[stratum] = len(observed) / len(expected) if expected else 0.0
    return {
        "schema_version": "frankengate-wiki-gap-labeled-experiment-v1",
        "seed": 20260803,
        "gold_query_count": len(gold),
        "candidate_count": len(candidates),
        "predicted_positive_count": len(predicted_positive),
        "actual_positive_count": len(actual_positive),
        "true_positive_count": len(true_positive),
        "false_positive_count": len(false_positive),
        "false_negative_count": len(false_negative),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "category_recall": category_recall,
        "predicted_types": dict(Counter(type_name for candidate in candidates for type_name in [candidate.gap_type])),
        "false_positive_query_ids": sorted(false_positive),
        "false_negative_query_ids": sorted(false_negative),
        "interpretation": "This is a deterministic detector evaluation; frontier adjudication and human labels remain required for production promotion.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--per-stratum", type=int, default=20)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    events, pages, gold = build_cohort(args.per_stratum)
    result = evaluate(events, pages, gold)
    result["event_count"] = len(events)
    result["strata"] = list(STRATA)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
