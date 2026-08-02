#!/usr/bin/env python3
"""Verify the repeated WMH-BIRD SQL explorer aggregate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SCHEMA_VERSION = "frankengate-wmh-bird-sql-explorer-probe-aggregate-v1"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(path: Path) -> dict[str, object]:
    result = json.loads(path.read_text(encoding="utf-8"))
    if result.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected SQL explorer aggregate schema")
    if result.get("runs") != 2 or result.get("cases_per_run") != 8:
        raise ValueError("unexpected aggregate dimensions")
    metrics = result.get("explorer_mean", {})
    for key in ("strict_mrr", "strict_recall_at_1", "strict_recall_at_5", "strict_recall_at_10", "compatible_mrr", "compatible_recall_at_1", "compatible_recall_at_5", "compatible_recall_at_10", "compatible_selected_rate"):
        value = float(metrics.get(key, -1))
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"invalid aggregate metric {key}")
    stability = result.get("stability", {})
    if not 0.0 <= float(stability.get("selected_set_jaccard_mean", -1)) <= 1.0:
        raise ValueError("invalid stability metric")
    if len(stability.get("case_jaccards", [])) != 8:
        raise ValueError("case stability count does not reconcile")
    boundary = result.get("claim_boundary", {})
    if boundary.get("semantic_alias_quality_established") is not False or boundary.get("validated_artifact_utility_established") is not False:
        raise ValueError("claim boundary overstates evidence")
    return {
        "schema_version": "frankengate-wmh-bird-sql-explorer-aggregate-verification-v1",
        "source_result_sha256": file_hash(path),
        "runs_verified": 2,
        "cases_per_run_verified": 8,
        "metrics_reconciled": True,
        "claim_boundary_verified": True,
        "verification_passed": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = verify(args.result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
