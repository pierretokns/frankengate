#!/usr/bin/env python3
"""Verify the content-free Wisp frontier/local agreement receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from wisp_frontier_local_adjudication import FIELDS, stable_hash


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(packet_path: Path, local_raw_path: Path, result_path: Path, raw_dir: Path) -> dict[str, Any]:
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if result.get("schema_version") != "frankengate-wisp-frontier-local-adjudication-v1":
        raise ValueError("unexpected schema version")
    if result["source"]["packet_sha256"] != file_sha256(packet_path) or result["source"]["local_raw_sha256"] != file_sha256(local_raw_path):
        raise ValueError("source hash mismatch")
    raw_path = raw_dir / "frontier.json"
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    if result["frontier_output"]["raw_sha256"] != file_sha256(raw_path):
        raise ValueError("frontier raw hash mismatch")
    structured = raw.get("structured_output")
    if not isinstance(structured, dict) or not isinstance(structured.get("decisions"), list):
        raise ValueError("missing structured frontier output")
    expected_ids = {candidate["blind_id"] for candidate in packet["candidates"]}
    receipt_ids = {candidate["blind_id"] for candidate in result["candidates"]}
    observed_ids = {item.get("blind_id") for item in structured["decisions"]}
    if not receipt_ids <= expected_ids or observed_ids != receipt_ids:
        raise ValueError("candidate coverage mismatch")
    for item in structured["decisions"]:
        if set(item.get("labels", {})) != set(FIELDS):
            raise ValueError(f"label fields missing: {item.get('blind_id')}")
    unsigned = dict(result)
    expected_hash = unsigned.pop("result_sha256")
    if stable_hash(unsigned) != expected_hash:
        raise ValueError("result hash mismatch")
    return {"status": "verified", "candidates": len(receipt_ids), "result_sha256": expected_hash, "raw_sha256": file_sha256(raw_path)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--local-raw", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.packet, args.local_raw, args.result, args.raw_dir), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
