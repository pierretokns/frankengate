#!/usr/bin/env python3
"""Verify cctrace normalized-output quality audit invariants."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-cctrace-ssl-normalizer-quality-audit-v1"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(result_path: Path) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected quality-audit schema")
    if result.get("source", {}).get("raw_content_committed") is not False:
        raise ValueError("raw-content disclosure boundary changed")
    claim = result.get("claim_boundary", {})
    for field in ("human_semantic_quality_measured", "task_correctness_measured", "skill_or_artifact_utility_measured"):
        if claim.get(field) is not False:
            raise ValueError(f"claim boundary overstates {field}")
    aggregate = result.get("aggregate", {})
    n = int(aggregate.get("records_audited", 0))
    rows = result.get("records", [])
    if n <= 0 or len(rows) != n:
        raise ValueError("record counts do not reconcile")
    for field in ("action_order_exact_rate", "action_type_accuracy", "mean_scene_action_coverage", "all_actions_in_scene_rate", "transition_refs_valid_rate"):
        value = aggregate.get(field)
        if not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0:
            raise ValueError(f"invalid aggregate {field}")
    for row in rows:
        for field in ("action_order_exact", "transition_refs_valid", "all_actions_in_scene"):
            if not isinstance(row.get(field), bool):
                raise ValueError(f"missing row boolean {field}")
        if not 0.0 <= float(row.get("action_type_accuracy", -1)) <= 1.0 or not 0.0 <= float(row.get("scene_action_coverage", -1)) <= 1.0:
            raise ValueError("invalid row metric")
    return {"schema_version": "frankengate-cctrace-ssl-quality-verification-v1", "source_result_sha256": file_hash(result_path), "records_verified": n, "claim_boundary_verified": True, "verification_passed": True}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verification = verify(args.result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(verification, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(verification, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
