#!/usr/bin/env python3
"""Verify the changed-system authority replay bridge receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SCHEMA_VERSION = "frankengate-changed-system-authority-replay-bridge-v1"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(result_path: Path) -> dict[str, object]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected bridge schema")
    protocol = result.get("protocol", {})
    for key in ("frontier_selection_replayed", "independent_sql_execution", "typed_gate_reexecuted"):
        if protocol.get(key) is not True:
            raise ValueError(f"missing protocol guarantee: {key}")
    rows = result.get("rows", [])
    if len(rows) != 30:
        raise ValueError("expected 30 case/arm rows")
    seen: set[tuple[int, str]] = set()
    for row in rows:
        key = (int(row["case_index"]), str(row["arm"]))
        if key in seen:
            raise ValueError("duplicate case/arm row")
        seen.add(key)
        for item in row.get("typed_gate", []):
            if not isinstance(item.get("accepted"), bool) or not isinstance(item.get("safe_correct"), bool) or not isinstance(item.get("unsafe_accept"), bool):
                raise ValueError("invalid replay booleans")
            execution = item.get("execution", {})
            if not isinstance(execution.get("semantic_result_match"), bool):
                raise ValueError("missing independent execution result")
    boundary = result.get("claim_boundary", {})
    for key in ("enterprise_artifact_utility_established", "causal_skill_improvement_established"):
        if boundary.get(key) is not False:
            raise ValueError(f"claim boundary overstates evidence: {key}")
    return {"schema_version": "frankengate-changed-system-authority-replay-bridge-verification-v1", "source_result_sha256": file_hash(result_path), "rows_verified": len(rows), "independent_execution_verified": True, "claim_boundary_verified": True, "verification_passed": True}


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
