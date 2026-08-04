#!/usr/bin/env python3
"""Verify the repaired MATM frontier timing receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    recorded = receipt.pop("result_sha256")
    assert recorded == stable_hash(receipt), "result hash mismatch"
    calls = receipt["frontier_calls"]
    rows = calls["receipts"]
    assert calls["requested"] == 9 and calls["completed"] == 9 and calls["failures"] == 0
    assert [row["query"] for row in rows] == list(range(9))
    assert all(float(row["elapsed_ms"]) > 0 for row in rows)
    assert all(int(row["model_tokens_used_diagnostic"]) > 0 for row in rows)
    assert receipt["receipt_repair"]["duplicate_entries_removed"] == 18
    assert receipt["receipt_repair"]["aggregate_metrics_changed"] is False
    expected = {
        "lexical": {"mrr": 1.0, "recall_at_1": 1.0, "recall_at_3": 1.0, "recall_at_5": 1.0, "top_3_success_rate": 0.703704},
        "embedding": {"mrr": 0.674074, "recall_at_1": 0.555556, "recall_at_3": 0.777778, "recall_at_5": 1.0, "top_3_success_rate": 0.666667},
        "frontier": {"mrr": 1.0, "recall_at_1": 1.0, "recall_at_3": 1.0, "recall_at_5": 1.0, "top_3_success_rate": 0.703704},
    }
    assert receipt["aggregate"] == expected
    print(json.dumps({"ok": True, "receipt_sha256": recorded, "query_count": len(rows), "aggregate": expected}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
