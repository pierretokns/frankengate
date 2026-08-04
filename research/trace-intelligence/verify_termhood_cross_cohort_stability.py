#!/usr/bin/env python3
"""Verify termhood cross-cohort stability receipt invariants."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def verify(path: Path) -> dict[str, object]:
    result = json.loads(path.read_text(encoding="utf-8"))
    assert result["schema_version"] == "frankengate-termhood-cross-cohort-stability-v1"
    cohorts = result["cohorts"]
    assert len(cohorts) >= 2
    for row in cohorts.values():
        assert row["document_count"] > 0
        assert row["unique_term_count"] > 0
        assert row["top_term_count"] > 0
    for row in result["pairwise_top_term_overlap"].values():
        assert 0.0 <= row["jaccard_top_terms"] <= 1.0
        assert row["shared_top_terms"] >= 0
    frequency = result["top_terms_by_cohort_frequency"]
    assert frequency["one_cohort"] + frequency["two_or_more_cohorts"] == frequency["unique_top_hashes"]
    claim = result["claim_boundary"]
    assert claim["alias_quality"] is False
    assert claim["enterprise_concept_quality"] is False
    assert claim["semantic_equivalence"] is False
    body = dict(result)
    actual = body.pop("result_sha256")
    assert actual == digest(body)
    verification = {"schema_version": "frankengate-termhood-cross-cohort-stability-verification-v1", "passed": True, "result_sha256": actual}
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
