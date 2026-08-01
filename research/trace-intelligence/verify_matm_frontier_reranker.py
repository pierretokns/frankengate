#!/usr/bin/env python3
"""Verify a content-minimized MATM frontier-reranker receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-matm-frontier-reranker-benchmark-v1"
FORBIDDEN_KEYS = {"goal", "action_templates", "scores", "candidates", "trajectory", "task_id"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _assert_no_raw_keys(value: Any) -> None:
    if isinstance(value, dict):
        overlap = FORBIDDEN_KEYS.intersection(value)
        if overlap:
            raise ValueError(f"receipt contains raw-content keys: {sorted(overlap)}")
        for item in value.values():
            _assert_no_raw_keys(item)
    elif isinstance(value, list):
        for item in value:
            _assert_no_raw_keys(item)


def verify(result_path: Path, raw_dir: Path) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected MATM frontier receipt schema")
    _assert_no_raw_keys(result)
    calls = result.get("frontier_calls", {})
    receipts = calls.get("receipts", [])
    if calls.get("failures") != 0 or calls.get("completed") != len(receipts):
        raise ValueError("frontier call counts are not complete")
    if result.get("protocol", {}).get("outcomes_hidden_from_frontier") is not True:
        raise ValueError("frontier prompt was allowed to see outcomes")
    for receipt in receipts:
        query = int(receipt["query"])
        path = raw_dir / f"query-{query:03d}.json"
        if not path.exists() or _sha256(path) != receipt.get("raw_sha256"):
            raise ValueError(f"raw receipt hash mismatch for query {query}")
        if not receipt.get("prompt_sha256"):
            raise ValueError(f"missing prompt hash for query {query}")
    for method, metrics in result.get("aggregate", {}).items():
        if method not in {"lexical", "embedding", "frontier"}:
            raise ValueError(f"unexpected ranking method: {method}")
        for metric in ("mrr", "recall_at_1", "recall_at_3", "recall_at_5", "top_3_success_rate"):
            value = metrics.get(metric)
            if not isinstance(value, (float, int)) or not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"invalid metric {method}.{metric}")
    return {
        "schema_version": "matm-frontier-reranker-verification-v1",
        "source_result_sha256": _sha256(result_path),
        "queries_verified": len(receipts),
        "raw_hashes_match": True,
        "content_minimized": True,
        "outcomes_hidden_from_frontier": True,
        "verification_passed": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.result, args.raw_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
