#!/usr/bin/env python3
"""Measure a fold-local ranker distilled from LRAT browsing behavior.

This is intentionally a retrieval proxy.  A document that is browsed after a
search is a weak, silver relevance label; it is not an independent correctness
or enterprise-utility judgment.  Training is leave-one-trajectory-out so that
the held-out query and candidate snippets cannot leak into the ranker.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from lrat_trajectory_retrieval_proxy import (
    aggregate,
    extract_trajectories,
    metrics,
    rank_lexical,
)


SCHEMA_VERSION = "frankengate-lrat-trajectory-distilled-ranker-proxy-v1"
DOC_ID_RE = re.compile(r"\bDocID\s*[:=]\s*[A-Za-z0-9_.:-]+\b", re.IGNORECASE)


def pair_text(query: str, snippet: str) -> str:
    # IDs are candidate keys, not semantic evidence.  Keeping them out of the
    # model text prevents memorization of the public sample identifiers.
    return f"{query}\nDOCUMENT\n{DOC_ID_RE.sub(' ', snippet)}"


def rank_distilled(
    train_rows: list[dict[str, Any]],
    held_out: dict[str, Any],
) -> list[str]:
    texts: list[str] = []
    labels: list[int] = []
    for row in train_rows:
        query = str(row["query"])
        positive = set(row["positive"])
        for identifier in row["exposed"]:
            texts.append(pair_text(query, row["snippets"].get(identifier, "")))
            labels.append(int(identifier in positive))

    # The public sample has both classes in each training fold.  Keep a safe
    # fallback for future sample revisions rather than silently changing the
    # receipt protocol.
    if len(set(labels)) < 2:
        return rank_lexical(held_out["query"], held_out["exposed"], held_out["snippets"])

    vectorizer = TfidfVectorizer(
        analyzer="word",
        ngram_range=(1, 2),
        min_df=1,
        max_features=20000,
        lowercase=True,
    )
    train_matrix = vectorizer.fit_transform(texts)
    classifier = LogisticRegression(
        class_weight="balanced",
        max_iter=1000,
        random_state=0,
    )
    classifier.fit(train_matrix, labels)
    candidates = held_out["exposed"]
    test_matrix = vectorizer.transform(
        [pair_text(str(held_out["query"]), held_out["snippets"].get(identifier, "")) for identifier in candidates]
    )
    scores = classifier.predict_proba(test_matrix)[:, 1]
    return [
        identifier
        for _, identifier in sorted(
            zip(scores.tolist(), candidates),
            key=lambda pair: (-pair[0], candidates.index(pair[1])),
        )
    ]


def run(root: Path, output: Path) -> dict[str, Any]:
    trajectories = extract_trajectories(root)
    arms: dict[str, list[dict[str, float]]] = {
        "search_order": [],
        "lexical": [],
        "trajectory_distilled_ranker": [],
    }
    fold_summaries: list[dict[str, Any]] = []
    counts = {
        "trajectories": len(trajectories),
        "exposed_documents": sum(len(row["exposed"]) for row in trajectories),
        "positive_documents": sum(len(row["positive"]) for row in trajectories),
        "folds": len(trajectories),
    }
    for index, held_out in enumerate(trajectories):
        train_rows = trajectories[:index] + trajectories[index + 1 :]
        search_order = list(held_out["exposed"])
        lexical = rank_lexical(held_out["query"], held_out["exposed"], held_out["snippets"])
        distilled = rank_distilled(train_rows, held_out)
        positive = set(held_out["positive"])
        arms["search_order"].append(metrics(search_order, positive))
        arms["lexical"].append(metrics(lexical, positive))
        arms["trajectory_distilled_ranker"].append(metrics(distilled, positive))
        fold_summaries.append(
            {
                "fold": index,
                "held_out_trajectory_hash": held_out["path_hash"],
                "candidate_count": len(held_out["exposed"]),
                "positive_count": len(positive),
                "train_trajectories": len(train_rows),
            }
        )

    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "root_uri": "external://lrat-repro/trajectory",
            "raw_content_committed": False,
            "trajectory_hashes_only": True,
        },
        "protocol": {
            "split": "leave-one-trajectory-out",
            "positive_definition": "browsed document intersected with search-exposed document",
            "negative_definition": "search-exposed but unbrowsed document",
            "candidate_pool": "within-trajectory exposed documents",
            "model": "tfidf(word_1_2grams)+balanced_logistic_regression",
            "document_ids_in_model_text": False,
            "positive_labels_are_silver": True,
        },
        "cohort": counts,
        "arms": {arm: aggregate(values) for arm, values in arms.items()},
        "folds": fold_summaries,
        "claim_boundary": {
            "trajectory_distillation_measured": True,
            "silver_relevance_only": True,
            "document_correctness_established": False,
            "enterprise_artifact_utility_established": False,
            "independent_correctness_established": False,
            "promotion_authorized": False,
            "reason": "Browsing is a weak relevance signal; the public samples have no independent correctness, principal, authority, or changed-system outcome labels.",
        },
    }
    result["result_sha256"] = hashlib.sha256(
        json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"cohort": counts, "arms": result["arms"]}, sort_keys=True))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.root, args.output)
