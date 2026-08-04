#!/usr/bin/env python3
"""Verify aggregate invariants for the Claude command normalization audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def verify(path: Path) -> dict[str, object]:
    result = json.loads(path.read_text(encoding="utf-8"))
    assert result["schema_version"] == "frankengate-claude-command-artifact-normalization-v1"
    assert result["source"]["path_count"] > 0
    for name, metrics in result["representations"].items():
        assert metrics["labeled_occurrences"] > 0
        assert metrics["distinct_artifacts"] > 0
        assert metrics["success_occurrences"] + metrics["failure_occurrences"] == metrics["labeled_occurrences"]
        assert metrics["same_scope_later_success"] + metrics["same_scope_later_failure"] == metrics["repeated_after_same_scope_success"]
        assert 0.0 <= metrics["overall_success_rate"] <= 1.0
        assert 0.0 <= metrics["same_scope_success_rate"] <= 1.0
        assert 0.0 <= metrics["other_scope_success_rate"] <= 1.0
        if name == "exact":
            assert metrics["parameterized_buckets_with_multiple_exact_commands"] == 0
    claim = result["claim_boundary"]
    assert claim["commands_executed"] is False
    assert claim["intent_labels"] is False
    assert claim["semantic_equivalence"] is False
    body = dict(result)
    actual = body.pop("result_sha256")
    assert actual == digest(body)
    verification = {"schema_version": "frankengate-claude-command-artifact-normalization-verification-v1", "passed": True, "result_sha256": actual}
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
