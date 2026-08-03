#!/usr/bin/env python3
"""Faithful, bounded implementation of Oracle ACL 2025 hard-negative mining.

This is the neural counterpart to ``enterprise_hard_negative_mining.py``. It
uses the six model families listed in Table 7 of the paper, concatenates their
normalized embeddings, fits PCA at 95% variance, applies the two published
distance inequalities, and optionally trains a cross-encoder with the paper's
margin triplet loss. The input/output contract is deliberately small so public
fixtures can be run without committing raw corpora.

The paper leaves pooling, normalization, PCA fit scope, and several training
hyperparameters under-specified. Those choices are recorded in the receipt;
the script must not be described as an exact numerical reproduction without
Oracle's private corpus/configuration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
from sentence_transformers import CrossEncoder, SentenceTransformer
from sklearn.decomposition import PCA
from sklearn.preprocessing import normalize


PAPER_EMBEDDING_MODELS: tuple[str, ...] = (
    "dunzhang/stella_en_400M_v5",
    "jinaai/jina-embeddings-v3",
    "mixedbread-ai/mxbai-embed-large-v1",
    "BAAI/bge-large-en-v1.5",
    "sentence-transformers/LaBSE",
    "sentence-transformers/all-mpnet-base-v2",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def page_text(page: dict[str, Any]) -> str:
    values = [page.get("title", ""), *(page.get("aliases") or []), page.get("text", "")]
    return " ".join(str(value) for value in values if value)


def stable_order(page_id: str, seed: int) -> str:
    return hashlib.sha256(f"{seed}:{page_id}".encode("utf-8")).hexdigest()


def bounded_pages(all_pages: Sequence[dict[str, Any]], required: set[str], limit: int, seed: int) -> list[dict[str, Any]]:
    required_pages = [page for page in all_pages if str(page.get("page_id")) in required]
    if len(required_pages) > limit:
        raise ValueError(f"candidate limit {limit} is below required positives {len(required_pages)}")
    rest = [page for page in all_pages if str(page.get("page_id")) not in required]
    rest.sort(key=lambda page: stable_order(str(page.get("page_id")), seed))
    return required_pages + rest[: limit - len(required_pages)]


def cosine_distance(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    left = normalize(np.asarray(left, dtype=np.float32).reshape(1, -1))[0]
    right_array = np.asarray(right, dtype=np.float32)
    right = normalize(right_array.reshape(1, -1) if right_array.ndim == 1 else right_array)
    return 1.0 - right @ left


def select_hard_negative(query: np.ndarray, positive: np.ndarray, candidates: np.ndarray, candidate_ids: Sequence[str]) -> str | None:
    """Apply equations (5) and (6), returning the closest valid candidate."""
    q_dist = cosine_distance(query, candidates)
    p_dist = cosine_distance(positive, candidates)
    positive_distance = float(cosine_distance(query, positive)[0])
    valid = [
        index
        for index, candidate_distance in enumerate(q_dist)
        if candidate_distance < positive_distance and candidate_distance < p_dist[index]
    ]
    if not valid:
        return None
    index = min(valid, key=lambda candidate_index: (float(q_dist[candidate_index]), str(candidate_ids[candidate_index])))
    return str(candidate_ids[index])


def encode(model: SentenceTransformer, texts: Sequence[str], role: str, batch_size: int, max_seq_length: int | None) -> np.ndarray:
    if max_seq_length is not None:
        model.max_seq_length = max_seq_length
    method = getattr(model, f"encode_{role}", None)
    if callable(method):
        values = method(list(texts), batch_size=batch_size, normalize_embeddings=True, show_progress_bar=False)
    else:
        values = model.encode(list(texts), batch_size=batch_size, normalize_embeddings=True, show_progress_bar=False)
    return np.asarray(values, dtype=np.float32)


@dataclass
class Ensemble:
    model_ids: tuple[str, ...]
    pca: PCA
    query_vectors: dict[str, np.ndarray]
    document_vectors: np.ndarray
    document_ids: list[str]


def fit_ensemble(pages: Sequence[dict[str, Any]], queries: Sequence[str], model_ids: Sequence[str], *, device: str, batch_size: int, max_seq_length: int | None, local_files_only: bool, trust_remote_code: bool) -> tuple[Ensemble, list[dict[str, Any]]]:
    documents = [page_text(page) for page in pages]
    document_parts: list[np.ndarray] = []
    query_parts: dict[str, list[np.ndarray]] = {query: [] for query in queries}
    model_receipts: list[dict[str, Any]] = []
    for model_id in model_ids:
        started = time.perf_counter()
        # Stella's custom implementation defaults to xformers-backed memory
        # efficient attention.  The model card documents a CPU-compatible path
        # that disables those two optimizations; use it only for Stella so the
        # faithful checkpoint is not silently dropped on a CPU host.
        config_kwargs = None
        if "stella_en_400M_v5" in model_id and device == "cpu":
            config_kwargs = {"use_memory_efficient_attention": False, "unpad_inputs": False}
        model = SentenceTransformer(
            model_id,
            device=device,
            local_files_only=local_files_only,
            trust_remote_code=trust_remote_code,
            config_kwargs=config_kwargs,
        )
        doc_vectors = encode(model, documents, "document", batch_size, max_seq_length)
        query_vectors = encode(model, list(query_parts), "query", batch_size, max_seq_length)
        document_parts.append(doc_vectors)
        for query, vector in zip(query_parts, query_vectors):
            query_parts[query].append(vector)
        model_receipts.append({
            "model_id": model_id,
            "embedding_dimension": int(doc_vectors.shape[1]),
            "elapsed_seconds": round(time.perf_counter() - started, 3),
            "device": device,
        })
        del model
    documents_concat = normalize(np.concatenate(document_parts, axis=1))
    queries_concat = {query: normalize(np.concatenate(parts).reshape(1, -1))[0] for query, parts in query_parts.items()}
    pca = PCA(n_components=0.95, svd_solver="full", random_state=0)
    documents_pca = normalize(pca.fit_transform(documents_concat))
    queries_pca = {query: normalize(pca.transform(vector.reshape(1, -1)))[0] for query, vector in queries_concat.items()}
    return Ensemble(tuple(model_ids), pca, queries_pca, documents_pca, [str(page.get("page_id")) for page in pages]), model_receipts


def mine_triplets(ensemble: Ensemble, questions: Sequence[dict[str, Any]], train_indices: Iterable[int]) -> tuple[list[tuple[str, str, str]], int]:
    by_id = {page_id: index for index, page_id in enumerate(ensemble.document_ids)}
    triplets: list[tuple[str, str, str]] = []
    missing = 0
    for question_index in train_indices:
        question = questions[question_index]
        gold = [str(value) for value in (question.get("gold_page_ids") or [])]
        if not gold or gold[0] not in by_id:
            missing += 1
            continue
        positive_index = by_id[gold[0]]
        query_vector = ensemble.query_vectors[str(question["question"])]
        candidate_vectors = ensemble.document_vectors
        q_dist = 1.0 - candidate_vectors @ query_vector
        p_dist = 1.0 - candidate_vectors @ ensemble.document_vectors[positive_index]
        positive_distance = float(q_dist[positive_index])
        candidates = [
            index for index, candidate_distance in enumerate(q_dist)
            if index != positive_index and candidate_distance < positive_distance and candidate_distance < p_dist[index]
        ]
        if not candidates:
            missing += 1
            continue
        negative_index = min(candidates, key=lambda index: (float(q_dist[index]), ensemble.document_ids[index]))
        triplets.append((str(question["question"]), ensemble.document_ids[positive_index], ensemble.document_ids[negative_index]))
    return triplets, missing


def train_triplet_reranker(triplets: Sequence[tuple[str, str, str]], pages_by_id: dict[str, dict[str, Any]], model_id: str, *, device: str, epochs: int, batch_size: int, margin: float, max_length: int) -> CrossEncoder:
    """Fine-tune a CrossEncoder with the paper's margin triplet objective."""
    import torch
    from torch.utils.data import DataLoader

    reranker = CrossEncoder(model_id, num_labels=1, max_length=max_length, device=device)
    optimizer = torch.optim.AdamW(reranker.model.parameters(), lr=2e-5)
    rng = random.Random(7)
    examples = list(triplets)
    for _ in range(epochs):
        rng.shuffle(examples)
        for start in range(0, len(examples), batch_size):
            batch = examples[start : start + batch_size]
            if not batch:
                continue
            queries = [item[0] for item in batch]
            positives = [page_text(pages_by_id[item[1]]) for item in batch]
            negatives = [page_text(pages_by_id[item[2]]) for item in batch]
            positive_tokens = reranker.tokenizer(queries, positives, padding=True, truncation=True, max_length=max_length, return_tensors="pt").to(reranker.model.device)
            negative_tokens = reranker.tokenizer(queries, negatives, padding=True, truncation=True, max_length=max_length, return_tensors="pt").to(reranker.model.device)
            positive_scores = reranker.model(**positive_tokens).logits.reshape(-1)
            negative_scores = reranker.model(**negative_tokens).logits.reshape(-1)
            loss = torch.relu(margin - positive_scores + negative_scores).mean()
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
    return reranker


def rerank_scores(reranker: CrossEncoder, questions: Sequence[dict[str, Any]], pages: Sequence[dict[str, Any]], *, batch_size: int, max_length: int) -> list[np.ndarray]:
    documents = [page_text(page) for page in pages]
    output: list[np.ndarray] = []
    for question in questions:
        pairs = [(str(question["question"]), document) for document in documents]
        scores = reranker.predict(pairs, batch_size=batch_size, show_progress_bar=False, convert_to_numpy=True)
        output.append(np.asarray(scores, dtype=np.float32).reshape(-1))
    return output


def mrr(scores: Sequence[np.ndarray], questions: Sequence[dict[str, Any]], page_ids: Sequence[str], k: int) -> float:
    values: list[float] = []
    for score, question in zip(scores, questions):
        gold = {str(value) for value in (question.get("gold_page_ids") or [])}
        ordered = np.argsort(score)[::-1][:k]
        hit = next((rank for rank, index in enumerate(ordered, 1) if page_ids[index] in gold), None)
        values.append(1.0 / hit if hit else 0.0)
    return float(np.mean(values)) if values else 0.0


def run(data: dict[str, Any], *, candidate_limit: int, train_limit: int, test_limit: int, seed: int, device: str, batch_size: int, max_seq_length: int | None, model_ids: Sequence[str], reranker_model: str | None, reranker_epochs: int, local_files_only: bool, trust_remote_code: bool) -> dict[str, Any]:
    all_questions = [question for question in data["questions"] if question.get("gold_page_ids")]
    train = all_questions[:train_limit]
    test = all_questions[train_limit : train_limit + test_limit]
    required = {str(page_id) for question in train + test for page_id in question["gold_page_ids"]}
    pages = bounded_pages(list(data["pages"]), required, candidate_limit, seed)
    queries = [str(question["question"]) for question in train + test]
    ensemble, model_receipts = fit_ensemble(pages, queries, model_ids, device=device, batch_size=batch_size, max_seq_length=max_seq_length, local_files_only=local_files_only, trust_remote_code=trust_remote_code)
    triplets, missing_triplets = mine_triplets(ensemble, train + test, range(len(train)))
    result: dict[str, Any] = {
        "schema_version": "frankengate-oracle-hard-negative-paper-reproduction-v1",
        "paper": {"title": "Hard Negative Mining for Domain-Specific Retrieval in Enterprise Systems", "arxiv": "2505.18366"},
        "dataset": {"pages": len(pages), "train_questions": len(train), "test_questions": len(test), "candidate_selection": "all positives plus stable-hash distractors", "seed": seed},
        "ensemble": {"models": list(model_ids), "model_receipts": model_receipts, "normalization": "per-model unit norm, then concatenated unit norm", "pca": "full PCA retaining 95% variance fit on bounded candidate corpus", "pca_components": int(ensemble.pca.n_components_)},
        "hard_negative_mining": {"inequalities": ["d(Q,D) < d(Q,PD)", "d(Q,D) < d(PD,D)"], "triplets_selected": len(triplets), "triplets_unavailable": missing_triplets},
        "claim_boundary": ["Faithful neural implementation of the published selection contract on a bounded public-style corpus.", "Exact paper reproduction remains unavailable without Oracle's private corpus, exact checkpoints/configuration, and original reranker training setup."],
    }
    if reranker_model:
        pages_by_id = {str(page.get("page_id")): page for page in pages}
        reranker = train_triplet_reranker(triplets, pages_by_id, reranker_model, device=device, epochs=reranker_epochs, batch_size=batch_size, margin=0.2, max_length=max_seq_length or 512)
        scores = rerank_scores(reranker, test, pages, batch_size=batch_size, max_length=max_seq_length or 512)
        result["reranker"] = {"model_id": reranker_model, "objective": "relu(margin - score(Q,PD) + score(Q,D_HN))", "margin": 0.2, "epochs": reranker_epochs, "mrr_at_3": mrr(scores, test, ensemble.document_ids, 3), "mrr_at_10": mrr(scores, test, ensemble.document_ids, 10)}
    else:
        result["reranker"] = {"status": "not_run", "reason": "pass --reranker-model to execute the paper's triplet-trained cross-encoder stage"}
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidate-limit", type=int, default=1000)
    parser.add_argument("--train-limit", type=int, default=100)
    parser.add_argument("--test-limit", type=int, default=100)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--max-seq-length", type=int, default=512)
    parser.add_argument("--model", dest="models", action="append", default=[])
    parser.add_argument("--reranker-model")
    parser.add_argument("--reranker-epochs", type=int, default=1)
    parser.add_argument("--local-files-only", action="store_true")
    parser.add_argument("--trust-remote-code", action="store_true", help="Allow model repositories with custom modeling code (required by Stella).")
    args = parser.parse_args()
    model_ids = tuple(args.models) if args.models else PAPER_EMBEDDING_MODELS
    data = json.loads(args.dataset.read_text(encoding="utf-8"))
    result = run(data, candidate_limit=args.candidate_limit, train_limit=args.train_limit, test_limit=args.test_limit, seed=args.seed, device=args.device, batch_size=args.batch_size, max_seq_length=args.max_seq_length, model_ids=model_ids, reranker_model=args.reranker_model, reranker_epochs=args.reranker_epochs, local_files_only=args.local_files_only, trust_remote_code=args.trust_remote_code)
    result["dataset"]["input_sha256"] = sha256(args.dataset)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"triplets": result["hard_negative_mining"], "reranker": result["reranker"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
