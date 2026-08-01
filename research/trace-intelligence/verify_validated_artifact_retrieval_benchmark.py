#!/usr/bin/env python3
"""Independent content-free verifier for the train-only artifact benchmark."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from validated_artifact_retrieval_benchmark import run


SCHEMA_VERSION = "frankengate-validated-artifact-retrieval-verification-v1"


def verify(*, expected: Path, recomputed: Path, **kwargs: object) -> dict[str, object]:
    stored = json.loads(expected.read_text(encoding="utf-8"))
    fresh = run(output=recomputed, **kwargs)
    stored_hash = stored.get("result_sha256")
    fresh_hash = fresh.get("result_sha256")
    aggregate = fresh.get("aggregate") or {}
    checks = {
        "result_hash_matches": stored_hash == fresh_hash,
        "target_count": aggregate.get("targets") == 10,
        "semantic_matches": aggregate.get("semantic_correct") == 0,
        "all_candidates_authorized": aggregate.get("security_authorized") == 10,
        "source_artifacts_validated_before_pool": bool(
            (fresh.get("source", {}).get("validated_artifact_counts") or {})
        ),
    }
    result = {
        "schema_version": SCHEMA_VERSION,
        "stored_result_sha256": stored_hash,
        "recomputed_result_sha256": fresh_hash,
        "checks": checks,
        "status": "verified" if all(checks.values()) else "failed",
    }
    return result


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
