#!/usr/bin/env python3
"""Prevent accidental aggregation across non-identical experiment cohorts.

The ontology projection and dense/frontier receipts use the same pinned source
files but different evaluation subsets and protocols.  A shared source hash is
therefore not enough to justify a pooled metric or a cascade claim.  This
guard compares cohort identity and emits a content-free incompatibility
receipt; it exits non-zero when ``--require-aligned`` is requested.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-cohort-comparison-guard-v1"


def sha256_json(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def identity(receipt: dict[str, Any]) -> dict[str, Any]:
    source = receipt.get("source", {})
    cohort = receipt.get("cohort", receipt.get("dataset", {}))
    return {
        "traces_sha256": source.get("traces_sha256"),
        "manifest_sha256": source.get("manifest_sha256"),
        "sqlite_root": source.get("sqlite_root"),
        "evaluation_tasks": cohort.get("evaluation_tasks", cohort.get("selected_cases")),
        "database_families": tuple(sorted(cohort.get("database_families", []))) if isinstance(cohort.get("database_families"), list) else cohort.get("database_families"),
        "split": cohort.get("split"),
        "candidate_pool": cohort.get("candidate_pool"),
        "strict_target": cohort.get("strict_target"),
        "compatible_target": cohort.get("compatible_target", cohort.get("target")),
    }


def run(left_path: Path, right_path: Path, output: Path, require_aligned: bool = False) -> int:
    left = json.loads(left_path.read_text(encoding="utf-8"))
    right = json.loads(right_path.read_text(encoding="utf-8"))
    left_id = identity(left)
    right_id = identity(right)
    differences = [key for key in left_id if left_id[key] != right_id[key]]
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "inputs": {
            "left": {"path": str(left_path), "receipt_sha256": left.get("result_sha256")},
            "right": {"path": str(right_path), "receipt_sha256": right.get("result_sha256")},
        },
        "source_hashes_shared": left_id["traces_sha256"] == right_id["traces_sha256"] and left_id["manifest_sha256"] == right_id["manifest_sha256"],
        "cohort_identity": {"left": left_id, "right": right_id},
        "aligned": not differences,
        "differences": differences,
        "claim_boundary": {
            "pooled_metric_permitted": not differences,
            "cascade_claim_permitted": not differences,
            "reason": "Shared source files do not make different task subsets, candidate pools, or split protocols one cohort; require exact cohort identity before aggregation.",
        },
    }
    result["result_sha256"] = sha256_json(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"aligned": result["aligned"], "differences": differences, "source_hashes_shared": result["source_hashes_shared"]}, sort_keys=True))
    return 0 if (result["aligned"] or not require_aligned) else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--left", type=Path, required=True)
    parser.add_argument("--right", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-aligned", action="store_true")
    args = parser.parse_args()
    return run(args.left, args.right, args.output, require_aligned=args.require_aligned)


if __name__ == "__main__":
    raise SystemExit(main())
