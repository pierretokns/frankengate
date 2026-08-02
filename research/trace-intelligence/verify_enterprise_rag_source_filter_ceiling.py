#!/usr/bin/env python3
"""Verify the aggregate-only EnterpriseRAG source-filter ceiling receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-enterprise-rag-source-filter-ceiling-v1"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(result_path: Path) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected source-filter receipt schema")
    protocol = result.get("protocol", {})
    if protocol.get("filter_is_oracle") is not True or protocol.get("filter_is_not_authorization") is not True:
        raise ValueError("oracle filter boundary is missing")
    boundary = result.get("claim_boundary", {})
    for field in ("production_metadata_retrieval_measured", "hard_negative_semantic_labels_established", "ontology_quality_measured", "trace_learning_measured", "artifact_utility_measured"):
        if boundary.get(field) is not False:
            raise ValueError(f"claim boundary overstates {field}")
    rows = result.get("rows")
    expected_rows = result.get("dataset", {}).get("questions")
    if not isinstance(rows, list) or not isinstance(expected_rows, int) or len(rows) != expected_rows or not rows:
        raise ValueError("row count mismatch")
    for row in rows:
        for arm in ("unfiltered", "oracle_source_filtered"):
            metrics = row.get(arm)
            if not isinstance(metrics, dict):
                raise ValueError(f"missing {arm} metrics")
            for field in ("mrr", "recall_at_1", "recall_at_5", "recall_at_10", "evidence_recall_at_10"):
                value = metrics.get(field)
                if not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0:
                    raise ValueError(f"invalid {arm}.{field}")
            for field in ("invalid_extra_at_10", "wrong_source_extra_at_10", "same_source_non_target_at_10", "ranked_count"):
                value = metrics.get(field)
                if not isinstance(value, int) or value < 0:
                    raise ValueError(f"invalid {arm}.{field}")
    verification = {
        "schema_version": "frankengate-enterprise-rag-source-filter-ceiling-verification-v1",
        "source_result_sha256": file_sha256(result_path),
        "questions_verified": len(rows),
        "oracle_boundary_verified": True,
        "claim_boundary_verified": True,
        "verification_passed": True,
    }
    return verification


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
