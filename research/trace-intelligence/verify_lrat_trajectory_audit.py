#!/usr/bin/env python3
"""Verify the content-minimized LRAT trajectory audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-lrat-trajectory-audit-v1"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(result_path: Path, raw_root: Path) -> dict[str, Any]:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unexpected LRAT audit schema")
    dataset = result.get("dataset", {})
    count = int(dataset.get("trajectory_files", 0))
    receipts = result.get("raw_receipts", [])
    if len(receipts) != count:
        raise ValueError("receipt count does not match trajectory count")
    for receipt in receipts:
        path = raw_root / str(receipt["relative_path"])
        if not path.exists() or sha256(path) != receipt.get("sha256"):
            raise ValueError(f"raw hash mismatch: {receipt.get('relative_path')}")
    records = result.get("records", {})
    if int(records.get("tool_calls", 0)) != int(records.get("nonempty_tool_outputs", 0)):
        raise ValueError("not every tool call has a non-empty output")
    if result.get("claim_boundary", {}).get("enterprise_alias_or_artifact_learning_measured") is not False:
        raise ValueError("enterprise learning claim boundary changed")
    return {
        "schema_version": "lrat-trajectory-audit-verification-v1",
        "source_result_sha256": sha256(result_path),
        "trajectory_files_verified": count,
        "raw_hashes_match": True,
        "verification_passed": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verification = verify(args.result, args.raw_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(verification, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(verification, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
