#!/usr/bin/env python3
"""Independently verify the dense/frontier WMH-BIRD cohort receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SCHEMA_VERSION = "frankengate-wmh-bird-sql-dense-frontier-cohort-v1"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(result_path: Path, raw_dir: Path) -> dict[str, object]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected schema")
    dataset = result.get("dataset", {})
    selected = int(dataset.get("selected_cases", 0))
    if selected != 44 or len(result.get("rows", [])) != selected or result.get("failures") != 0:
        raise ValueError("incomplete 44-case cohort")
    protocol = result.get("protocol", {})
    for key in ("explorer_sees_sql", "explorer_sees_replay_outcomes", "explorer_sees_gold_targets", "tool_endpoints_invoked"):
        if protocol.get(key) is not False:
            raise ValueError(f"unsafe protocol flag {key}")
    for index, row in enumerate(result["rows"]):
        raw_path = raw_dir / f"case-{index:03d}.json"
        if not raw_path.exists():
            raise ValueError("missing raw frontier receipt")
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        value = raw.get("structured_output")
        indices = value.get("selected_indices") if isinstance(value, dict) else None
        if not isinstance(indices, list) or not indices or len(indices) > 8 or len(indices) != len(set(indices)):
            raise ValueError("invalid frontier selection")
        if any(not isinstance(item, int) or item < 0 or item >= int(row["candidate_count"]) for item in indices):
            raise ValueError("selection outside candidate pool")
        for arm in ("lexical", "dense", "frontier"):
            metrics = row.get(arm, {})
            for key in ("strict_mrr", "strict_recall_at_1", "strict_recall_at_5", "strict_recall_at_10", "compatible_mrr", "compatible_recall_at_1", "compatible_recall_at_5", "compatible_recall_at_10", "compatible_selected_rate"):
                value = float(metrics.get(key, -1))
                if not 0.0 <= value <= 1.0:
                    raise ValueError(f"invalid metric {arm}.{key}")
    boundary = result.get("claim_boundary", {})
    if boundary.get("semantic_alias_quality_established") is not False or boundary.get("validated_artifact_utility_established") is not False:
        raise ValueError("claim boundary overstates evidence")
    return {"schema_version": "frankengate-wmh-bird-sql-dense-frontier-cohort-verification-v1", "source_result_sha256": file_hash(result_path), "selected_cases_verified": selected, "raw_receipts_verified": selected, "protocol_flags_verified": True, "claim_boundary_verified": True, "verification_passed": True}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = verify(args.result.resolve(), args.raw_dir.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
