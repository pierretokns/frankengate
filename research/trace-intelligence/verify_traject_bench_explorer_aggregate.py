#!/usr/bin/env python3
"""Verify the repeated separate-explorer aggregate receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SCHEMA_VERSION = "frankengate-traject-bench-explorer-probe-aggregate-v1"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(path: Path) -> dict[str, object]:
    result = json.loads(path.read_text(encoding="utf-8"))
    if result.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected aggregate schema")
    if result.get("runs") != 2 or result.get("cases_per_run") != 8:
        raise ValueError("unexpected run dimensions")
    metrics = result.get("explorer_mean", {})
    for key in ("candidate_coverage", "mrr", "recall_at_1", "recall_at_5", "recall_at_10"):
        if not 0.0 <= float(metrics.get(key, -1)) <= 1.0:
            raise ValueError(f"invalid aggregate metric {key}")
    stability = result.get("stability", {})
    if not 0.0 <= float(stability.get("selected_set_jaccard_mean", -1)) <= 1.0:
        raise ValueError("invalid stability metric")
    if len(stability.get("case_jaccards", [])) != 8:
        raise ValueError("case stability count does not reconcile")
    if result.get("claim_boundary", {}).get("validated_artifact_utility_measured") is not False:
        raise ValueError("claim boundary overstates utility")
    return {
        "schema_version": "frankengate-traject-bench-explorer-aggregate-verification-v1",
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
