#!/usr/bin/env python3
"""Verify the content-free collision embedding-adaptation receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from nl2sql_real_alias_benchmark import stable_hash


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(raw_path: Path, result_path: Path) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("schema_version") != "frankengate-nl2sql-collision-embedding-adaptation-v1":
        raise ValueError("unexpected adaptation schema")
    if result["dataset"]["raw_sha256"] != file_sha256(raw_path):
        raise ValueError("raw cohort hash mismatch")
    folds = result.get("folds", [])
    databases = result["dataset"]["databases"]
    if len(folds) != len(databases) or {fold["held_out_database"] for fold in folds} != set(databases):
        raise ValueError("database-family holdout coverage mismatch")
    arms = set(result["aggregate"])
    expected_arms = {"identifier_embedding", "table_embedding", "structured", "hard_negative_adapter"}
    if arms != expected_arms:
        raise ValueError("adaptation arm mismatch")
    for fold in folds:
        if set(fold["arms"]) != expected_arms:
            raise ValueError("fold arm mismatch")
        for arm in expected_arms:
            values = fold["arms"][arm]
            if values["cases"] != fold["test_cases"]:
                raise ValueError("fold case count mismatch")
            for key in ("mrr", "recall_at_1", "recall_at_5", "same_scope_collision_before_target"):
                if not 0.0 <= float(values[key]) <= 1.0:
                    raise ValueError(f"metric outside [0,1]: {arm}/{key}")
    unsigned = dict(result)
    expected_hash = unsigned.pop("result_sha256")
    if stable_hash(unsigned) != expected_hash:
        raise ValueError("result hash mismatch")
    return {"status": "verified", "databases": databases, "folds": len(folds), "result_sha256": expected_hash, "raw_sha256": file_sha256(raw_path)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.raw, args.result), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
