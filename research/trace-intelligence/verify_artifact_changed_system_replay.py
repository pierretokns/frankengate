#!/usr/bin/env python3
"""Independently verify the content-minimized changed-system artifact receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-artifact-changed-system-replay-v1"


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def verify(path: Path) -> dict[str, Any]:
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if receipt.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected schema version")
    observed_hash = receipt.get("result_sha256")
    unsigned = dict(receipt)
    unsigned.pop("result_sha256", None)
    if observed_hash != digest(unsigned):
        raise ValueError("result hash mismatch")
    cases = receipt.get("cases", [])
    if [case.get("case_id") for case in cases] != [
        "unchanged",
        "additive_column",
        "approved_semantic_rename",
        "semantic_collision",
        "same_name_semantic_drift",
    ]:
        raise ValueError("unexpected case order")
    expected = {
        "unchanged": {"strict": (True, True), "name_compatibility": (True, True), "semantic_compatibility": (True, True)},
        "additive_column": {"strict": (False, False), "name_compatibility": (True, True), "semantic_compatibility": (True, True)},
        "approved_semantic_rename": {"strict": (False, False), "name_compatibility": (True, True), "semantic_compatibility": (True, True)},
        "semantic_collision": {"strict": (False, False), "name_compatibility": (True, False), "semantic_compatibility": (False, False)},
        "same_name_semantic_drift": {"strict": (False, False), "name_compatibility": (True, False), "semantic_compatibility": (False, False)},
    }
    for case in cases:
        case_id = case["case_id"]
        for policy, (accepted, semantic_match) in expected[case_id].items():
            observed = case["policies"].get(policy)
            if observed is None or bool(observed.get("accepted")) != accepted:
                raise ValueError(f"acceptance mismatch: {case_id}/{policy}")
            if accepted and bool(observed.get("semantic_match")) != semantic_match:
                raise ValueError(f"semantic outcome mismatch: {case_id}/{policy}")
    aggregate = receipt.get("aggregate", {})
    if aggregate != {
        "cases": 5,
        "name_compatibility_accepts": 5,
        "name_compatibility_false_semantic_accepts": 2,
        "semantic_compatibility_accepts": 3,
        "semantic_compatibility_false_semantic_accepts": 0,
        "strict_accepts": 1,
    }:
        raise ValueError("aggregate mismatch")
    tool = receipt.get("tool_contract_drift")
    if not tool or tool.get("semantic_match") is not True:
        raise ValueError("tool contract semantic mapping missing")
    return {
        "schema_version": "frankengate-artifact-changed-system-replay-verification-v1",
        "receipt_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "cases_verified": len(cases),
        "semantic_compatibility_false_accepts": aggregate["semantic_compatibility_false_semantic_accepts"],
        "verification_passed": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.receipt)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
