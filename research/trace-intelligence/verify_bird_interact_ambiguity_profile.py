#!/usr/bin/env python3
"""Verify the content-free BIRD-Interact ambiguity profile receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-bird-interact-ambiguity-profile-v1"


def stable_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def verify(receipt_path: Path) -> dict[str, Any]:
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if receipt.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected profile schema")
    source = receipt.get("source", {})
    aggregate = receipt.get("aggregate", {})
    records = int(source.get("records", 0))
    if records != 600:
        raise ValueError(f"unexpected record count: {records}")
    if int(aggregate.get("records_with_follow_up", 0)) != records:
        raise ValueError("follow-up coverage mismatch")
    if int(aggregate.get("records_with_critical_ambiguity", 0)) <= 0:
        raise ValueError("critical ambiguity cohort is empty")
    if sum(aggregate.get("follow_up_types", {}).values()) != records:
        raise ValueError("follow-up type partition mismatch")
    if receipt.get("claim_boundary", {}).get("friction_or_agent_quality_measured") is not False:
        raise ValueError("claim boundary widened unexpectedly")
    unsigned = dict(receipt)
    observed = unsigned.pop("result_sha256", None)
    expected = hashlib.sha256(stable_json(unsigned)).hexdigest()
    if observed != expected:
        raise ValueError("profile receipt hash mismatch")
    return {"status": "verified", "records": records, "result_sha256": observed}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.receipt.resolve()), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
