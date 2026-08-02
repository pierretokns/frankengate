#!/usr/bin/env python3
"""Run a real embedding retrieval arm over the adapted State of AI corpus."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

from sentence_transformers import SentenceTransformer

from wiki_agentic_rag_benchmark import percentile, sha256


def document_text(page: dict[str, Any], compiled: bool) -> str:
    values = [page.get("title", ""), page.get("text", "")]
    if compiled:
        values.extend(page.get("aliases", []))
        values.append(page.get("source_id", ""))
        values.append(page.get("source_domain", ""))
    return " ".join(str(value) for value in values if value)


def run(data: dict[str, Any], model_name: str, sizes: list[int], k: int, compiled: bool) -> dict[str, Any]:
    model = SentenceTransformer(model_name, local_files_only=True)
    all_wikis = sorted({page["wiki_id"] for page in data["pages"]})
    all_questions = data["questions"]
    pages_by_id = {page["page_id"]: page for page in data["pages"]}
    page_texts = [document_text(page, compiled) for page in data["pages"]]
    build_started = time.perf_counter()
    embeddings = model.encode(page_texts, normalize_embeddings=True, show_progress_bar=False)
    build_ms = (time.perf_counter() - build_started) * 1000
    results: list[dict[str, Any]] = []
    for size in sizes:
        selected = set(all_wikis[:size])
        indexes = [index for index, page in enumerate(data["pages"]) if page["wiki_id"] in selected]
        pages = [data["pages"][index] for index in indexes]
        questions = [question for question in all_questions if not question["gold_page_ids"] or question["wiki_id"] in selected]
        queries = [question["question"] for question in questions]
        query_started = time.perf_counter()
        query_embeddings = model.encode(queries, normalize_embeddings=True, show_progress_bar=False)
        query_ms = (time.perf_counter() - query_started) * 1000
        rows: list[dict[str, Any]] = []
        for question, query_embedding in zip(questions, query_embeddings):
            started = time.perf_counter_ns()
            scores = embeddings[indexes] @ query_embedding
            order = sorted(range(len(scores)), key=lambda index: (-float(scores[index]), pages[index]["page_id"]))[:k]
            latency_ms = (time.perf_counter_ns() - started) / 1_000_000
            ranked = [pages[index] for index in order]
            gold = set(question["gold_page_ids"])
            top_ids = {page["page_id"] for page in ranked}
            rows.append({
                "question_id": question["question_id"],
                "gold": bool(gold),
                "recall_at_1": bool(ranked and ranked[0]["page_id"] in gold) if gold else None,
                "recall_at_k": bool(top_ids & gold) if gold else None,
                "mrr": next((1.0 / index for index, page in enumerate(ranked, start=1) if page["page_id"] in gold), 0.0) if gold else None,
                "wrong_wiki_at_1": bool(ranked and ranked[0]["wiki_id"] != question["wiki_id"]) if gold else None,
                "nil_false_positive": bool(ranked) if not gold else None,
                "latency_ms": latency_ms,
            })
        gold_rows = [row for row in rows if row["gold"]]
        nil_rows = [row for row in rows if not row["gold"]]
        results.append({
            "size": size,
            "compiled": compiled,
            "records": len(rows),
            "metrics": {
                "recall_at_1": sum(row["recall_at_1"] for row in gold_rows) / len(gold_rows) if gold_rows else 0.0,
                "recall_at_k": sum(row["recall_at_k"] for row in gold_rows) / len(gold_rows) if gold_rows else 0.0,
                "mrr": sum(row["mrr"] for row in gold_rows) / len(gold_rows) if gold_rows else 0.0,
                "wrong_wiki_at_1": sum(row["wrong_wiki_at_1"] for row in gold_rows) / len(gold_rows) if gold_rows else 0.0,
                "nil_false_positive_rate": sum(row["nil_false_positive"] for row in nil_rows) / len(nil_rows) if nil_rows else 0.0,
                "p50_search_ms": percentile([row["latency_ms"] for row in rows], 0.50),
                "p95_search_ms": percentile([row["latency_ms"] for row in rows], 0.95),
            },
            "embedding_build_ms": build_ms,
            "query_encoding_ms": query_ms,
        })
    return {"schema_version": "frankengate-stateofai-wiki-dense-benchmark-v1", "model": model_name, "compiled": compiled, "results": results}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--model", default="BAAI/bge-base-en-v1.5")
    parser.add_argument("--sizes", default="1,5,10,25")
    parser.add_argument("--k", type=int, default=20)
    parser.add_argument("--compiled", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.corpus.read_text(encoding="utf-8"))
    sizes = [int(value) for value in args.sizes.split(",") if value.strip()]
    result = run(data, args.model, sizes, args.k, args.compiled)
    result["corpus"] = {"sha256": sha256(args.corpus), "pages": len(data["pages"]), "wikis": len({page["wiki_id"] for page in data["pages"]})}
    result["claim_boundary"] = "Real State of AI wiki-export retrieval benchmark using a general BGE model. Gold labels are title/source identity, not answer correctness or enterprise user utility."
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"schema_version": result["schema_version"], "model": result["model"], "compiled": result["compiled"], "results": result["results"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
