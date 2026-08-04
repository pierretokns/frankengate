#!/usr/bin/env python3
"""Independent verifier for the controlled shared-intent retrieval receipt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from validated_artifact_shared_intent_benchmark import run


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
    stored = json.loads(args.expected.read_text(encoding="utf-8"))
    fresh = run(
        source_root=args.source_root.resolve(strict=True),
        cohort_manifest=args.cohort_manifest.resolve(strict=True),
        dataset_manifest=args.dataset_manifest.resolve(strict=True),
        dsn_template=args.dsn_template,
        databases=tuple(args.database),
        output=args.recomputed,
        endpoint=args.endpoint,
    )
    aggregate = fresh["aggregate"]
    checks = {
        "result_hash_matches": stored.get("result_sha256") == fresh.get("result_sha256"),
        "known_shared_intent_declared": fresh["target"].get("known_shared_intent") is True,
        "target_count": fresh["target"].get("target_count") == 20,
        "all_dense_top1_recovered": aggregate["dense"].get("known_source_top1") == 20,
        "all_hybrid_top1_recovered": aggregate["hybrid"].get("known_source_top1") == 20,
        "all_lexical_top1_recovered": aggregate["lexical"].get("known_source_top1") == 20,
        "scoped_execution_authorized": all(
            aggregate[arm].get("top3_authorized") == 60 and aggregate[arm].get("top3_errors") == 0
            for arm in aggregate
        ),
        "claim_boundary_present": fresh["claim_boundary"].get("causal_agent_benefit_established") is False,
    }
    result = {
        "schema_version": "frankengate-validated-artifact-shared-intent-verification-v1",
        "stored_result_sha256": stored.get("result_sha256"),
        "recomputed_result_sha256": fresh.get("result_sha256"),
        "checks": checks,
        "status": "verified" if all(checks.values()) else "failed",
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "verified" else 1


if __name__ == "__main__":
    raise SystemExit(main())
