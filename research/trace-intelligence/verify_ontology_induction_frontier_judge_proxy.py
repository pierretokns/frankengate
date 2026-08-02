#!/usr/bin/env python3
"""Verify the content-minimized ontology silver-judge receipt."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


FORBIDDEN = {"prompt", "sql", "tool_arguments", "command", "rows", "content", "transcript", "raw_text", "output", "document_text"}


def scan(value: object) -> bool:
    if isinstance(value, dict):
        return any(str(key).lower() in FORBIDDEN or scan(child) for key, child in value.items())
    if isinstance(value, list):
        return any(scan(child) for child in value)
    return False


def verify(path: Path) -> dict[str, object]:
    result = json.loads(path.read_text(encoding="utf-8"))
    recorded = result.pop("result_sha256", None)
    actual = hashlib.sha256(json.dumps(result, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    errors: list[str] = []
    if recorded != actual:
        errors.append("receipt hash mismatch")
    if result.get("schema_version") != "frankengate-ontology-induction-frontier-judge-proxy-v1":
        errors.append("schema version mismatch")
    if scan(result):
        errors.append("raw content field present")
    if result.get("dataset", {}).get("documents") != 5:
        errors.append("unexpected document count")
    for arm in ("goi_proposal", "ontogpt_population"):
        summary = result.get("arms", {}).get(arm, {})
        if summary.get("completed") != 5 or summary.get("failures") != 0:
            errors.append(f"incomplete arm: {arm}")
        for field in ("supported_rate", "unsupported_rate", "unclear_rate"):
            if not 0.0 <= float(summary.get(field, -1.0)) <= 1.0:
                errors.append(f"invalid {field}: {arm}")
    if len(result.get("records", [])) != 10:
        errors.append("unexpected record count")
    boundary = result.get("claim_boundary", {})
    for key in ("ontology_correctness_established", "human_adjudication_established", "replay_utility_established"):
        if boundary.get(key) is not False:
            errors.append(f"claim boundary widened: {key}")
    return {"valid": not errors, "errors": errors, "result_sha256": actual}


if __name__ == "__main__":
    verification = verify(Path(sys.argv[1]))
    print(json.dumps(verification, sort_keys=True))
    raise SystemExit(0 if verification["valid"] else 1)
