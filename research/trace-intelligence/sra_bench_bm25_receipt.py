#!/usr/bin/env python3
"""Create a content-minimized receipt for the public SRA-Bench BM25 control.

The SRA result files contain skill IDs and retrieved rankings.  This receipt
keeps only dataset-level metrics and hashes so that public benchmark content
is not copied into the Frankengate research branch.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


DATASETS = ("toolqa", "bigcodebench", "theoremqa", "logicbench", "medcalcbench", "champ")
METRICS = ("Recall@1", "Recall@5", "Recall@10", "Recall@50", "nDCG@1", "nDCG@5", "nDCG@10", "nDCG@50")
SCHEMA_VERSION = "frankengate-sra-bench-bm25-retrieval-control-v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_head(root: Path) -> str:
    return subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()


def run(root: Path, result_dir: Path, output: Path) -> dict[str, Any]:
    corpus = root / "data/bench/corpus/corpus.json"
    if not corpus.exists():
        raise FileNotFoundError(corpus)
    datasets: dict[str, Any] = {}
    for dataset in DATASETS:
        result_path = result_dir / f"sra-{dataset}-bm25.json"
        instance_path = root / f"data/bench/instances/{dataset}.json"
        payload = json.loads(result_path.read_text(encoding="utf-8"))
        metadata = payload.get("metadata", {})
        metrics = payload.get("metrics", {})
        if metadata.get("dataset") != dataset or metadata.get("retriever") != "bm25":
            raise ValueError(f"unexpected metadata for {dataset}")
        if set(METRICS) - set(metrics):
            raise ValueError(f"missing metrics for {dataset}")
        datasets[dataset] = {
            "instances_sha256": sha256(instance_path),
            "result_sha256": sha256(result_path),
            "queries": int(metadata["n_queries"]),
            "corpus_size": int(metadata["corpus_size"]),
            "top_k": int(metadata["top_k"]),
            "metrics": {name: round(float(metrics[name]), 8) for name in METRICS},
            "raw_rankings_committed": False,
        }
    receipt: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "repository": "https://github.com/oneal2000/SR-Agents",
            "repository_head": git_head(root),
            "corpus_sha256": sha256(corpus),
            "raw_skill_content_committed": False,
        },
        "protocol": {
            "retriever": "BM25",
            "top_k": 50,
            "stage": "skill retrieval only",
            "incorporation_measured": False,
            "end_task_execution_measured": False,
            "authority_or_consent_measured": False,
            "changed_system_replay_measured": False,
        },
        "datasets": datasets,
        "claim_boundary": {
            "retrieval_control_verified": True,
            "skill_utility_established": False,
            "enterprise_alias_quality_established": False,
            "artifact_correctness_established": False,
            "reason": "public gold-skill and web-distractor corpus; receipt intentionally excludes raw skills and rankings",
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
