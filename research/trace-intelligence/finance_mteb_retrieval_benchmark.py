#!/usr/bin/env python3
"""Run a reproducible FinanceBench retrieval comparison.

The benchmark is deliberately storage-independent.  It compares lexical TF-IDF
against pinned embedding models on the same cached FinanceMTEB/FinanceBench
corpus and qrels.  No source text or vectors are written to the repository;
only aggregate metrics, model revisions, and input hashes are emitted.

This is a relevance gate, not an authorization or Aurora benchmark.  RLS,
classification, deletion, latency-at-scale, and cost must be measured by the
separate governed PostgreSQL experiments before a model or index is promoted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import platform
import sys
import time
from typing import Any, Iterable


SCHEMA_VERSION = "frankengate-finance-mteb-retrieval-v1"
DATASET_ID = "FinanceMTEB/FinanceBench"
DATASET_REVISION = "4738010357e3dda4b337abbde86d5b36c3118c8f"
DEFAULT_MODELS = (
    "BalyasnyAI/multilingual-e5-base",
    "Qwen/Qwen3-Embedding-0.6B",
)
MODEL_LICENSES = {
    "BalyasnyAI/multilingual-e5-base": "apache-2.0",
    "Qwen/Qwen3-Embedding-0.6B": "apache-2.0",
}


def file_sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_arrow(path: pathlib.Path) -> list[dict[str, Any]]:
    """Read a Hugging Face Arrow stream without rebuilding or mutating caches."""
    import pyarrow as pa
    import pyarrow.ipc as ipc

    with pa.memory_map(str(path), "r") as source:
        return ipc.open_stream(source).read_all().to_pylist()


def _metrics(
    scores: Any,
    *,
    query_ids: list[str],
    document_ids: list[str],
    relevant: dict[str, set[str]],
    method: str,
) -> dict[str, Any]:
    """Calculate binary Recall@k and MRR, preserving multi-positive qrels."""
    # Keep the metric lane dependency-light.  The benchmark's production
    # embedding path uses NumPy, but ranking and qrel scoring do not need it;
    # accepting nested lists and array-like rows also makes the fixture test
    # runnable in the minimal reproducibility environment.
    order = [
        sorted(range(len(row)), key=lambda index: (-float(row[index]), index))
        for row in scores
    ]
    reciprocal_ranks: list[float] = []
    recalls: dict[int, list[float]] = {k: [] for k in (1, 5, 10, 20)}
    for row, query_id in enumerate(query_ids):
        positives = relevant[query_id]
        ranked = [document_ids[index] for index in order[row]]
        positive_positions = [position for position, doc_id in enumerate(ranked, 1) if doc_id in positives]
        reciprocal_ranks.append(1.0 / positive_positions[0] if positive_positions else 0.0)
        for k in recalls:
            recalls[k].append(float(bool(set(ranked[:k]) & positives)))
    result: dict[str, Any] = {
        "method": method,
        "queries": len(query_ids),
        "relevant_query_count": len(relevant),
        "mrr": sum(reciprocal_ranks) / len(reciprocal_ranks),
    }
    result.update({f"recall@{k}": sum(values) / len(values) for k, values in recalls.items()})
    return result


def _embed(model_id: str, queries: list[str], documents: list[str]) -> tuple[Any, Any, dict[str, Any]]:
    """Encode from a locally cached snapshot; network downloads are forbidden."""
    from huggingface_hub import snapshot_download
    from sentence_transformers import SentenceTransformer

    snapshot = pathlib.Path(snapshot_download(model_id, local_files_only=True))
    model = SentenceTransformer(str(snapshot), local_files_only=True)
    if "multilingual-e5" in model_id.lower():
        query_inputs = [f"query: {value}" for value in queries]
        document_inputs = [f"passage: {value}" for value in documents]
    else:
        query_inputs = queries
        document_inputs = documents
    started = time.perf_counter()
    document_vectors = model.encode(
        document_inputs,
        normalize_embeddings=True,
        batch_size=8,
        show_progress_bar=False,
    )
    query_vectors = model.encode(
        query_inputs,
        normalize_embeddings=True,
        batch_size=8,
        show_progress_bar=False,
    )
    return query_vectors, document_vectors, {
        "model_id": model_id,
        "license": MODEL_LICENSES.get(model_id),
        "snapshot_revision": snapshot.name,
        "embedding_dimension": int(document_vectors.shape[1]),
        "encode_seconds": time.perf_counter() - started,
        "input_prefix": "query:/passage:" if "multilingual-e5" in model_id.lower() else "model-default",
    }


def run(
    *,
    corpus_path: pathlib.Path,
    queries_path: pathlib.Path,
    qrels_path: pathlib.Path,
    model_ids: Iterable[str],
    max_document_characters: int | None = None,
    max_query_characters: int | None = None,
) -> dict[str, Any]:
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.preprocessing import normalize
    import pyarrow
    import sentence_transformers
    import sklearn
    import torch
    import transformers

    corpus = read_arrow(corpus_path)
    queries = read_arrow(queries_path)
    qrels = read_arrow(qrels_path)
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
    original_documents = documents
    original_queries = query_texts
    if max_document_characters is not None:
        documents = [value[:max_document_characters] for value in documents]
    if max_query_characters is not None:
        query_texts = [value[:max_query_characters] for value in query_texts]

    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        sublinear_tf=True,
        strip_accents="unicode",
        min_df=1,
    )
    document_matrix = normalize(vectorizer.fit_transform(documents))
    query_matrix = normalize(vectorizer.transform(query_texts))
    lexical_scores = (query_matrix @ document_matrix.T).toarray()
    arms = [_metrics(lexical_scores, query_ids=query_ids, document_ids=document_ids, relevant=relevant, method="tfidf_unigram_bigram")]

    model_receipts: list[dict[str, Any]] = []
    for model_id in model_ids:
        query_vectors, document_vectors, receipt = _embed(model_id, query_texts, documents)
        dense_scores = np.asarray(query_vectors @ document_vectors.T)
        metric = _metrics(dense_scores, query_ids=query_ids, document_ids=document_ids, relevant=relevant, method=model_id)
        metric["model"] = receipt
        arms.append(metric)
        model_receipts.append(receipt)

    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_revision": "financebench-embedding-choice-v1",
        "dataset": {
            "id": DATASET_ID,
            "revision": DATASET_REVISION,
            "license_declared_by_cached_dataset_info": None,
            "projection": {
                "document_max_characters": max_document_characters,
                "query_max_characters": max_query_characters,
                "documents_truncated": sum(len(value) > max_document_characters for value in original_documents) if max_document_characters is not None else 0,
                "queries_truncated": sum(len(value) > max_query_characters for value in original_queries) if max_query_characters is not None else 0,
            },
            "corpus_rows": len(corpus),
            "query_rows": len(queries),
            "qrel_rows": len(qrels),
            "evaluated_queries": len(query_ids),
            "multi_positive_queries": sum(len(values) > 1 for values in relevant.values()),
            "corpus_sha256": file_sha256(corpus_path),
            "queries_sha256": file_sha256(queries_path),
            "qrels_sha256": file_sha256(qrels_path),
        },
        "runtime": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "numpy": np.__version__,
            "pyarrow": pyarrow.__version__,
            "scikit_learn": sklearn.__version__,
            "sentence_transformers": sentence_transformers.__version__,
            "torch": torch.__version__,
            "transformers": transformers.__version__,
        },
        "arms": arms,
        "model_receipts": model_receipts,
        "policy": {
            "raw_text_committed": False,
            "vectors_committed": False,
            "local_files_only": True,
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
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--summary", type=pathlib.Path, required=True)
    parser.add_argument("--model", action="append", dest="models", default=None)
    parser.add_argument("--max-document-characters", type=int, default=None)
    parser.add_argument("--max-query-characters", type=int, default=None)
    args = parser.parse_args()
    result = run(
        corpus_path=args.corpus,
        queries_path=args.queries,
        qrels_path=args.qrels,
        model_ids=args.models or DEFAULT_MODELS,
        max_document_characters=args.max_document_characters,
        max_query_characters=args.max_query_characters,
    )
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# FinanceBench embedding-choice benchmark (bounded)",
        "",
        f"Pinned `{DATASET_ID}` revision `{DATASET_REVISION}`: {result['dataset']['corpus_rows']} corpus documents, {result['dataset']['evaluated_queries']} evaluated queries, and {result['dataset']['qrel_rows']} qrels.",
        "",
        "This is a relevance-only comparison. It does not prove RLS, deletion, Aurora scale, or enterprise transfer.",
        "",
        "| arm | MRR | Recall@1 | Recall@5 | Recall@10 | Recall@20 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm in result["arms"]:
        lines.append(
            f"| {arm['method']} | {arm['mrr']:.4f} | {arm['recall@1']:.4f} | {arm['recall@5']:.4f} | {arm['recall@10']:.4f} | {arm['recall@20']:.4f} |"
        )
    lines.extend([
        "",
        "The promotion gate remains closed until the winning model is replayed with governed candidate filtering, deletion closure, hard-negative labels, and held-out transfer.",
    ])
    args.summary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
