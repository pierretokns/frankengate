#!/usr/bin/env python3
"""Verify cross-cohort command-transfer receipt invariants."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def verify(path: Path) -> dict[str, object]:
    result = json.loads(path.read_text(encoding="utf-8"))
    assert result["schema_version"] == "frankengate-claude-cross-cohort-command-transfer-v1"
    assert len(result["sources"]) >= 2
    assert result["combined"]["labeled_occurrences"] > 0
    assert result["combined"]["cohort_count"] == len(result["sources"])
    for representation in ("exact", "normalized"):
        metric = result["cross_cohort_transfer"][representation]
        assert metric["eligible_successes"] + metric["eligible_failures"] == metric["eligible_occurrences"]
        assert 0.0 <= metric["cross_cohort_success_rate"] <= 1.0
        assert metric["cross_cohort_artifact_count"] >= 0
    claim = result["claim_boundary"]
    assert claim["user_intent_labels"] is False
    assert claim["authority_labels"] is False
    assert claim["semantic_equivalence"] is False
    assert claim["causal_transfer"] is False
    body = dict(result)
    actual = body.pop("result_sha256")
    assert actual == digest(body)
    verification = {"schema_version": "frankengate-claude-cross-cohort-command-transfer-verification-v1", "passed": True, "result_sha256": actual}
    print(json.dumps(verification, sort_keys=True))
    return verification


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
