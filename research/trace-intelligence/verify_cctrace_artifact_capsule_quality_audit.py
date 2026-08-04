#!/usr/bin/env python3
"""Verify parameter-aware capsule quality-audit invariants."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-cctrace-artifact-capsule-quality-audit-v1"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(result_path: Path) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected capsule quality schema")
    if result.get("source", {}).get("raw_content_committed") is not False:
        raise ValueError("raw-content boundary changed")
    claim = result.get("claim_boundary", {})
    for field in ("replay_executed", "artifact_correctness_measured"):
        if claim.get(field) is not False:
            raise ValueError(f"claim boundary overstates {field}")
    aggregate = result.get("aggregate", {})
    n = int(aggregate.get("records_audited", 0))
    rows = result.get("records", [])
    if n <= 0 or len(rows) != n:
        raise ValueError("record counts do not reconcile")
    for field in ("top_level_tool_order_exact_rate", "per_action_resource_order_exact_rate", "action_count_exact_rate", "input_keys_exact_rate", "safe_template_rate", "literal_only_rate", "not_replayable_rate"):
        value = aggregate.get(field)
        if not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0:
            raise ValueError(f"invalid aggregate {field}")
    for row in rows:
        for field in ("top_level_tool_order_exact", "per_action_resource_order_exact", "action_count_exact", "input_keys_exact"):
            if not isinstance(row.get(field), bool):
                raise ValueError(f"missing row boolean {field}")
    return {"schema_version": "frankengate-cctrace-artifact-quality-verification-v1", "source_result_sha256": file_hash(result_path), "records_verified": n, "claim_boundary_verified": True, "verification_passed": True}


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
