#!/usr/bin/env python3
"""Independently verify the content-minimized GLiNER term probe receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def stable_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    recorded = receipt.pop("result_sha256", None)
    expected = stable_hash(receipt)
    assert recorded == expected, f"receipt hash mismatch: {recorded} != {expected}"
    assert receipt["schema_version"] == "frankengate-term-extraction-gliner-benchmark-v1"
    assert receipt["dataset"]["document_count"] == 49
    assert receipt["baseline"]["unique_term_count"] == 15391
    assert receipt["baseline"]["acronym_count"] == 666
    assert receipt["baseline"]["reformulation_candidate_count"] == 191
    assert receipt["gliner"]["entity_count"] == 567
    assert receipt["gliner"]["capability_probe"]["hits"] == 2
    assert receipt["claim_boundary"]["enterprise_term_quality_established"] is False
    assert receipt["claim_boundary"]["retrieval_impact_evaluated"] is False
    # Content minimization invariant: no extracted span or source text is in the receipt.
    forbidden = {"text", "content", "input", "output", "raw_text", "prompt", "sql"}
    def walk(value: Any) -> None:
        if isinstance(value, dict):
            assert not forbidden.intersection(value), f"raw field leaked: {forbidden.intersection(value)}"
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(receipt)
    print(json.dumps({"ok": True, "receipt_sha256": expected, "entities": 567, "probe_hits": 2}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
