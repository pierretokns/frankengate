#!/usr/bin/env python3
"""Verify the local-only cross-user candidate-generation receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


SCHEMA_VERSION = "frankengate-dataclaw-cross-user-dense-candidates-v1"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(result_path: Path) -> dict[str, object]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected schema")
    source = result.get("source", {})
    aggregate = result.get("aggregate", {})
    rows = result.get("rows", [])
    if int(source.get("left_session_count", 0)) != len(rows) or int(source.get("right_session_count", 0)) != 38:
        raise ValueError("unexpected session counts")
    if int(aggregate.get("queries", 0)) != len(rows) or int(aggregate.get("candidate_pool", 0)) != 38:
        raise ValueError("aggregate mismatch")
    protocol = result.get("protocol", {})
    if protocol.get("session_text_stays_local") is not True or protocol.get("semantic_adjudication") is not False:
        raise ValueError("unsafe protocol flags")
    for row in rows:
        for key in ("left_session_hash", "lexical_top_pair_hash", "dense_top_pair_hash"):
            if not isinstance(row.get(key), str) or not row[key]:
                raise ValueError("missing content hash")
        for key in ("lexical_top_score", "dense_top_score", "top_k_set_jaccard", "lexical_top_tool_jaccard", "dense_top_tool_jaccard"):
            value = float(row.get(key, -1))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"invalid bounded metric {key}")
    boundary = result.get("claim_boundary", {})
    for key in ("cross_user_task_equivalence_established", "skill_gap_established", "enterprise_collaboration_value_established"):
        if boundary.get(key) is not False:
            raise ValueError("claim boundary overstates evidence")
    return {"schema_version": "frankengate-dataclaw-cross-user-dense-candidates-verification-v1", "source_result_sha256": file_hash(result_path), "queries_verified": len(rows), "local_only_protocol_verified": True, "claim_boundary_verified": True, "verification_passed": True}


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
