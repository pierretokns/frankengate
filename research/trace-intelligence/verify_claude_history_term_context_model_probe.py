#!/usr/bin/env python3
"""Verify the content-minimized term-context model probe receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SCHEMA_VERSION = "frankengate-claude-history-term-context-model-probe-v1"


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def verify(input_path: Path, output_path: Path) -> dict[str, object]:
    result = json.loads(input_path.read_text(encoding="utf-8"))
    expected = result.get("result_sha256")
    copy = dict(result)
    copy.pop("result_sha256", None)
    rows = result.get("rows", [])
    checks = {
        "schema_version": result.get("schema_version") == SCHEMA_VERSION,
        "result_hash": expected == digest(copy),
        "raw_content_not_committed": result.get("source", {}).get("raw_content_committed") is False,
        "claim_boundary_present": isinstance(result.get("claim_boundary"), dict),
        "both_cohorts_present": {row.get("cohort") for row in rows} == {"low_context", "high_context"},
        "both_arms_present": all(set(row.get("calls", {})) == {"term_only", "term_plus_context"} for row in rows),
        "nonempty_probe": len(rows) >= 2,
        "summary_present": set(result.get("summary", {})) == {"term_only", "term_plus_context"},
        "no_snippets_emitted": all("left_context" not in row and "right_context" not in row and "term" not in row for row in rows),
    }
    receipt = {
        "schema_version": "frankengate-claude-history-term-context-model-probe-verification-v1",
        "passed": all(checks.values()),
        "checks": checks,
        "result_sha256": expected,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if verify(args.input, args.output)["passed"] else 1)
