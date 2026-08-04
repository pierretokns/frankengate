#!/usr/bin/env python3
"""Independently verify the separate-explorer probe receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-traject-bench-explorer-probe-v1"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(result_path: Path, raw_dir: Path) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected explorer schema")
    protocol = result.get("protocol", {})
    for key in ("explorer_sees_gold_targets", "explorer_sees_tool_outputs", "tool_endpoints_invoked"):
        if protocol.get(key) is not False:
            raise ValueError(f"unsafe protocol flag: {key}")
    rows = result.get("rows", [])
    selected = int(result.get("dataset", {}).get("selected_cases", 0))
    if len(rows) != selected:
        raise ValueError("row count does not match selected cases")
    completed = [row for row in rows if "explorer" in row]
    if int(result.get("failures", 0)) != selected - len(completed):
        raise ValueError("failure count does not reconcile")
    for row in completed:
        candidate_count = int(row.get("candidate_count", 0))
        explorer = row["explorer"]
        selected_count = int(explorer.get("selected_count", 0))
        if not 1 <= selected_count <= min(16, candidate_count):
            raise ValueError("invalid explorer shortlist size")
        if int(row.get("prompt_chars", 0)) <= 0:
            raise ValueError("missing prompt size")
        for arm_name in ("lexical_name", "lexical_description", "explorer"):
            arm = row[arm_name]
            for key in ("candidate_coverage", "mrr", "recall_at_1", "recall_at_5", "recall_at_10"):
                value = float(arm.get(key, -1))
                if not 0.0 <= value <= 1.0:
                    raise ValueError(f"invalid metric {arm_name}.{key}")
    arms = result.get("arms", {})
    if set(arms) != {"lexical_name", "lexical_description", "explorer"}:
        raise ValueError("unexpected arms")
    for arm in arms.values():
        if int(arm.get("records", -1)) != len(completed):
            raise ValueError("arm records do not reconcile")
    if result.get("claim_boundary", {}).get("validated_artifact_utility_measured") is not False:
        raise ValueError("claim boundary overstates artifact utility")
    return {
        "schema_version": "frankengate-traject-bench-explorer-verification-v1",
        "source_result_sha256": file_hash(result_path),
        "selected_cases_verified": selected,
        "completed_cases_verified": len(completed),
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
