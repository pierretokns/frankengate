#!/usr/bin/env python3
"""Compare content-free aggregates across independently implemented harnesses."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not value.get("semantic_verification_passed"):
        raise ValueError(f"semantic verification failed: {path}")
    return value


def compare(inputs: list[tuple[str, Path, Path]], output: Path) -> dict[str, Any]:
    if len(inputs) < 2:
        raise ValueError("at least two harness receipt pairs are required")
    rows = []
    task_hashes: set[str] | None = None
    arms: set[str] | None = None
    for label, result_path, verification_path in inputs:
        result = json.loads(result_path.read_text(encoding="utf-8"))
        verification = _load(verification_path)
        current_tasks = set(result["dataset"]["task_id_sha256"])
        current_arms = set(result["arms"])
        if task_hashes is None:
            task_hashes, arms = current_tasks, current_arms
        elif current_tasks != task_hashes or current_arms != arms:
            raise ValueError("harness receipts do not share task or arm sets")
        rows.append({
            "label": label,
            "harness": result.get("model", {}).get("harness"),
            "endpoint_scope": result.get("model", {}).get("endpoint_scope"),
            "seed_base": result.get("protocol_remediation", {}).get("seed_base"),
            "task_mutation": result.get("protocol_remediation", {}).get("task_mutation"),
            "source_result_sha256": hashlib.sha256(result_path.read_bytes()).hexdigest(),
            "source_verification_sha256": hashlib.sha256(verification_path.read_bytes()).hexdigest(),
            "arms": result["arms"],
        })
    value = {
        "schema_version": "frankengate-frontier-transfer-harness-comparison-v1",
        "task_count": len(task_hashes or ()),
        "arms": sorted(arms or ()),
        "harnesses": rows,
        "claim_boundary": "Descriptive same-task/arm harness comparison with independent semantic verification. Different seeds and sample size prevent a causal harness ranking or universal skill claim.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", action="append", nargs=3, metavar=("LABEL", "RESULT", "VERIFICATION"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = compare([(label, Path(result), Path(verification)) for label, result, verification in args.input], args.output)
    print(json.dumps({"status": "ok", "harnesses": [row["label"] for row in value["harnesses"]]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
