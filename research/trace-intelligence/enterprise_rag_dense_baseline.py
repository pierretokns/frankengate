#!/usr/bin/env python3
"""Stream a local sentence-transformer dense baseline over EnterpriseRAG-Bench."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq
from sentence_transformers import SentenceTransformer


SCHEMA_VERSION = "frankengate-enterprise-rag-dense-baseline-v1"
MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def representation(row: dict[str, Any], mode: str) -> str:
    if mode == "title":
        return f"source_type: {row['source_type']}\ntitle: {row['title'] or ''}"
    return f"source_type: {row['source_type']}\ntitle: {row['title'] or ''}\ncontent: {(row['content'] or '')[:256]}"


def metric(ranked: list[str], expected: set[str], k: int) -> dict[str, float]:
    top = ranked[:k]
    hits = [index for index, doc_id in enumerate(ranked, start=1) if doc_id in expected]
    return {"mrr": 1.0 / hits[0] if hits else 0.0, f"recall_at_{k}": float(bool(set(top) & expected))}


def run(documents: Path, questions: Path, model_path: Path, output: Path, *, batch_size: int = 256, top_k: int = 20, representation_mode: str = "title_snippet") -> dict[str, Any]:
    model = SentenceTransformer(str(model_path), device="cpu")
    question_rows = [row for row in pq.read_table(questions).to_pylist() if row["question_type"] == "semantic"]
    query_vectors = model.encode([row["question"] for row in question_rows], batch_size=64, normalize_embeddings=True, show_progress_bar=False).astype(np.float32)
    top_scores = np.full((len(question_rows), top_k), -np.inf, dtype=np.float32)
    top_ids: list[list[str]] = [[""] * top_k for _ in question_rows]
    document_count = 0
    for batch_index, batch in enumerate(pq.ParquetFile(documents).iter_batches(batch_size=batch_size), start=1):
        rows = batch.to_pylist()
        vectors = model.encode([representation(row, representation_mode) for row in rows], batch_size=64, normalize_embeddings=True, show_progress_bar=False).astype(np.float32)
        scores = query_vectors @ vectors.T
        ids = [str(row["doc_id"]) for row in rows]
        for query_index in range(len(question_rows)):
            combined_scores = np.concatenate((top_scores[query_index], scores[query_index]))
            combined_ids = top_ids[query_index] + ids
            keep = np.argpartition(combined_scores, -top_k)[-top_k:]
            keep = keep[np.argsort(combined_scores[keep])[::-1]]
            top_scores[query_index] = combined_scores[keep]
            top_ids[query_index] = [combined_ids[index] for index in keep]
        document_count += len(rows)
        if batch_index % 100 == 0:
            print(json.dumps({"batches": batch_index, "documents": document_count}), flush=True)
    rows: list[dict[str, Any]] = []
    for index, question in enumerate(question_rows):
        expected = set(question["expected_doc_ids"] or [])
        ranked = top_ids[index]
        rows.append({"question_id": question["question_id"], "question_type": question["question_type"], "mrr": metric(ranked, expected, top_k)["mrr"], "recall_at_1": metric(ranked, expected, 1)["recall_at_1"], "recall_at_5": metric(ranked, expected, 5)["recall_at_5"], "recall_at_10": metric(ranked, expected, 10)["recall_at_10"], "recall_at_20": metric(ranked, expected, 20)["recall_at_20"]})
    fields = ("mrr", "recall_at_1", "recall_at_5", "recall_at_10", "recall_at_20")
    aggregate = {field: round(sum(float(row[field]) for row in rows) / len(rows), 6) for field in fields} if rows else {}
    result = {
        "schema_version": SCHEMA_VERSION,
        "source": {"documents_sha256": sha256(documents), "questions_sha256": sha256(questions), "model_id": MODEL_ID, "model_path_external": True, "raw_texts_and_vectors_committed": False},
        "dataset": {"question_type": "semantic", "questions": len(question_rows), "documents": document_count, "representation": representation_mode, "top_k": top_k},
        "protocol": {"embedding_model": MODEL_ID, "device": "cpu", "normalized_cosine": True, "document_batch_size": batch_size, "candidate_generation": "full-corpus streaming dense similarity"},
        "arms": {"dense_full_corpus": aggregate},
        "claim_boundary": {"dense_retrieval_measured": True, "custom_embedding_measured": False, "frontier_reranking_measured": False, "ontology_quality_measured": False, "trace_learning_measured": False, "reason": "Public synthetic document corpus and semantic questions only; no corporate aliases, principals, authority epochs, or changed-system outcomes."},
    }
    result["result_sha256"] = stable_hash(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["arms"], sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--documents", type=Path, required=True)
    parser.add_argument("--questions", type=Path, required=True)
    parser.add_argument("--model-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--representation", choices=("title", "title_snippet"), default="title_snippet")
    args = parser.parse_args()
    run(args.documents, args.questions, args.model_path, args.output, batch_size=args.batch_size, top_k=args.top_k, representation_mode=args.representation)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
