#!/usr/bin/env python3
"""Verify the content-minimized frontier SSL-normalizer probe receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-traject-bench-ssl-normalizer-probe-v1"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(result_path: Path) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected SSL-normalizer schema")
    if result.get("dataset", {}).get("raw_content_committed") is not False:
        raise ValueError("raw-content disclosure boundary changed")
    protocol = result.get("protocol", {})
    for field in ("raw_prompts_responses_external",):
        if protocol.get(field) is not True:
            raise ValueError(f"missing external raw-data boundary: {field}")
    claim = result.get("claim_boundary", {})
    for field in ("retrieval_lift_measured", "semantic_alias_quality_measured", "risk_quality_measured", "skill_or_artifact_utility_measured"):
        if claim.get(field) is not False:
            raise ValueError(f"claim boundary overstates {field}")
    aggregate = result.get("aggregate", {})
    selected = int(aggregate.get("selected", 0))
    completed = int(aggregate.get("completed", 0))
    failures = int(aggregate.get("failures", 0))
    records = result.get("records", [])
    if selected <= 0 or len(records) != selected or completed + failures != selected:
        raise ValueError("record counts do not reconcile")
    for field in ("identifier_fidelity_rate", "all_evidence_grounded_rate", "evidence_grounding_rate"):
        value = aggregate.get(field)
        if not isinstance(value, (int, float)) or not 0.0 <= float(value) <= 1.0:
            raise ValueError(f"invalid aggregate {field}")
    for record in records:
        if record.get("status") == "ok":
            if not isinstance(record.get("identifier_fidelity"), bool) or not isinstance(record.get("all_evidence_grounded"), bool):
                raise ValueError("missing per-record grounding booleans")
            if int(record.get("evidence_count", 0)) < int(record.get("grounded_evidence_count", 0)):
                raise ValueError("grounded evidence exceeds evidence count")
        elif record.get("status") != "error":
            raise ValueError("unknown record status")
    verification = {
        "schema_version": "traject-bench-ssl-normalizer-probe-verification-v1",
        "source_result_sha256": file_hash(result_path),
        "selected_verified": selected,
        "completed_verified": completed,
        "failures_verified": failures,
        "claim_boundary_verified": True,
        "verification_passed": True,
    }
    return verification


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
