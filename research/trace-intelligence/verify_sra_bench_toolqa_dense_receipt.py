#!/usr/bin/env python3
"""Verify the content-minimized ToolQA dense comparison receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


METHODS = {"bm25", "tfidf", "bge_base_en_v1_5"}
METRICS = {"Recall@1", "Recall@5", "Recall@10", "Recall@50", "nDCG@1", "nDCG@5", "nDCG@10", "nDCG@50"}


def run(path: Path) -> dict[str, object]:
    receipt = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if receipt.get("schema_version") != "frankengate-sra-bench-toolqa-lexical-dense-comparison-v1":
        errors.append("schema_version")
    if set(receipt.get("methods", {})) != METHODS:
        errors.append("methods")
    protocol = receipt.get("protocol", {})
    if protocol.get("dataset") != "toolqa" or protocol.get("queries") != 1430 or protocol.get("corpus_size") != 26262 or protocol.get("top_k") != 50:
        errors.append("protocol")
    if any(not 0.0 <= float(value) <= 1.0 for method in receipt.get("methods", {}).values() for value in method.get("metrics", {}).values()):
        errors.append("metric range")
    if receipt.get("source", {}).get("raw_rankings_committed") or receipt.get("source", {}).get("raw_skill_content_committed"):
        errors.append("raw content committed")
    unsigned = dict(receipt)
    expected = unsigned.pop("receipt_sha256", None)
    actual = hashlib.sha256(json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if expected != actual:
        errors.append("receipt hash")
    result = {"verification_passed": not errors, "errors": errors, "methods_verified": len(receipt.get("methods", {})), "receipt_sha256": expected}
    print(json.dumps(result, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    return 0 if run(args.receipt)["verification_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
