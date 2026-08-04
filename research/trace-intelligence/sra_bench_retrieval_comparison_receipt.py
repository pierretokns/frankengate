#!/usr/bin/env python3
"""Create a content-minimized BM25/TF-IDF SRA-Bench comparison receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


DATASETS = ("toolqa", "bigcodebench", "theoremqa", "logicbench", "medcalcbench", "champ")
METRICS = ("Recall@1", "Recall@5", "Recall@10", "Recall@50", "nDCG@1", "nDCG@5", "nDCG@10", "nDCG@50")
SCHEMA_VERSION = "frankengate-sra-bench-bm25-tfidf-comparison-v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path, dataset: str, method: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    metadata = payload.get("metadata", {})
    metrics = payload.get("metrics", {})
    if metadata.get("dataset") != dataset or metadata.get("retriever") != method:
        raise ValueError(f"unexpected {method} metadata for {dataset}")
    if set(METRICS) - set(metrics):
        raise ValueError(f"missing {method} metrics for {dataset}")
    return {
        "result_sha256": sha256(path),
        "queries": int(metadata["n_queries"]),
        "corpus_size": int(metadata["corpus_size"]),
        "top_k": int(metadata["top_k"]),
        "metrics": {name: round(float(metrics[name]), 8) for name in METRICS},
    }


def run(root: Path, result_dir: Path, output: Path) -> dict[str, Any]:
    corpus = root / "data/bench/corpus/corpus.json"
    datasets: dict[str, Any] = {}
    for dataset in DATASETS:
        bm25 = load(result_dir / f"sra-{dataset}-bm25.json", dataset, "bm25")
        tfidf = load(result_dir / f"sra-{dataset}-tfidf.json", dataset, "tfidf")
        if (bm25["queries"], bm25["corpus_size"], bm25["top_k"]) != (tfidf["queries"], tfidf["corpus_size"], tfidf["top_k"]):
            raise ValueError(f"protocol mismatch for {dataset}")
        datasets[dataset] = {
            "queries": bm25["queries"],
            "corpus_size": bm25["corpus_size"],
            "top_k": bm25["top_k"],
            "bm25": bm25,
            "tfidf": tfidf,
            "tfidf_minus_bm25": {name: round(tfidf["metrics"][name] - bm25["metrics"][name], 8) for name in METRICS},
            "raw_rankings_committed": False,
        }
    receipt: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "repository": "https://github.com/oneal2000/SR-Agents",
            "corpus_sha256": sha256(corpus),
            "raw_skill_content_committed": False,
        },
        "protocol": {
            "methods": ["bm25", "tfidf"],
            "top_k": 50,
            "same_corpus_and_queries": True,
            "stage": "skill retrieval only",
            "incorporation_measured": False,
            "end_task_execution_measured": False,
        },
        "datasets": datasets,
        "claim_boundary": {
            "retrieval_comparison_verified": True,
            "embedding_measured": False,
            "skill_utility_established": False,
            "enterprise_alias_quality_established": False,
            "reason": "BM25 and TF-IDF are lexical controls on a public gold-skill/web-distractor corpus",
        },
    }
    receipt["receipt_sha256"] = hashlib.sha256(json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--result-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.root, args.result_dir, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
