#!/usr/bin/env python3
"""Verify the WMH-BIRD fold-local embedding adapter receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SCHEMA_VERSION = "frankengate-wmh-bird-sql-embedding-adapter-cohort-v1"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def aggregate(rows: list[dict[str, object]], arm: str) -> dict[str, float | int]:
    if not rows:
        raise ValueError("empty evaluation rows")
    fields = (
        "strict_mrr",
        "strict_recall_at_1",
        "strict_recall_at_5",
        "compatible_mrr",
        "compatible_recall_at_1",
        "compatible_recall_at_5",
        "compatible_selected_rate",
        "invalid_selected_count",
        "selected_count",
    )
    result: dict[str, float | int] = {"records": len(rows)}
    result.update({
        field: round(sum(float(row[arm][field]) for row in rows) / len(rows), 6)  # type: ignore[index]
        for field in fields
    })
    return result


def verify(result_path: Path) -> dict[str, object]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected adapter schema")
    dataset = result.get("dataset", {})
    evaluation_tasks = int(dataset.get("evaluation_tasks", 0))
    if evaluation_tasks <= 0 or int(dataset.get("train_tasks", 0)) <= 0:
        raise ValueError("unexpected train/evaluation split")
    rows = result.get("rows", [])
    if len(rows) != evaluation_tasks:
        raise ValueError("evaluation row count does not match dataset")
    seen: set[str] = set()
    for row in rows:
        trace_hash = str(row.get("trace_hash", ""))
        if not trace_hash or trace_hash in seen:
            raise ValueError("duplicate or missing trace hash")
        seen.add(trace_hash)
        for arm in ("lexical", "dense", "adapted"):
            metrics = row.get(arm, {})
            for key in ("strict_mrr", "strict_recall_at_1", "strict_recall_at_5", "compatible_mrr", "compatible_recall_at_1", "compatible_recall_at_5", "compatible_selected_rate"):
                value = float(metrics.get(key, -1))
                if not 0.0 <= value <= 1.0:
                    raise ValueError(f"invalid {arm}.{key}")
    arms = result.get("arms", {})
    for arm in ("lexical", "dense", "adapted"):
        expected = arms.get(arm)
        if not isinstance(expected, dict):
            raise ValueError(f"missing aggregate for {arm}")
        actual = aggregate(rows, arm)
        if expected != actual:
            raise ValueError(f"aggregate mismatch for {arm}: expected {expected!r}, recomputed {actual!r}")
    protocol = result.get("protocol", {})
    if protocol.get("adapter") != "pairwise hinge over absolute-difference and interaction features" or int(protocol.get("training_pair_count", 0)) <= 0:
        raise ValueError("adapter protocol missing")
    boundary = result.get("claim_boundary", {})
    for key in ("custom_enterprise_embedding_established", "semantic_alias_quality_established", "validated_artifact_utility_established", "enterprise_skill_transfer_measured"):
        if boundary.get(key) is not False:
            raise ValueError(f"claim boundary overstates evidence: {key}")
    return {"schema_version": "frankengate-wmh-bird-sql-embedding-adapter-cohort-verification-v1", "source_result_sha256": file_hash(result_path), "train_evaluation_split_verified": True, "evaluation_rows_verified": len(rows), "aggregate_reconciliation_verified": True, "adapter_protocol_verified": True, "claim_boundary_verified": True, "verification_passed": True}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = verify(args.result.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
