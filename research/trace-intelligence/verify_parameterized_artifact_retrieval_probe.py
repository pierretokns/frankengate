#!/usr/bin/env python3
"""Content-free verifier for the parameterized-artifact retrieval receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-parameterized-artifact-retrieval-v1"


def stable_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def verify(path: Path) -> dict[str, Any]:
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if receipt.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected receipt schema")
    source = receipt.get("source", {})
    positive_count = int(source.get("parameter_mutation_count", 0))
    nil_count = int(source.get("template_nil_count", 0))
    if positive_count <= 0 or nil_count <= 0:
        raise ValueError("receipt must contain positive and NIL cohorts")
    aggregate = receipt.get("aggregate", {})
    expected_arms = {"lexical", "template", "template_gate"}
    if set(aggregate) != expected_arms:
        raise ValueError("unexpected retrieval arms")
    for arm, values in aggregate.items():
        if values.get("targets") != positive_count:
            raise ValueError(f"positive count mismatch for {arm}")
        if values.get("nil_targets") != nil_count:
            raise ValueError(f"NIL count mismatch for {arm}")
        if not 0.0 <= float(values.get("mrr", -1.0)) <= 1.0:
            raise ValueError(f"invalid MRR for {arm}")
        if values.get("top1_correct", 0) > positive_count:
            raise ValueError(f"invalid positive count for {arm}")
        if values.get("abstained_nil", 0) + values.get("false_accept_nil", 0) != nil_count:
            raise ValueError(f"NIL partition mismatch for {arm}")
    for row in receipt.get("rows", []):
        if any(key in row for key in ("question", "sql", "query", "template")):
            raise ValueError("raw or unhashed content found in receipt")
    unsigned = dict(receipt)
    observed_hash = unsigned.pop("result_sha256", None)
    expected_hash = hashlib.sha256(stable_json(unsigned)).hexdigest()
    if observed_hash != expected_hash:
        raise ValueError("receipt hash mismatch")
    return {
        "status": "verified",
        "positive_targets": positive_count,
        "nil_targets": nil_count,
        "arms": sorted(expected_arms),
        "result_sha256": observed_hash,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.receipt.resolve()), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
