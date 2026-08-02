#!/usr/bin/env python3
"""Measure a structured identifier reranker on top of BGE candidate recall."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from wiki_agentic_rag_benchmark import percentile, sha256, tokens


def text(page: dict[str, Any]) -> str:
    return " ".join(str(value) for value in [page.get("title", ""), page.get("text", ""), *page.get("aliases", []), page.get("source_id", ""), page.get("source_domain", "")] if value)


def rerank_score(query: str, page: dict[str, Any], dense: float) -> float:
    query_lower = query.lower()
    page_id = str(page.get("source_id", "")).lower()
    qtokens = set(tokens(query))
    ptokens = set(tokens(text(page)))
    overlap = len(qtokens & ptokens) / len(qtokens) if qtokens else 0.0
    exact_id = 2.0 if page_id and page_id in query_lower else 0.0
    return float(dense) + 1.5 * overlap + exact_id


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--model", default="BAAI/bge-base-en-v1.5")
    parser.add_argument("--sizes", default="1,5,10,25")
    parser.add_argument("--k", type=int, default=20)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    from sentence_transformers import SentenceTransformer

    data = json.loads(args.corpus.read_text(encoding="utf-8"))
    model = SentenceTransformer(args.model, local_files_only=True)
    all_wikis = sorted({page["wiki_id"] for page in data["pages"]})
    pages_by_id = {page["page_id"]: page for page in data["pages"]}
    pages = data["pages"]
    embeddings = model.encode([text(page) for page in pages], normalize_embeddings=True, show_progress_bar=False)
    results: list[dict[str, Any]] = []
    for size in [int(value) for value in args.sizes.split(",") if value.strip()]:
        selected = set(all_wikis[:size])
        indexes = [index for index, page in enumerate(pages) if page["wiki_id"] in selected]
        questions = [question for question in data["questions"] if not question["gold_page_ids"] or question["wiki_id"] in selected]
        query_embeddings = model.encode([question["question"] for question in questions], normalize_embeddings=True, show_progress_bar=False)
        rows: list[dict[str, Any]] = []
        for question, query_embedding in zip(questions, query_embeddings):
            dense_scores = embeddings[indexes] @ query_embedding
            candidates = sorted(indexes, key=lambda index: (-float(dense_scores[indexes.index(index)]), pages[index]["page_id"]))[:args.k]
            reranked = sorted(candidates, key=lambda index: (-rerank_score(question["question"], pages[index], float(dense_scores[indexes.index(index)])), pages[index]["page_id"]))
            gold = set(question["gold_page_ids"])
            ranked_pages = [pages[index] for index in reranked]
            rows.append({"gold": bool(gold), "recall_at_1": bool(ranked_pages and ranked_pages[0]["page_id"] in gold) if gold else None, "recall_at_k": bool(gold & {page["page_id"] for page in ranked_pages}) if gold else None, "mrr": next((1.0 / rank for rank, page in enumerate(ranked_pages, 1) if page["page_id"] in gold), 0.0) if gold else None, "nil_false_positive": bool(ranked_pages) if not gold else None})
        gold_rows = [row for row in rows if row["gold"]]
        nil_rows = [row for row in rows if not row["gold"]]
        results.append({"size": size, "records": len(rows), "metrics": {"recall_at_1": sum(row["recall_at_1"] for row in gold_rows) / len(gold_rows), "recall_at_k": sum(row["recall_at_k"] for row in gold_rows) / len(gold_rows), "mrr": sum(row["mrr"] for row in gold_rows) / len(gold_rows), "nil_false_positive_rate": sum(row["nil_false_positive"] for row in nil_rows) / len(nil_rows) if nil_rows else 0.0}})
    result = {"schema_version": "frankengate-stateofai-wiki-identifier-reranker-v1", "model": args.model, "corpus": {"sha256": sha256(args.corpus), "pages": len(pages), "wikis": len(all_wikis)}, "results": results, "claim_boundary": "Structured identifier/metadata reranking over BGE candidates on source-identity labels. Not answer quality, enterprise utility, or a learned corporate embedding."}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"schema_version": result["schema_version"], "results": results}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
