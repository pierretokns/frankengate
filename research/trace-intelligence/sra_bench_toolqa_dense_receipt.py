#!/usr/bin/env python3
"""Create a content-minimized ToolQA lexical/dense comparison receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


METRICS = ("Recall@1", "Recall@5", "Recall@10", "Recall@50", "nDCG@1", "nDCG@5", "nDCG@10", "nDCG@50")
SCHEMA_VERSION = "frankengate-sra-bench-toolqa-lexical-dense-comparison-v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load(path: Path, method: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    metadata = payload.get("metadata", {})
    metrics = payload.get("metrics", {})
    if metadata.get("dataset") != "toolqa" or metadata.get("retriever") != method:
        raise ValueError(f"unexpected {method} metadata")
    return {
        "result_sha256": sha256(path),
        "queries": int(metadata["n_queries"]),
        "corpus_size": int(metadata["corpus_size"]),
        "top_k": int(metadata["top_k"]),
        "metrics": {name: round(float(metrics[name]), 8) for name in METRICS},
    }


def run(root: Path, result_dir: Path, output: Path) -> dict[str, Any]:
    corpus = root / "data/bench/corpus/corpus.json"
    instances = root / "data/bench/instances/toolqa.json"
    methods = {
        "bm25": load(result_dir / "sra-toolqa-bm25.json", "bm25"),
        "tfidf": load(result_dir / "sra-toolqa-tfidf.json", "tfidf"),
        "bge_base_en_v1_5": load(result_dir / "sra-toolqa-bge.json", "bge"),
    }
    if any((entry["queries"], entry["corpus_size"], entry["top_k"]) != (1430, 26262, 50) for entry in methods.values()):
        raise ValueError("protocol mismatch")
    receipt: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "repository": "https://github.com/oneal2000/SR-Agents",
            "corpus_sha256": sha256(corpus),
            "instances_sha256": sha256(instances),
            "raw_skill_content_committed": False,
            "raw_rankings_committed": False,
        },
        "protocol": {
            "dataset": "toolqa",
            "queries": 1430,
            "corpus_size": 26262,
            "top_k": 50,
            "methods": ["bm25", "tfidf", "BAAI/bge-base-en-v1.5"],
            "bge_query_prefix": "Represent this sentence for searching relevant passages: ",
            "stage": "skill retrieval only",
            "incorporation_measured": False,
            "end_task_execution_measured": False,
        },
        "methods": methods,
        "claim_boundary": {
            "dense_retrieval_measured": True,
            "skill_utility_established": False,
            "enterprise_alias_quality_established": False,
            "reason": "public ToolQA gold-skill/web-distractor corpus; retrieval-only comparison",
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
