#!/usr/bin/env python3
"""Independent receipt and corpus-conformance verifier for schema retrieval."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from nl2sql_real_alias_cohort import schema_from_ddl
from nl2sql_schema_adaptive_benchmark import DBS, load_test_cases, make_docs, stable_hash


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--ddl-root", type=Path, required=True)
    parser.add_argument("--cohort-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    result = json.loads(args.result.read_text(encoding="utf-8"))
    checks: dict[str, bool] = {}
    expected_hash = result.get("result_sha256")
    unhashed = dict(result)
    unhashed.pop("result_sha256", None)
    checks["result_hash"] = expected_hash == stable_hash(unhashed)

    schemas = {db: schema_from_ddl(args.ddl_root / db / f"{db}.sql") for db in DBS}
    docs = make_docs(schemas)
    cases = load_test_cases(
        source_root=args.source_root,
        cohort_manifest=args.cohort_manifest,
        schemas=schemas,
        docs=docs,
    )
    checks["document_count"] = result["dataset"]["documents"] == len(docs)
    checks["case_count"] = result["dataset"]["cases"] == len(cases)
    checks["raw_not_committed"] = result["dataset"]["raw_content_committed"] is False

    expected_dll = {
        db: sha256_file(args.ddl_root / db / f"{db}.sql") for db in DBS
    }
    checks["ddl_hashes"] = result["dataset"]["ddl_sha256"] == expected_dll
    manifest_hash = sha256_file(args.cohort_manifest)
    checks["cohort_hash"] = result["dataset"]["cohort_manifest_sha256"] == manifest_hash

    fold_databases = [fold["held_out_database"] for fold in result["folds"]]
    checks["fold_coverage"] = sorted(fold_databases) == sorted(DBS)
    expected_counts = Counter(case["scope_db"] for case in cases)
    checks["fold_case_counts"] = all(
        fold["test_cases"] == expected_counts[fold["held_out_database"]]
        for fold in result["folds"]
    )

    modes = {"scope_filtered", "pooled"}
    arms = {"exact_scope", "lexical", "frozen_embedding", "schema_adaptive_pair_scorer"}
    checks["mode_and_arm_coverage"] = all(
        set(fold["modes"]) == modes
        and all(set(fold["modes"][mode]) == arms for mode in modes)
        for fold in result["folds"]
    )
    bounded = True
    for mode in modes:
        for arm in arms:
            aggregate = result["aggregate"][mode][arm]
            bounded = bounded and all(
                0.0 <= float(aggregate[key]) <= 1.0
                for key in (
                    "mrr",
                    "recall_at_1",
                    "recall_at_5",
                    "recall_at_10",
                    "same_scope_collision_before_target",
                    "wrong_scope_collision_before_target",
                )
            )
            bounded = bounded and aggregate["cases"] == len(cases)
    checks["metric_bounds_and_case_totals"] = bounded

    receipt = {
        "schema_version": "frankengate-nl2sql-schema-adaptive-retrieval-verification-v1",
        "source_result_sha256": expected_hash,
        "checks": checks,
        "status": "verified" if all(checks.values()) else "failed",
        "claim_boundary": "Receipt, source-hash, split, and metric-conformance verification only; no semantic-alias or downstream-agent claim.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))
    return 0 if receipt["status"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
