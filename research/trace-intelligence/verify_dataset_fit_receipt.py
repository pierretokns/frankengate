#!/usr/bin/env python3
"""Verify the dataset-fit audit and its conservative boundary checks."""

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
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
    rows = receipt.get("rows", [])
    by_pair = {(row.get("dataset_id"), row.get("claim")): row for row in rows}
    checks = {
        "schema": receipt.get("schema_version") == "frankengate-dataset-fit-audit-v1",
        "manifest_count": receipt.get("manifest_count") == 44,
        "profiles_present": len(receipt.get("claim_profiles", {})) == 6,
        "rows_present": len(rows) == 44 * 6,
        "defog_direct_nl2sql": by_pair.get(("defog-ai/sql-eval:enterprise-postgresql-96", "nl2sql_schema_retrieval"), {}).get("level") == "direct",
        "bird_direct_nl2sql": by_pair.get(("experiential-labs/wmh-bird-sql-traces", "nl2sql_schema_retrieval"), {}).get("level") == "direct",
        "no_cross_user_direct": not any(row.get("claim") == "cross_user_similarity" and row.get("level") == "direct" for row in rows),
        "no_skill_direct": not any(row.get("claim") == "skill_improvement" and row.get("level") == "direct" for row in rows),
        "no_term_alias_direct": not any(row.get("claim") == "term_alias_quality" and row.get("level") == "direct" for row in rows),
        "hash": receipt.get("result_sha256") == stable_hash({key: value for key, value in receipt.items() if key != "result_sha256"}),
    }
    output = {"schema_version": "frankengate-dataset-fit-verification-v1", "all_passed": all(checks.values()), "checks": checks}
    output["receipt_sha256"] = hashlib.sha256(args.receipt.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output, sort_keys=True))
    return 0 if output["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
