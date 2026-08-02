#!/usr/bin/env python3
"""Verify the content-minimized SRA-Bench BM25/TF-IDF comparison receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


DATASETS = {"toolqa", "bigcodebench", "theoremqa", "logicbench", "medcalcbench", "champ"}


def run(path: Path) -> dict[str, object]:
    receipt = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if receipt.get("schema_version") != "frankengate-sra-bench-bm25-tfidf-comparison-v1":
        errors.append("schema_version")
    if set(receipt.get("datasets", {})) != DATASETS:
        errors.append("dataset set")
    protocol = receipt.get("protocol", {})
    if protocol.get("methods") != ["bm25", "tfidf"] or protocol.get("top_k") != 50 or not protocol.get("same_corpus_and_queries"):
        errors.append("protocol")
    if any(bool(entry.get("raw_rankings_committed")) for entry in receipt.get("datasets", {}).values()):
        errors.append("raw rankings committed")
    for dataset, entry in receipt.get("datasets", {}).items():
        if set(entry.get("bm25", {}).get("metrics", {})) != set(entry.get("tfidf", {}).get("metrics", {})):
            errors.append(f"metrics:{dataset}")
        for method in ("bm25", "tfidf"):
            if entry.get(method, {}).get("top_k") != 50 or entry.get(method, {}).get("corpus_size") != 26262:
                errors.append(f"metadata:{dataset}:{method}")
            if any(not 0.0 <= float(value) <= 1.0 for value in entry.get(method, {}).get("metrics", {}).values()):
                errors.append(f"range:{dataset}:{method}")
    unsigned = dict(receipt)
    expected = unsigned.pop("receipt_sha256", None)
    actual = hashlib.sha256(json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if expected != actual:
        errors.append("receipt hash")
    result = {"verification_passed": not errors, "errors": errors, "datasets_verified": len(receipt.get("datasets", {})), "receipt_sha256": expected}
    print(json.dumps(result, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    return 0 if run(args.receipt)["verification_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
