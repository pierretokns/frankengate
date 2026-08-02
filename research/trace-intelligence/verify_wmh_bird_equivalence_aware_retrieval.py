#!/usr/bin/env python3
"""Independent checks for the equivalence-aware retrieval receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def stable_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def verify(path: Path) -> dict[str, object]:
    result = json.loads(path.read_text(encoding="utf-8"))
    assert result["schema_version"] == "frankengate-wmh-bird-equivalence-aware-retrieval-v1"
    replay = result["replay"]
    assert replay["counterfactual_pairs"] == replay["execution_errors"] + replay["result_mismatches"] + replay["result_preserving_candidates"]
    assert replay["result_preserving_candidates"] > 0
    assert result["cohort"]["exact_target"] != result["cohort"]["execution_equivalent_target"]
    for arm, targets in result["metrics"].items():
        assert set(targets) == {"exact", "execution_equivalent", "execution_equivalent_only"}
        for metric in targets.values():
            assert metric["cases"] >= 1
            assert 0.0 <= metric["mrr"] <= 1.0
            assert 0.0 <= metric["recall_at_1"] <= 1.0
            assert 0.0 <= metric["recall_at_5"] <= 1.0
            assert 0.0 <= metric["recall_at_10"] <= 1.0
    claim = result["claim_boundary"]
    assert claim["execution_equivalence_is_semantic_alias"] is False
    assert claim["enterprise_intent_labels_established"] is False
    assert claim["validated_artifact_utility_established"] is False
    body = dict(result)
    digest = body.pop("result_sha256")
    assert digest == stable_hash(body)
    verification = {"schema_version": "frankengate-wmh-bird-equivalence-aware-retrieval-verification-v1", "passed": True, "result_sha256": digest}
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
