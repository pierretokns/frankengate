#!/usr/bin/env python3
"""Bounded, deterministic proxies for query-expansion families.

This is intentionally *not* an implementation of QueryGym, ConvGQR, or SIRA.
It uses a small synthetic retrieval fixture to test the mechanics described in
the term-enrichment protocol: query-side keyword/pseudo-document/entity and
feedback expansion, conversational rewriting, and search-only document
enrichment.  The receipt contains no enterprise or model-quality claim.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-query-expansion-probe-v1"
TOKEN_RE = re.compile(r"[a-z][a-z0-9-]+")
STOP = {"a", "and", "by", "for", "how", "is", "last", "of", "the", "to", "what", "which"}


DOCS = [
    {"id": "d1", "name": "sales_order", "text": "sales order amount quarter revenue"},
    {"id": "d2", "name": "pipeline_forecast", "text": "pipeline forecast quarter probability revenue"},
    {"id": "d3", "name": "customer_account", "text": "customer account active region owner"},
    {"id": "d4", "name": "incident_register", "text": "incident severity response service"},
    {"id": "d5", "name": "renewal_forecast", "text": "renewal forecast quarter probability customer"},
    {"id": "d6", "name": "marketing_campaign", "text": "marketing campaign spend conversion quarter"},
]

# Approved search vocabulary.  These are deliberately scoped to this fixture
# and represent reviewed aliases, not guessed enterprise terminology.
ALIASES = {
    "bookings": {"sales", "order", "sales_order"},
    "booking": {"sales", "order", "sales_order"},
    "subscribers": {"customer", "account", "customer_account"},
    "subscriber": {"customer", "account", "customer_account"},
    "outages": {"incident", "service", "incident_register"},
    "outage": {"incident", "service", "incident_register"},
    "sev2": {"incident", "severity", "incident_register"},
    "commit": {"pipeline", "forecast", "pipeline_forecast"},
    "pipeline": {"pipeline", "forecast", "pipeline_forecast"},
    "renewals": {"renewal", "forecast", "renewal_forecast"},
}

# A small pseudo-document vocabulary.  It is intentionally generic and does
# not contain target IDs beyond the approved alias map above.
PSEUDO = {
    "bookings": {"commercial", "orders", "bookings", "revenue"},
    "subscribers": {"customer", "accounts", "active", "users"},
    "outages": {"service", "incident", "severity", "downtime"},
    "sev2": {"service", "incident", "severity", "response"},
    "commit": {"pipeline", "forecast", "probability", "quarter"},
    "renewals": {"renewal", "forecast", "customer", "quarter"},
}

CASES = [
    {"id": "q01", "query": "How many bookings by quarter?", "target": "d1", "kind": "alias"},
    {"id": "q02", "query": "How many subscribers are active?", "target": "d3", "kind": "alias"},
    {"id": "q03", "query": "How many Sev2 outages last quarter?", "target": "d4", "kind": "alias"},
    {"id": "q04", "query": "Show renewal forecast by quarter", "target": "d5", "kind": "alias"},
    {"id": "q05", "query": "Which system owns the commit forecast?", "target": "d2", "kind": "collision"},
    {"id": "q06", "query": "How much campaign spend this quarter?", "target": "d6", "kind": "exact"},
    {"id": "q07", "query": "Which system owns the pipeline forecast?", "target": "d2", "kind": "exact"},
    {"id": "q08", "query": "Which account owner changed last quarter?", "target": "d3", "kind": "conversation", "history": "Show active subscribers by region."},
    {"id": "q09", "query": "And what changed last quarter?", "target": "d2", "kind": "conversation", "history": "Which system owns the pipeline forecast?"},
    {"id": "q10", "query": "How many renewals did we forecast?", "target": "d5", "kind": "alias"},
    {"id": "q11", "query": "What was the response time for outages?", "target": "d4", "kind": "alias"},
    {"id": "q12", "query": "List customer accounts by region", "target": "d3", "kind": "exact"},
]


def stable_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def tokens(text: str) -> set[str]:
    return {token for token in TOKEN_RE.findall(text.lower()) if token not in STOP}


def score(query: str, document: dict[str, str]) -> float:
    query_tokens = tokens(query)
    doc_tokens = tokens(document["name"].replace("_", " ") + " " + document["text"])
    # Tiny BM25-like lexical proxy with a name bonus.  This is enough to expose
    # expansion effects while remaining transparent and deterministic.
    return sum(2.0 if token in document["name"] else 1.0 for token in query_tokens & doc_tokens)


def rank(query: str, documents: list[dict[str, str]]) -> list[str]:
    return [doc["id"] for doc in sorted(documents, key=lambda doc: (-score(query, doc), doc["id"]))]


def expand_keyword(query: str) -> str:
    extra = {item for token in tokens(query) for item in ALIASES.get(token, set())}
    return query + " " + " ".join(sorted(extra))


def expand_pseudo(query: str) -> str:
    extra = {item for token in tokens(query) for item in PSEUDO.get(token, set())}
    return query + " " + " ".join(sorted(extra))


def expand_entity(query: str) -> str:
    # Entity/answer expansion uses only the canonical entity hints in the
    # reviewed alias table, not target labels or gold answers.
    extra = {item for token in tokens(query) for item in ALIASES.get(token, set()) if "_" in item}
    return query + " " + " ".join(sorted(extra))


def expand_feedback(query: str, documents: list[dict[str, str]]) -> str:
    top = sorted(documents, key=lambda doc: (-score(query, doc), doc["id"]))[0]
    return query + " " + top["name"].replace("_", " ")


def rewrite_conv(case: dict[str, Any]) -> str:
    if case["kind"] != "conversation":
        return case["query"]
    # ConvGQR-style operation represented as a transparent history+follow-up
    # rewrite.  No learned model is claimed.
    return case["history"] + " " + case["query"]


def enrich_documents(documents: list[dict[str, str]]) -> list[dict[str, str]]:
    result = []
    for doc in documents:
        aliases = set()
        for surface, values in ALIASES.items():
            if doc["name"] in values:
                aliases.add(surface)
        result.append({**doc, "text": doc["text"] + " " + " ".join(sorted(aliases))})
    return result


def metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    first = [row["rank"].index(row["target"]) + 1 for row in rows]
    return {
        "cases": len(rows),
        "mrr": round(sum(1.0 / position for position in first) / len(first), 6),
        "recall_at_1": round(sum(position == 1 for position in first) / len(first), 6),
        "recall_at_3": round(sum(position <= 3 for position in first) / len(first), 6),
        "wrong_top1": sum(row["rank"][0] != row["target"] for row in rows),
    }


def run(output: Path) -> dict[str, Any]:
    arms = {
        "lexical": lambda case, docs: case["query"],
        "querygym_keyword": lambda case, docs: expand_keyword(case["query"]),
        "querygym_pseudo_document": lambda case, docs: expand_pseudo(case["query"]),
        "querygym_answer_entity": lambda case, docs: expand_entity(case["query"]),
        "querygym_corpus_feedback": lambda case, docs: expand_feedback(case["query"], docs),
        "convgqr_rewrite": lambda case, docs: rewrite_conv(case),
        "sira_document_enrichment": lambda case, docs: case["query"],
    }
    enriched = enrich_documents(DOCS)
    aggregate: dict[str, dict[str, Any]] = {}
    by_kind: dict[str, dict[str, dict[str, Any]]] = {}
    for arm, query_fn in arms.items():
        docs = enriched if arm == "sira_document_enrichment" else DOCS
        rows = []
        for case in CASES:
            query = query_fn(case, docs)
            rows.append({"id": case["id"], "kind": case["kind"], "target": case["target"], "query_sha256": stable_hash(query), "rank": rank(query, docs)})
        aggregate[arm] = metrics(rows)
        by_kind[arm] = {kind: metrics([row for row in rows if row["kind"] == kind]) for kind in sorted({case["kind"] for case in CASES})}
    result = {
        "schema_version": SCHEMA_VERSION,
        "fixture": {"documents": len(DOCS), "cases": len(CASES), "case_kinds": dict(Counter(case["kind"] for case in CASES)), "raw_fixture_committed": True, "fixture_sha256": stable_hash({"documents": DOCS, "cases": CASES})},
        "protocol": {"ranking": "deterministic lexical overlap with canonical-name bonus", "expansions": "reviewed fixture vocabulary and generic pseudo-document terms", "no_model_calls": True, "gold_targets_used_only_for_scoring": True},
        "aggregate": aggregate,
        "by_kind": by_kind,
        "claim_boundary": "Synthetic retrieval mechanics only. These are transparent proxies, not QueryGym/ConvGQR/SIRA implementations, and do not establish enterprise relevance, conversational quality, or production safety.",
    }
    result["result_sha256"] = stable_hash(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.output)
    print(json.dumps({"aggregate": result["aggregate"], "result_sha256": result["result_sha256"]}, sort_keys=True))
