#!/usr/bin/env python3
"""Independently verify the content-free model-dream quality receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-natural-model-dream-procedure-verification-v1"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    rows = receipt.get("rows", [])
    checks: dict[str, Any] = {
        "schema_present": receipt.get("schema_version") == "frankengate-natural-model-dream-procedure-v1",
        "rows_present": isinstance(rows, list) and bool(rows),
        "all_rows_content_free": receipt.get("content_policy", {}).get("raw_trace_content_emitted") is False
        and receipt.get("content_policy", {}).get("model_response_emitted") is False,
        "quality_count_matches_rows": receipt.get("projects_quality_passed") == sum(
            bool(row.get("checks", {}).get("quality_passed")) for row in rows
        ),
        "no_semantic_claim": receipt.get("claim_boundary", {}).get("semantic_procedure_quality_confirmed") is False,
        "no_utility_claim": receipt.get("claim_boundary", {}).get("causal_skill_or_memory_utility_confirmed") is False,
        "row_digests_present": all(
            isinstance(row.get("model_response_sha256"), str)
            and len(row["model_response_sha256"]) == 64
            for row in rows
        ),
    }
    result = {
        "schema_version": SCHEMA_VERSION,
        "receipt": args.receipt.name,
        "checks": checks,
        "all_passed": all(checks.values()),
        "projects_verified": len(rows),
        "projects_quality_passed": receipt.get("projects_quality_passed", 0),
        "receipt_sha256": hashlib.sha256(args.receipt.read_bytes()).hexdigest(),
        "raw_content_policy": {"model_response_emitted": False, "trace_content_emitted": False},
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"all_passed": result["all_passed"], "projects_verified": len(rows)}, sort_keys=True))
    return 0 if result["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
