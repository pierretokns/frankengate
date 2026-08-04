#!/usr/bin/env python3
"""Independent receipt verifier for the LRAT trajectory retrieval proxy."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


FORBIDDEN = {"query", "snippet", "document_id", "docid", "prompt", "sql", "output"}


def scan(value: object) -> bool:
    if isinstance(value, dict):
        return any(str(key).lower() in FORBIDDEN or scan(child) for key, child in value.items())
    if isinstance(value, list):
        return any(scan(child) for child in value)
    return False


def verify(path: Path) -> dict[str, object]:
    result = json.loads(path.read_text(encoding="utf-8"))
    recorded = result.pop("result_sha256", None)
    actual = hashlib.sha256(json.dumps(result, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    errors: list[str] = []
    if recorded != actual:
        errors.append("receipt hash mismatch")
    if result.get("schema_version") != "frankengate-lrat-trajectory-retrieval-proxy-v1":
        errors.append("schema version mismatch")
    if scan(result):
        errors.append("raw content field present")
    if result.get("cohort", {}).get("trajectories_with_exposure_and_browse_positive") != 10:
        errors.append("unexpected trajectory count")
    for arm in ("search_order", "lexical", "dense"):
        if arm not in result.get("arms", {}):
            errors.append(f"missing arm: {arm}")
    if result.get("claim_boundary", {}).get("enterprise_artifact_utility_established") is not False:
        errors.append("claim boundary widened")
    return {"valid": not errors, "errors": errors, "result_sha256": actual}


if __name__ == "__main__":
    verification = verify(Path(sys.argv[1]))
    print(json.dumps(verification, sort_keys=True))
    raise SystemExit(0 if verification["valid"] else 1)
