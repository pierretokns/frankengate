#!/usr/bin/env python3
"""Verify the TheoremQA dense-retrieval receipt and its claim boundary."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    metrics = receipt["metrics"]
    checks = {
        "schema": receipt.get("schema_version") == "frankengate-sra-bench-theoremqa-dense-retrieval-v1",
        "dataset": receipt.get("dataset", {}).get("queries") == 747 and receipt["dataset"].get("corpus_skills") == 26262,
        "all_arms": all(set(("Recall@1", "Recall@5", "Recall@10", "Recall@50", "nDCG@10")) <= set(metrics[name]) for name in ("bge", "bm25", "tfidf")),
        "dense_beats_bm25_at_r1": metrics["bge"]["Recall@1"] > metrics["bm25"]["Recall@1"],
        "dense_beats_bm25_at_r10": metrics["bge"]["Recall@10"] > metrics["bm25"]["Recall@10"],
        "dense_beats_tfidf_at_r10": metrics["bge"]["Recall@10"] > metrics["tfidf"]["Recall@10"],
        "raw_outputs_external": receipt.get("protocol", {}).get("raw_outputs_committed") is False,
        "promotion_blocked": receipt.get("decision", {}).get("skill_release_authorized") is False and receipt.get("decision", {}).get("execution_or_incorporation_measured") is False,
        "claim_boundary": bool(receipt.get("claim_boundary")),
    }
    result = {"schema_version": "frankengate-sra-bench-theoremqa-dense-retrieval-verification-v1", "source_receipt_sha256": hashlib.sha256(args.receipt.read_bytes()).hexdigest(), "checks": checks, "verification_passed": all(checks.values())}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0 if result["verification_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
