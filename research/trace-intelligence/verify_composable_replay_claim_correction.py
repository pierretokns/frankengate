#!/usr/bin/env python3
"""Independently verify an append-only composable replay claim correction."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from composable_replay_claim_correction import SCHEMA_VERSION, build_correction, digest, file_digest, load


def verify(receipt_path: Path, paths: dict[str, Path]) -> dict[str, object]:
    receipt = load(receipt_path)
    if receipt.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected schema version")
    observed = receipt.get("result_sha256")
    unsigned = dict(receipt)
    unsigned.pop("result_sha256", None)
    if observed != digest(unsigned):
        raise ValueError("result hash mismatch")
    expected = build_correction(**{name: load(path) for name, path in paths.items()})
    expected["source_receipts"] = {name: {"sha256": file_digest(path), "raw_content_committed": False} for name, path in paths.items()}
    expected["result_sha256"] = digest({k: v for k, v in expected.items() if k != "result_sha256"})
    if expected != receipt:
        raise ValueError("correction does not match source receipts")
    checks = receipt["checks"]
    if not all(checks.values()):
        raise ValueError("correction contains a failed check")
    boundary = receipt["corrected_claim_boundary"]
    if boundary["changed_system_replay_verified"] is not False or boundary["promotion_authorized"] is not False:
        raise ValueError("correction overstates promotion or changed-system evidence")
    if receipt["historical_receipts_unchanged"] is not True:
        raise ValueError("correction is not append-only")
    return {
        "schema_version": "frankengate-composable-replay-claim-correction-verification-v1",
        "receipt_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
        "source_target_disjointness_verified": boundary["source_target_disjointness_verified"],
        "historical_receipts_unchanged": receipt["historical_receipts_unchanged"],
        "verification_passed": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    for name in ("aggregate", "seed_a", "seed_b", "candidate", "cohort_manifest"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    paths = {name: getattr(args, name).resolve() for name in ("aggregate", "seed_a", "seed_b", "candidate", "cohort_manifest")}
    result = verify(args.receipt.resolve(), paths)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
