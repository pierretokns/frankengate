#!/usr/bin/env python3
"""Independently verify the changed-system authority explorer receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SCHEMA_VERSION = "frankengate-changed-system-authority-explorer-v1"


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
    if dataset.get("case_count") != 10 or dataset.get("candidate_metadata_arms") != ["name_only", "typed_metadata"]:
        raise ValueError("unexpected fixture")
    protocol = result.get("protocol", {})
    for key in ("explorer_sees_gold_validity", "explorer_sees_hidden_expected_indices", "tool_endpoints_invoked"):
        if protocol.get(key) is not False:
            raise ValueError(f"unsafe protocol flag: {key}")
    rows = result.get("rows", [])
    if len(rows) != 20 or result.get("failures") != 0:
        raise ValueError("incomplete result")
    seen: set[tuple[int, str]] = set()
    for row in rows:
        key = (int(row["case_index"]), str(row["arm"]))
        if key in seen:
            raise ValueError("duplicate row")
        seen.add(key)
        raw_path = raw_dir / f"case-{int(row['case_index']):02d}-{row['arm']}.json"
        if not raw_path.exists():
            raise ValueError("missing raw receipt")
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
        value = raw.get("structured_output")
        indices = value.get("selected_indices") if isinstance(value, dict) else None
        if not isinstance(indices, list) or len(indices) > 5 or len(indices) != len(set(indices)):
            raise ValueError("invalid selection")
        if any(not isinstance(item, int) or item < 0 or item >= int(row["candidate_count"]) for item in indices):
            raise ValueError("selection outside candidate pool")
        selection = row.get("selection", {})
        for field in ("target_found", "unsafe_accept", "unsafe_first", "correct_abstention"):
            if not isinstance(selection.get(field), bool):
                raise ValueError(f"invalid boolean metric: {field}")
        for field in ("selected_valid_rate",):
            if not 0.0 <= float(selection.get(field, -1)) <= 1.0:
                raise ValueError(f"invalid bounded metric: {field}")
    boundary = result.get("claim_boundary", {})
    for key in ("enterprise_semantic_alias_quality_established", "causal_artifact_utility_established", "skill_transfer_measured"):
        if boundary.get(key) is not False:
            raise ValueError(f"claim boundary overstates evidence: {key}")
    return {
        "schema_version": "frankengate-changed-system-authority-explorer-verification-v1",
        "source_result_sha256": file_hash(result_path),
        "rows_verified": len(rows),
        "raw_receipts_verified": len(rows),
        "protocol_flags_verified": True,
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
