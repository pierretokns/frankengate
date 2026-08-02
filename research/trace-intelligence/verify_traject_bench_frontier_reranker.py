#!/usr/bin/env python3
"""Verify a content-minimized TRAJECT-Bench frontier-reranker receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-traject-bench-frontier-reranker-v1"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(result_path: Path, raw_dir: Path) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected frontier reranker schema")
    if result.get("failures") != 0:
        raise ValueError("frontier calls are incomplete")
    protocol = result.get("protocol", {})
    if protocol.get("frontier_sees_gold_targets") is not False:
        raise ValueError("frontier prompt was allowed to see gold targets")
    if protocol.get("frontier_sees_tool_outputs") is not False:
        raise ValueError("frontier prompt was allowed to see tool outputs")
    selected = int(result.get("dataset", {}).get("selected_cases", 0))
    receipts = result.get("raw_receipts", [])
    if len(receipts) != selected:
        raise ValueError("raw receipt count does not match selected cases")
    for receipt in receipts:
        index = int(receipt["case_index"])
        path = raw_dir / f"case-{index:03d}.json"
        if not path.exists() or file_hash(path) != receipt.get("raw_sha256"):
            raise ValueError(f"raw receipt hash mismatch for case {index}")
    for arm_name, arm in result.get("arms", {}).items():
        if arm_name not in {"lexical", "frontier"}:
            raise ValueError(f"unexpected arm: {arm_name}")
        if int(arm.get("records", 0)) != selected:
            raise ValueError(f"incomplete arm: {arm_name}")
        for metric in ("mrr", "recall_at_1", "recall_at_5", "recall_at_10"):
            value = arm.get(metric)
            if not isinstance(value, (float, int)) or not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"invalid metric {arm_name}.{metric}")
    return {
        "schema_version": "traject-bench-frontier-reranker-verification-v1",
        "source_result_sha256": file_hash(result_path),
        "cases_verified": selected,
        "raw_hashes_match": True,
        "outcomes_hidden_from_frontier": True,
        "verification_passed": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verification = verify(args.result, args.raw_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(verification, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(verification, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
