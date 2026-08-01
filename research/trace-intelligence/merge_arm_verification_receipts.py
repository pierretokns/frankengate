#!/usr/bin/env python3
"""Combine independent verifier receipts for one seed's isolated arms."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verification", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipts = [json.loads(path.read_text(encoding="utf-8")) for path in args.verification]
    if not all(receipt.get("semantic_verification_passed") for receipt in receipts):
        raise SystemExit("all arm verification receipts must pass")
    payload = {
        "schema_version": "frankengate-defog-semantic-independent-verification-arm-aggregate-v1",
        "semantic_verification_passed": True,
        "semantic_recomputation": "all isolated arm receipts independently recomputed against pinned governed Postgres",
        "arm_verifications": [
            {
                "path": str(path),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "receipt": receipt,
            }
            for path, receipt in zip(args.verification, receipts)
        ],
        "claim_boundary": "All listed arm receipts passed independent semantic recomputation; this aggregate does not establish universal skill utility or promotion eligibility.",
    }
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "arms": len(receipts), "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
