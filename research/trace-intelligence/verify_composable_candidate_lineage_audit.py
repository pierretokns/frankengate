#!/usr/bin/env python3
"""Independently verify the same-candidate composable replay lineage receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from composable_candidate_lineage_audit import SCHEMA_VERSION, build_audit, digest, file_digest, load


def verify(receipt_path: Path, paths: dict[str, Path]) -> dict[str, object]:
    receipt = load(receipt_path)
    if receipt.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected schema version")
    observed = receipt.get("result_sha256")
    unsigned = dict(receipt)
    unsigned.pop("result_sha256", None)
    if observed != digest(unsigned):
        raise ValueError("result hash mismatch")
    expected = build_audit(**{name: load(path) for name, path in paths.items()})
    expected["source_receipts"] = {name: {"sha256": file_digest(path), "raw_content_committed": False} for name, path in paths.items()}
    expected["result_sha256"] = digest({k: v for k, v in expected.items() if k != "result_sha256"})
    if expected != receipt:
        raise ValueError("receipt does not match source receipts")
    checks = receipt["checks"]
    for key in ("candidate_identity_stable", "independent_semantic_verifiers_passed", "authority_valid_all_candidate_runs", "no_unauthorized_candidate_observations", "candidate_stable_semantic_success"):
        if checks.get(key) is not True:
            raise ValueError(f"required lineage check failed: {key}")
    if checks.get("manifest_source_target_split_verified") is not True:
        raise ValueError("manifest source/target reconstruction failed")
    if receipt["claim_boundary"]["production_promotion_established"] is not False:
        raise ValueError("promotion boundary overstates evidence")
    return {
        "schema_version": "frankengate-composable-candidate-lineage-verification-v1",
        "receipt_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
        "artifact_id_sha256": receipt["candidate"]["artifact_id_sha256"],
        "seeds": receipt["replay"]["seeds"],
        "source_target_reconciliation_required": receipt["gates_open"]["aggregate_vs_seed_claim_boundary_reconciliation"],
        "verification_passed": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    for name in ("aggregate", "seed_a", "seed_b", "verify_a", "verify_b", "candidate", "cohort_manifest"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    paths = {name: getattr(args, name).resolve() for name in ("aggregate", "seed_a", "seed_b", "verify_a", "verify_b", "candidate", "cohort_manifest")}
    result = verify(args.receipt.resolve(), paths)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
