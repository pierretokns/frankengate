#!/usr/bin/env python3
"""Deduplicate a MATM timing receipt produced by the pre-fix harness.

The old harness appended one identical call receipt per ranking arm. This
repair keeps the first byte-identical entry per query, records the source hash,
and recomputes the content hash. It does not change any aggregate metric.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source = json.loads(args.source.read_text(encoding="utf-8"))
    original_hash = source.get("result_sha256")
    receipts = source.get("frontier_calls", {}).get("receipts", [])
    by_query: dict[int, dict[str, Any]] = {}
    for receipt in receipts:
        query = int(receipt["query"])
        if query in by_query:
            assert receipt == by_query[query], f"non-identical duplicate for query {query}"
        else:
            by_query[query] = receipt
    repaired = dict(source)
    repaired["frontier_calls"] = dict(source["frontier_calls"])
    repaired["frontier_calls"]["receipts"] = [by_query[key] for key in sorted(by_query)]
    repaired["frontier_calls"]["completed"] = len(by_query)
    repaired["receipt_repair"] = {
        "source_result_sha256": original_hash,
        "source_file_sha256": file_hash(args.source),
        "reason": "pre-fix harness appended one identical timing receipt per ranking arm",
        "duplicate_entries_removed": len(receipts) - len(by_query),
        "aggregate_metrics_changed": False,
    }
    repaired.pop("result_sha256", None)
    repaired["result_sha256"] = stable_hash(repaired)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(repaired, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"source_result_sha256": original_hash, "result_sha256": repaired["result_sha256"], "queries": len(by_query), "duplicates_removed": len(receipts) - len(by_query)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
