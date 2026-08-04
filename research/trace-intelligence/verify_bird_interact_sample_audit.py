#!/usr/bin/env python3
"""Verify the content-free BIRD-Interact sample audit receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-bird-interact-sample-audit-v1"


def stable_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def verify(path: Path) -> dict[str, Any]:
    receipt = json.loads(path.read_text(encoding="utf-8"))
    if receipt.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected sample audit schema")
    modes = receipt.get("aggregate", {}).get("modes", {})
    if set(modes) != {"a-interact", "c-interact"}:
        raise ValueError("mode coverage mismatch")
    if receipt.get("aggregate", {}).get("samples") != 20:
        raise ValueError("sample count mismatch")
    for mode, values in modes.items():
        if values.get("samples") != 10:
            raise ValueError(f"sample count mismatch for {mode}")
        for key in ("phase1_rate", "phase2_rate", "reward_mean"):
            if not 0.0 <= float(values.get(key, -1.0)) <= 1.0:
                raise ValueError(f"invalid metric for {mode}: {key}")
    unsigned = dict(receipt)
    observed = unsigned.pop("result_sha256", None)
    expected = hashlib.sha256(stable_json(unsigned)).hexdigest()
    if observed != expected:
        raise ValueError("sample audit hash mismatch")
    return {"status": "verified", "samples": 20, "result_sha256": observed}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.receipt.resolve()), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
