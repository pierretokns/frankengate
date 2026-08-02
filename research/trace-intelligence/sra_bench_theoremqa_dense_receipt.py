#!/usr/bin/env python3
"""Build a content-minimized SRA-Bench TheoremQA dense-retrieval receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metrics(path: Path) -> dict[str, float]:
    value: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return {key: float(value["metrics"][key]) for key in ("Recall@1", "Recall@5", "Recall@10", "Recall@50", "nDCG@10")}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dense", type=Path, required=True)
    parser.add_argument("--bm25", type=Path, required=True)
    parser.add_argument("--tfidf", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    dense, bm25, tfidf = metrics(args.dense), metrics(args.bm25), metrics(args.tfidf)
    result = {
        "schema_version": "frankengate-sra-bench-theoremqa-dense-retrieval-v1",
        "dataset": {"name": "theoremqa", "queries": 747, "corpus_skills": 26262, "gold_skill_annotations": 636},
        "protocol": {"dense_model": "BAAI/bge-base-en-v1.5", "query_prefix": "Represent this sentence for searching relevant passages:", "top_k": 50, "source": "SRA-Bench/SR-Agents pinned public corpus", "raw_outputs_committed": False},
        "metrics": {"bge": dense, "bm25": bm25, "tfidf": tfidf},
        "delta_vs_bm25": {key: dense[key] - bm25[key] for key in dense},
        "delta_vs_tfidf": {key: dense[key] - tfidf[key] for key in dense},
        "inputs": {"dense_sha256": sha256(args.dense), "bm25_sha256": sha256(args.bm25), "tfidf_sha256": sha256(args.tfidf)},
        "decision": {"dense_role": "candidate_generation", "execution_or_incorporation_measured": False, "changed_system_replay_measured": False, "skill_release_authorized": False},
        "claim_boundary": "This is a public capability-retrieval measurement. It does not establish enterprise alias quality, tool compatibility, incorporation, causal skill utility, authority safety, or prospective user benefit.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"schema_version": result["schema_version"], "metrics": result["metrics"], "delta_vs_bm25": result["delta_vs_bm25"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
