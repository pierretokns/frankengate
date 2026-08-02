#!/usr/bin/env python3
"""Independently verify the artifact lifecycle audit receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from artifact_lifecycle_audit import SCHEMA_VERSION, build_audit, digest, file_digest, load


def verify(receipt_path: Path, source_paths: dict[str, Path]) -> dict[str, object]:
    receipt = load(receipt_path)
    if receipt.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected schema version")
    unsigned = dict(receipt)
    observed_hash = unsigned.pop("result_sha256", None)
    if observed_hash != digest(unsigned):
        raise ValueError("result hash mismatch")
    expected = build_audit(**{name: load(path) for name, path in source_paths.items()})
    expected["source_receipts"] = {
        name: {"sha256": file_digest(path), "raw_content_committed": False}
        for name, path in source_paths.items()
    }
    expected["result_sha256"] = digest({k: v for k, v in expected.items() if k != "result_sha256"})
    if expected != receipt:
        raise ValueError("receipt does not match source receipts")
    if receipt["frontier_lifecycle"]["promotion_ready_count"] != 0:
        raise ValueError("frontier candidates incorrectly marked promotion-ready")
    if not receipt["claim_boundary"]["replay_receipts_share_candidate_ids_with_frontier"]:
        # This should remain false: the source cohorts are intentionally not
        # joined by fabricated IDs.
        pass
    return {
        "schema_version": "frankengate-artifact-lifecycle-audit-verification-v1",
        "receipt_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
        "candidate_count": receipt["frontier_lifecycle"]["candidate_count"],
        "promotion_ready_count": receipt["frontier_lifecycle"]["promotion_ready_count"],
        "verification_passed": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    for name in ("frontier", "replay", "stress", "promotion", "drift", "memory"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    source_paths = {name: getattr(args, name).resolve() for name in ("frontier", "replay", "stress", "promotion", "drift", "memory")}
    result = verify(args.receipt.resolve(), source_paths)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
