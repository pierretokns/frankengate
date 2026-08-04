#!/usr/bin/env python3
"""Independent verifier for the artifact-pool semantic coverage receipt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from validated_artifact_pool_coverage import run


SCHEMA_VERSION = "frankengate-validated-artifact-pool-coverage-verification-v1"


def verify(*, expected: Path, recomputed: Path, **kwargs: object) -> dict[str, object]:
    stored = json.loads(expected.read_text(encoding="utf-8"))
    fresh = run(output=recomputed, **kwargs)
    aggregate = fresh.get("aggregate") or {}
    checks = {
        "result_hash_matches": stored.get("result_sha256") == fresh.get("result_sha256"),
        "target_count": aggregate.get("targets") == 10,
        "all_source_pool_executions_authorized": (
            aggregate.get("authorized_executions") == aggregate.get("source_artifacts_checked")
            and aggregate.get("execution_errors") == 0
        ),
        "semantic_pool_ceiling_zero": (
            aggregate.get("targets_with_any_semantic_match") == 0
            and aggregate.get("semantic_match_artifacts") == 0
        ),
        "oracle_structured_ceiling_zero": (
            aggregate.get("oracle_structured_top1_semantic") == 0
            and aggregate.get("oracle_structured_top3_semantic") == 0
        ),
        "claim_boundary_present": fresh.get("claim_boundary", {}).get("retriever_quality_measured") is False,
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
    )
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
