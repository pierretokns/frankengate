#!/usr/bin/env python3
"""Clean-room CPU reimplementation of the hard-negative selection protocol.

The Oracle paper (ACL 2025, arXiv:2505.18366) uses six neural bi-encoder
views, concatenation, PCA (95% variance), and two distance inequalities to
mine a semantically-close but positive-dissimilar document.  This module keeps
that algorithmic contract while using six deterministic TF-IDF views so it can
run locally without model downloads.  It is deliberately labelled a surrogate:
the paper's exact private encoders and cross-encoder are not available.

Input is the research corpus shape used by the wiki experiments: ``pages`` and
``questions`` with ``gold_page_ids``.  The output is a receipt containing
selection rates and a held-out MRR comparison for random, lexical, and proposed
hard negatives.
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from sklearn.decomposition import PCA
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import pairwise_distances
from sklearn.preprocessing import normalize


VIEWS = (
    {"name": "word-1-1", "analyzer": "word", "ngram_range": (1, 1)},
    {"name": "word-1-2", "analyzer": "word", "ngram_range": (1, 2)},
    {"name": "word-1-3", "analyzer": "word", "ngram_range": (1, 3)},
    {"name": "char-3-5", "analyzer": "char", "ngram_range": (3, 5)},
    {"name": "char-4-6", "analyzer": "char", "ngram_range": (4, 6)},
    {"name": "char-2-6", "analyzer": "char", "ngram_range": (2, 6)},
)


def page_text(page: dict[str, Any]) -> str:
    metadata = [page.get("title", ""), *page.get("aliases", [])]
    metadata += [page.get("issuer", ""), page.get("source_family", "")]
    return " ".join(str(value) for value in (*metadata, page.get("text", "")) if value)


@dataclass
class FeatureBank:
    pages: list[dict[str, Any]]
    vectors: np.ndarray
    pca_vectors: np.ndarray
    view_slices: list[slice]
    lexical: np.ndarray
    page_ids: list[str]

    def query_vectors(self, query: str) -> tuple[np.ndarray, np.ndarray]:
        dense_views: list[np.ndarray] = []
        for vectorizer in self._vectorizers:
            vector = vectorizer.transform([query])
            dense_views.append(vector.toarray()[0])
        dense = np.concatenate(dense_views)
        pca = self._pca.transform([dense])[0]
        return normalize(dense.reshape(1, -1))[0], normalize(pca.reshape(1, -1))[0]

    # Private fitted objects are attached after construction. Keeping them on
    # the dataclass makes repeated query evaluation cheap without serializing
    # model internals into the content-minimized receipt.
    _vectorizers: list[TfidfVectorizer] = None  # type: ignore[assignment]
    _pca: PCA = None  # type: ignore[assignment]
    lexical_vectorizer: TfidfVectorizer = None  # type: ignore[assignment]


def fit_feature_bank(pages: list[dict[str, Any]]) -> FeatureBank:
    texts = [page_text(page) for page in pages]
    vectorizers: list[TfidfVectorizer] = []
    matrices: list[np.ndarray] = []
    slices: list[slice] = []
    offset = 0
    for spec in VIEWS:
        vectorizer = TfidfVectorizer(
            analyzer=spec["analyzer"],
            ngram_range=spec["ngram_range"],
            lowercase=True,
            min_df=1,
            max_features=2048,
            sublinear_tf=True,
        )
        matrix = vectorizer.fit_transform(texts)
        dense = normalize(matrix).toarray()
        matrices.append(dense)
        vectorizers.append(vectorizer)
        slices.append(slice(offset, offset + dense.shape[1]))
        offset += dense.shape[1]
    vectors = normalize(np.concatenate(matrices, axis=1))
    pca = PCA(n_components=0.95, svd_solver="full", random_state=0)
    pca_vectors = normalize(pca.fit_transform(vectors))
    lexical_vectorizer = vectorizers[1]
    lexical = normalize(lexical_vectorizer.transform(texts)).toarray()
    bank = FeatureBank(
        pages=pages,
        vectors=vectors,
        pca_vectors=pca_vectors,
        view_slices=slices,
        lexical=lexical,
        page_ids=[str(page["page_id"]) for page in pages],
    )
    bank._vectorizers = vectorizers
    bank._pca = pca
    bank.lexical_vectorizer = lexical_vectorizer
    return bank


def cosine_scores(query_vector: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    return matrix @ query_vector


def mine_hard_negative(bank: FeatureBank, query: str, positive_id: str) -> str | None:
    _, query_pca = bank.query_vectors(query)
    positive_index = bank.page_ids.index(positive_id)
    distances_q = pairwise_distances(query_pca.reshape(1, -1), bank.pca_vectors, metric="cosine")[0]
    distances_p = pairwise_distances(bank.pca_vectors[positive_index].reshape(1, -1), bank.pca_vectors, metric="cosine")[0]
    positive_distance = float(distances_q[positive_index])
    candidates = [
        index
        for index, page_id in enumerate(bank.page_ids)
        if page_id != positive_id
        and distances_q[index] < positive_distance
        and distances_q[index] < distances_p[index]
    ]
    if not candidates:
        return None
    return bank.page_ids[min(candidates, key=lambda index: (distances_q[index], bank.page_ids[index]))]


def pair_features(bank: FeatureBank, query: str, doc_indices: Iterable[int]) -> np.ndarray:
    query_vector, _ = bank.query_vectors(query)
    query_views = [query_vector[sl] for sl in bank.view_slices]
    rows: list[list[float]] = []
    for index in doc_indices:
        doc_vector = bank.vectors[index]
        per_view = [float(doc_vector[sl] @ query_views[position]) for position, sl in enumerate(bank.view_slices)]
        rows.append([*per_view, float(bank.lexical[index] @ (bank.lexical_vectorizer.transform([query]).toarray()[0]))])
    return np.asarray(rows, dtype=np.float32)


def rank_mrr(scores: np.ndarray, gold_index: int, k: int) -> float:
    order = np.argsort(-scores, kind="stable")[:k]
    for rank, index in enumerate(order, 1):
        if int(index) == gold_index:
            return 1.0 / rank
    return 0.0


def choose_negative(bank: FeatureBank, query: str, positive_index: int, strategy: str, rng: random.Random) -> int | None:
    candidates = [index for index in range(len(bank.pages)) if index != positive_index]
    if not candidates:
        return None
    if strategy == "random":
        return rng.choice(candidates)
    query_vector, _ = bank.query_vectors(query)
    if strategy == "lexical":
        scores = cosine_scores(query_vector, bank.vectors)
    elif strategy == "proposed":
        page_id = bank.page_ids[positive_index]
        mined = mine_hard_negative(bank, query, page_id)
        return bank.page_ids.index(mined) if mined else None
    else:
        raise ValueError(f"unknown strategy: {strategy}")
    return max(candidates, key=lambda index: (float(scores[index]), -index))


def run(data: dict[str, Any], limit: int = 0, seed: int = 7) -> dict[str, Any]:
    pages = list(data["pages"])
    bank = fit_feature_bank(pages)
    questions = [question for question in data["questions"] if question.get("gold_page_ids")]
    if limit:
        questions = questions[:limit]
    train = [question for index, question in enumerate(questions) if index % 5 != 0]
    test = [question for index, question in enumerate(questions) if index % 5 == 0]
    rng = random.Random(seed)
    methods = {strategy: {"x": [], "selected": 0, "known_hard_matches": 0} for strategy in ("random", "lexical", "proposed")}
    for question in train:
        positive_id = str(question["gold_page_ids"][0])
        if positive_id not in bank.page_ids:
            continue
        positive_index = bank.page_ids.index(positive_id)
        all_features = pair_features(bank, question["question"], range(len(pages)))
        positive_features = all_features[positive_index]
        for strategy in methods:
            negative_index = choose_negative(bank, question["question"], positive_index, strategy, rng)
            if negative_index is None:
                continue
            negative_features = all_features[negative_index]
            methods[strategy]["x"].append((positive_features, negative_features))
            methods[strategy]["selected"] += 1
            if bank.page_ids[negative_index] in {str(value) for value in question.get("hard_negative_page_ids", [])}:
                methods[strategy]["known_hard_matches"] += 1
    metrics: dict[str, Any] = {}
    for strategy, payload in methods.items():
        if not payload["x"]:
            continue
        x = np.asarray([row[0] for row in payload["x"]] + [row[1] for row in payload["x"]], dtype=np.float32)
        y = np.asarray([1] * len(payload["x"]) + [0] * len(payload["x"]), dtype=np.int32)
        model = LogisticRegression(max_iter=500, random_state=seed, solver="liblinear")
        model.fit(x, y)
        values3: list[float] = []
        values10: list[float] = []
        for question in test:
            positive_id = str(question["gold_page_ids"][0])
            if positive_id not in bank.page_ids:
                continue
            positive_index = bank.page_ids.index(positive_id)
            features = pair_features(bank, question["question"], range(len(pages)))
            scores = model.predict_proba(features)[:, 1]
            values3.append(rank_mrr(scores, positive_index, 3))
            values10.append(rank_mrr(scores, positive_index, 10))
        metrics[strategy] = {
            "train_examples": len(payload["x"]),
            "selection_rate": payload["selected"] / len(train) if train else 0.0,
            "known_hard_match_rate": payload["known_hard_matches"] / payload["selected"] if payload["selected"] else 0.0,
            "test_queries": len(values3),
            "mrr_at_3": float(np.mean(values3)) if values3 else 0.0,
            "mrr_at_10": float(np.mean(values10)) if values10 else 0.0,
        }
    return {
        "schema_version": "frankengate-enterprise-hard-negative-mining-v1",
        "protocol": {
            "algorithm": "six-view TF-IDF surrogate for six bi-encoders + PCA(95%) + d(Q,D)<d(Q,PD) and d(Q,D)<d(PD,D)",
            "reranker": "linear logistic pair scorer (cross-encoder surrogate)",
            "split": "deterministic every fifth question held out",
            "seed": seed,
        },
        "corpus": {"pages": len(pages), "questions": len(questions), "train": len(train), "test": len(test)},
        "metrics": metrics,
        "claim_boundary": "CPU clean-room surrogate; not a reproduction of the paper's private six encoders or cross-encoder. Results test whether the selection logic transfers to this corpus.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(json.loads(args.corpus.read_text(encoding="utf-8")), limit=args.limit, seed=args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"schema_version": result["schema_version"], "metrics": result["metrics"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
