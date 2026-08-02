#!/usr/bin/env python3
"""Verify the aggregate WMH-BIRD step-fault audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-wmh-bird-step-fault-audit-v1"


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(result_path: Path) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected step-fault schema")
    aggregate = result.get("aggregate", {})
    for key in ("traces", "reward_0", "reward_1", "sql_traces", "sql_steps"):
        if not isinstance(aggregate.get(key), int) or aggregate[key] < 0:
            raise ValueError("invalid aggregate count")
    if aggregate["reward_0"] + aggregate["reward_1"] != aggregate["traces"]:
        raise ValueError("reward counts do not reconcile")
    if len(result.get("rows", [])) != aggregate["traces"]:
        raise ValueError("row count does not reconcile")
    claim = result.get("claim_boundary", {})
    if claim.get("gold_diff_step_proxy_measured") is not True:
        raise ValueError("gold-diff proxy missing")
    for key in ("causal_fault_attribution_established", "skill_revision_utility_measured", "enterprise_transfer_established"):
        if claim.get(key) is not False:
            raise ValueError("claim boundary overstates evidence")
    return {"schema_version": "frankengate-wmh-bird-step-fault-verification-v1", "source_result_sha256": file_hash(result_path), "traces_verified": aggregate["traces"], "sql_steps_verified": aggregate["sql_steps"], "claim_boundary_verified": True, "verification_passed": True}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = verify(args.result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(value, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
