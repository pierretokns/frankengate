#!/usr/bin/env python3
"""Independently verify the LRAT distilled-ranker receipt."""

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
    if result.get("schema_version") != "frankengate-lrat-trajectory-distilled-ranker-proxy-v1":
        errors.append("schema version mismatch")
    if scan(result):
        errors.append("raw content field present")
    cohort = result.get("cohort", {})
    if cohort.get("trajectories") != 10 or cohort.get("folds") != 10:
        errors.append("unexpected trajectory/fold count")
    arms = result.get("arms", {})
    for arm in ("search_order", "lexical", "trajectory_distilled_ranker"):
        if arm not in arms:
            errors.append(f"missing arm: {arm}")
    protocol = result.get("protocol", {})
    if protocol.get("split") != "leave-one-trajectory-out":
        errors.append("split protocol mismatch")
    if protocol.get("document_ids_in_model_text") is not False:
        errors.append("document IDs may have entered model text")
    boundary = result.get("claim_boundary", {})
    for key in ("silver_relevance_only", "document_correctness_established", "enterprise_artifact_utility_established", "promotion_authorized"):
        if boundary.get(key) is not (True if key == "silver_relevance_only" else False):
            errors.append(f"claim boundary mismatch: {key}")
    if len(result.get("folds", [])) != 10:
        errors.append("fold receipt count mismatch")
    return {"valid": not errors, "errors": errors, "result_sha256": actual}


if __name__ == "__main__":
    verification = verify(Path(sys.argv[1]))
    print(json.dumps(verification, sort_keys=True))
    raise SystemExit(0 if verification["valid"] else 1)
