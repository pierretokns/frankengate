#!/usr/bin/env python3
"""Verify the content-minimized parameter-aware artifact probe receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-cctrace-artifact-capsule-probe-v1"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(result_path: Path) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected artifact capsule schema")
    if result.get("dataset", {}).get("raw_content_committed") is not False:
        raise ValueError("raw-content disclosure boundary changed")
    protocol = result.get("protocol", {})
    if protocol.get("raw_prompts_responses_external") is not True or protocol.get("replay_executed") is not False:
        raise ValueError("protocol boundary changed")
    claim = result.get("claim_boundary", {})
    for field in ("replay_executed", "artifact_utility_measured", "semantic_alias_quality_measured"):
        if claim.get(field) is not False:
            raise ValueError(f"claim boundary overstates {field}")
    aggregate = result.get("aggregate", {})
    selected = int(aggregate.get("selected", 0))
    completed = int(aggregate.get("completed", 0))
    failures = int(aggregate.get("failures", 0))
    records = result.get("records", [])
    if selected <= 0 or len(records) != selected or completed + failures != selected:
        raise ValueError("record counts do not reconcile")
    for field in ("tool_names_exact_order_rate", "action_count_exact_rate", "input_key_fidelity", "template_grounding_rate", "all_evidence_grounded_rate", "evidence_grounding_rate", "safe_template_rate", "literal_only_rate", "not_replayable_rate"):
        value = aggregate.get(field)
        if not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0:
            raise ValueError(f"invalid aggregate {field}")
    for record in records:
        if record.get("status") == "ok":
            for field in ("tool_names_exact_order", "action_count_exact", "all_evidence_grounded"):
                if not isinstance(record.get(field), bool):
                    raise ValueError(f"missing per-record boolean {field}")
            if not 0.0 <= float(record.get("input_key_fidelity", -1)) <= 1.0:
                raise ValueError("invalid input-key fidelity")
        elif record.get("status") != "error":
            raise ValueError("unknown record status")
    return {"schema_version": "frankengate-cctrace-artifact-capsule-verification-v1", "source_result_sha256": file_hash(result_path), "selected_verified": selected, "completed_verified": completed, "failures_verified": failures, "claim_boundary_verified": True, "verification_passed": True}


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
