#!/usr/bin/env python3
"""Verify one replay-backed WMH-BIRD SQL explorer receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-wmh-bird-sql-explorer-probe-v1"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(result_path: Path, raw_dir: Path) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected SQL explorer schema")
    protocol = result.get("protocol", {})
    for key in ("explorer_sees_sql", "explorer_sees_replay_outcomes", "explorer_sees_gold_targets", "tool_endpoints_invoked"):
        if protocol.get(key) is not False:
            raise ValueError(f"unsafe protocol flag: {key}")
    rows = result.get("rows", [])
    if len(rows) != int(result.get("dataset", {}).get("selected_cases", 0)) or len(rows) != 8:
        raise ValueError("row count does not reconcile")
    if result.get("failures") != 0:
        raise ValueError("frontier SQL explorer run is incomplete")
    for index, row in enumerate(rows):
        candidate_count = int(row.get("candidate_count", 0))
        if candidate_count <= 0 or not row.get("target_tables"):
            raise ValueError("missing candidate or target data")
        raw_path = raw_dir / f"case-{index:03d}.json"
        if not raw_path.exists():
            raise ValueError(f"missing raw receipt {raw_path}")
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        value = raw.get("structured_output")
        indices = value.get("selected_indices") if isinstance(value, dict) else None
        if not isinstance(indices, list) or not indices or len(indices) > 8 or len(indices) != len(set(indices)):
            raise ValueError("invalid raw explorer selection")
        if any(int(item) < 0 or int(item) >= candidate_count for item in indices):
            raise ValueError("raw selection is outside candidate pool")
        for arm_name in ("lexical", "explorer"):
            arm = row.get(arm_name, {})
            for key in ("strict_mrr", "strict_recall_at_1", "strict_recall_at_5", "strict_recall_at_10", "compatible_mrr", "compatible_recall_at_1", "compatible_recall_at_5", "compatible_recall_at_10", "compatible_selected_rate"):
                value = float(arm.get(key, -1))
                if not 0.0 <= value <= 1.0:
                    raise ValueError(f"invalid metric {arm_name}.{key}")
    if result.get("claim_boundary", {}).get("semantic_alias_quality_established") is not False or result.get("claim_boundary", {}).get("validated_artifact_utility_established") is not False:
        raise ValueError("claim boundary overstates evidence")
    return {
        "schema_version": "frankengate-wmh-bird-sql-explorer-verification-v1",
        "source_result_sha256": file_hash(result_path),
        "selected_cases_verified": len(rows),
        "raw_receipts_verified": len(rows),
        "protocol_flags_verified": True,
        "metrics_reconciled": True,
        "claim_boundary_verified": True,
        "verification_passed": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = verify(args.result, args.raw_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
