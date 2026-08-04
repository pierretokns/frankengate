#!/usr/bin/env python3
"""Run the FinanceBench relevance gate through Ollama's local embedding API.

This is a separate harness from the Hugging Face/SentenceTransformers runner.
The endpoint is required to be loopback-only, and the result stores aggregate
metrics plus request timing—not source text, vectors, or credentials.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import time
from typing import Any
from urllib.request import Request, urlopen

import finance_mteb_retrieval_benchmark as benchmark


SCHEMA_VERSION = "frankengate-finance-mteb-ollama-retrieval-v1"
DEFAULT_MODEL = "nomic-embed-text:latest"
DEFAULT_ENDPOINT = "http://127.0.0.1:11434"
MAX_DOCUMENT_CHARACTERS = 2500
MAX_QUERY_CHARACTERS = 2000


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def embed(
    *,
    endpoint: str,
    model: str,
    texts: list[str],
    prefix: str,
    batch_size: int = 16,
) -> tuple[list[list[float]], dict[str, Any]]:
    if not endpoint.startswith("http://127.0.0.1:") and not endpoint.startswith("http://localhost:"):
        raise ValueError("Ollama endpoint must be loopback-only")
    vectors: list[list[float]] = []
    request_count = 0
    started = time.perf_counter()
    for offset in range(0, len(texts), batch_size):
        payload = {
            "model": model,
            "input": [prefix + text for text in texts[offset : offset + batch_size]],
        }
        request = Request(
            endpoint.rstrip("/") + "/api/embed",
            data=_canonical(payload),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=180) as response:
            value = json.loads(response.read())
        batch = value.get("embeddings")
        if not isinstance(batch, list) or len(batch) != len(payload["input"]):
            raise RuntimeError("Ollama returned an unexpected embedding batch")
        vectors.extend([[float(item) for item in row] for row in batch])
        request_count += 1
    dimensions = {len(row) for row in vectors}
    if len(dimensions) != 1:
        raise RuntimeError("Ollama returned inconsistent embedding dimensions")
    return vectors, {
        "endpoint_scope": "loopback-only",
        "model_id": model,
        "embedding_dimension": next(iter(dimensions)),
        "request_count": request_count,
        "batch_size": batch_size,
        "encode_seconds": time.perf_counter() - started,
        "query_prefix": "search_query: ",
        "document_prefix": "search_document: ",
    }


def run(
    *,
    corpus_path: pathlib.Path,
    queries_path: pathlib.Path,
    qrels_path: pathlib.Path,
    endpoint: str,
    model: str,
) -> dict[str, Any]:
    import numpy as np

    corpus = benchmark.read_arrow(corpus_path)
    queries = benchmark.read_arrow(queries_path)
    qrels = benchmark.read_arrow(qrels_path)
    corpus_by_id = {str(row["_id"]): row for row in corpus}
    query_by_id = {str(row["_id"]): row for row in queries}
    relevant: dict[str, set[str]] = {}
    for row in qrels:
        if float(row.get("score", 0)) > 0:
            relevant.setdefault(str(row["query-id"]), set()).add(str(row["corpus-id"]))
    query_ids = [query_id for query_id in query_by_id if query_id in relevant]
    document_ids = list(corpus_by_id)
    documents = [str(corpus_by_id[doc_id].get("title", "")) + "\n" + str(corpus_by_id[doc_id]["text"]) for doc_id in document_ids]
    query_texts = [str(query_by_id[query_id]["text"]) for query_id in query_ids]
    # nomic-embed-text's local context is smaller than the HF transformer
    # wrapper's tokenizer window for a few long filings.  Apply a deterministic
    # projection and record it; silently dropping long documents would make the
    # harness result incomparable and non-reproducible.
    projected_documents = [text[:MAX_DOCUMENT_CHARACTERS] for text in documents]
    projected_queries = [text[:MAX_QUERY_CHARACTERS] for text in query_texts]
    query_vectors, query_receipt = embed(
        endpoint=endpoint,
        model=model,
        texts=projected_queries,
        prefix="search_query: ",
    )
    document_vectors, document_receipt = embed(
        endpoint=endpoint,
        model=model,
        texts=projected_documents,
        prefix="search_document: ",
    )
    scores = np.asarray(query_vectors) @ np.asarray(document_vectors).T
    metrics = benchmark._metrics(
        scores,
        query_ids=query_ids,
        document_ids=document_ids,
        relevant=relevant,
        method=f"ollama:{model}",
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_revision": "financebench-ollama-embedding-choice-v1",
        "dataset": {
            "id": benchmark.DATASET_ID,
            "revision": benchmark.DATASET_REVISION,
            "corpus_rows": len(corpus),
            "query_rows": len(queries),
            "qrel_rows": len(qrels),
            "evaluated_queries": len(query_ids),
            "multi_positive_queries": sum(len(values) > 1 for values in relevant.values()),
            "corpus_sha256": benchmark.file_sha256(corpus_path),
            "queries_sha256": benchmark.file_sha256(queries_path),
            "qrels_sha256": benchmark.file_sha256(qrels_path),
            "projection": {
                "document_max_characters": MAX_DOCUMENT_CHARACTERS,
                "query_max_characters": MAX_QUERY_CHARACTERS,
                "documents_truncated": sum(len(value) > MAX_DOCUMENT_CHARACTERS for value in documents),
                "queries_truncated": sum(len(value) > MAX_QUERY_CHARACTERS for value in query_texts),
            },
        },
        "arm": metrics,
        "model": {
            "endpoint": endpoint,
            "endpoint_scope": "loopback-only",
            "model_id": model,
            "query_receipt": query_receipt,
            "document_receipt": document_receipt,
        },
        "policy": {
            "raw_text_committed": False,
            "vectors_committed": False,
            "authorization_evaluated": False,
            "promotion_requires": [
                "same-corpus governed RLS/deletion replay",
                "independent enterprise hard-negative labels",
                "held-out transfer and latency/cost receipts",
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=pathlib.Path, required=True)
    parser.add_argument("--queries", type=pathlib.Path, required=True)
    parser.add_argument("--qrels", type=pathlib.Path, required=True)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--summary", type=pathlib.Path, required=True)
    args = parser.parse_args()
    result = run(
        corpus_path=args.corpus,
        queries_path=args.queries,
        qrels_path=args.qrels,
        endpoint=args.endpoint,
        model=args.model,
    )
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    arm = result["arm"]
    args.summary.write_text(
        "\n".join(
            [
                "# FinanceBench Ollama embedding-harness benchmark (bounded)",
                "",
                f"Pinned `{benchmark.DATASET_ID}` revision `{benchmark.DATASET_REVISION}`: {result['dataset']['corpus_rows']} corpus documents and {result['dataset']['evaluated_queries']} evaluated queries.",
                "",
                "| arm | MRR | Recall@1 | Recall@5 | Recall@10 | Recall@20 |",
                "| --- | ---: | ---: | ---: | ---: | ---: |",
                f"| {arm['method']} | {arm['mrr']:.4f} | {arm['recall@1']:.4f} | {arm['recall@5']:.4f} | {arm['recall@10']:.4f} | {arm['recall@20']:.4f} |",
                "",
                "This is a loopback Ollama relevance run, not an authorization, deletion, Aurora, or promotion result.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": "ok", "arm": arm}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
