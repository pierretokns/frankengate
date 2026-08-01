#!/usr/bin/env python3
"""Independent verifier for the retrieval-family comparison receipt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from validated_artifact_retrieval_comparison import run


SCHEMA_VERSION = "frankengate-validated-artifact-retrieval-comparison-verification-v1"


def verify(*, expected: Path, recomputed: Path, **kwargs: object) -> dict[str, object]:
    stored = json.loads(expected.read_text(encoding="utf-8"))
    fresh = run(output=recomputed, **kwargs)
    aggregate = fresh.get("aggregate") or {}
    scoped = aggregate.get("scope_filtered") or {}
    pooled = aggregate.get("pooled") or {}
    checks = {
        "result_hash_matches": stored.get("result_sha256") == fresh.get("result_sha256"),
        "target_count": fresh.get("source", {}).get("target_count") == 10,
        "validated_artifacts_present": int(fresh.get("source", {}).get("validated_artifact_count", 0)) > 0,
        "scoped_lexical_top3_authorized": scoped.get("lexical", {}).get("top3_authorized") == 30,
        "scoped_dense_top3_authorized": scoped.get("dense", {}).get("top3_authorized") == 30,
        "scoped_identifier_top3_authorized": scoped.get("identifier", {}).get("top3_authorized") == 30,
        "scoped_semantic_top3_zero": all(
            scoped.get(arm, {}).get("top3_semantic") == 0
            for arm in ("lexical", "dense", "identifier", "hybrid")
        ),
        "pooled_scope_contamination_measured": (
            pooled.get("lexical", {}).get("scope_correct_top1") is not None
            and pooled.get("dense", {}).get("scope_correct_top1") is not None
        ),
        "claim_boundary_present": bool(fresh.get("claim_boundary", {}).get("causal_agent_benefit_established") is False),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "stored_result_sha256": stored.get("result_sha256"),
        "recomputed_result_sha256": fresh.get("result_sha256"),
        "checks": checks,
        "status": "verified" if all(checks.values()) else "failed",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--recomputed", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--cohort-manifest", type=Path, required=True)
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--dsn-template", required=True)
    parser.add_argument("--database", action="append", required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(
        expected=args.expected.resolve(strict=True),
        recomputed=args.recomputed,
        source_root=args.source_root.resolve(strict=True),
        cohort_manifest=args.cohort_manifest.resolve(strict=True),
        dataset_manifest=args.dataset_manifest.resolve(strict=True),
        dsn_template=args.dsn_template,
        databases=tuple(args.database),
        endpoint=args.endpoint,
    )
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
