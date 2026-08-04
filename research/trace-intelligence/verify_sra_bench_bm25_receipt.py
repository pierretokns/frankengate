#!/usr/bin/env python3
"""Verify the content-minimized SRA-Bench BM25 control receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


DATASETS = {"toolqa", "bigcodebench", "theoremqa", "logicbench", "medcalcbench", "champ"}
METRICS = {"Recall@1", "Recall@5", "Recall@10", "Recall@50", "nDCG@1", "nDCG@5", "nDCG@10", "nDCG@50"}


def run(path: Path) -> dict[str, object]:
    receipt = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    if receipt.get("schema_version") != "frankengate-sra-bench-bm25-retrieval-control-v1":
        errors.append("schema_version")
    if set(receipt.get("datasets", {})) != DATASETS:
        errors.append("dataset set")
    protocol = receipt.get("protocol", {})
    if protocol.get("retriever") != "BM25" or protocol.get("top_k") != 50:
        errors.append("protocol")
    if any(bool(entry.get("raw_rankings_committed")) for entry in receipt.get("datasets", {}).values()):
        errors.append("raw rankings committed")
    if receipt.get("claim_boundary", {}).get("skill_utility_established"):
        errors.append("skill utility overclaim")
    for dataset, entry in receipt.get("datasets", {}).items():
        metrics = set(entry.get("metrics", {}))
        if metrics != METRICS:
            errors.append(f"metrics:{dataset}")
        if entry.get("top_k") != 50 or entry.get("corpus_size") != 26262:
            errors.append(f"metadata:{dataset}")
        if any(not 0.0 <= float(value) <= 1.0 for value in entry.get("metrics", {}).values()):
            errors.append(f"range:{dataset}")
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
