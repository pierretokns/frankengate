#!/usr/bin/env python3
"""Merge one-seed, one-arm receipts without losing isolation provenance."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def merge(paths: list[Path], output: Path) -> None:
    if not paths:
        raise ValueError("at least one arm receipt is required")
    receipts = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    first = receipts[0]
    task_hashes = tuple(first["dataset"]["task_id_sha256"])
    seed = int(first["protocol_remediation"]["seed_base"])
    arms: dict[str, object] = {}
    artifacts: dict[str, object] = {}
    task_runs: list[dict[str, object]] = []
    sources: list[str] = []
    isolation = []
    for path, receipt in zip(paths, receipts):
        if tuple(receipt["dataset"]["task_id_sha256"]) != task_hashes:
            raise ValueError(f"task set differs in {path}")
        if int(receipt["protocol_remediation"]["seed_base"]) != seed:
            raise ValueError(f"seed differs in {path}")
        names = set(receipt.get("arms", {}))
        if len(names) != 1:
            raise ValueError(f"expected one arm in {path}, got {names}")
        arm = next(iter(names))
        if arm in arms:
            raise ValueError(f"duplicate arm {arm}")
        arms[arm] = receipt["arms"][arm]
        artifacts[arm] = receipt.get("arm_artifacts", {}).get(arm)
        task_runs.extend(receipt.get("task_runs", []))
        sources.append(hashlib.sha256(path.read_bytes()).hexdigest())
        isolation.append(receipt.get("isolation", "one-disposable-postgres-container-per-arm"))
    merged = dict(first)
    merged["arms"] = arms
    merged["arm_artifacts"] = artifacts
    merged["task_runs"] = task_runs
    merged["source_arm_receipt_sha256"] = sources
    merged["isolation"] = isolation
    merged["claim_boundary"] = (
        "Each arm was run with a fresh database container, governed role, port, "
        "audit root, and verifier; merged here only for paired analysis. This "
        "does not establish universal skill utility or promotion eligibility."
    )
    output.write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    merge(args.result, args.output)
    print(json.dumps({"status": "ok", "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
