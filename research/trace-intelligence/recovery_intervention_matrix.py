#!/usr/bin/env python3
"""Freeze a paired Recovery-Bench intervention matrix before model execution.

This preflight intentionally emits only set hashes and counts. It prevents a
later recovery run from silently changing the failed-task cohort or comparing
unpaired arms. It does not run Harbor, call a model, or measure recovery.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List


ARMS = (
    "no_context",
    "full_context",
    "summary_context",
    "reviewed_skill",
    "formatting_placebo",
)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _set_hash(values: Iterable[str]) -> str:
    return _sha256_bytes("\n".join(sorted(values)).encode("utf-8"))


def build_matrix(manifest_path: Path) -> Dict[str, Any]:
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    failures = manifest.get("failures") if isinstance(manifest, dict) else None
    if not isinstance(failures, list) or not failures:
        raise ValueError("failure manifest must contain a non-empty failures list")

    task_names: List[str] = []
    task_checksums: List[str] = []
    task_paths: List[str] = []
    missing_fields: List[int] = []
    for index, entry in enumerate(failures):
        if not isinstance(entry, dict):
            missing_fields.append(index)
            continue
        task_name = str(entry.get("task_name", ""))
        checksum = str(entry.get("task_checksum", ""))
        task_path = str(entry.get("task_path", ""))
        trajectory = entry.get("trajectory")
        if not task_name or not checksum or not task_path or not trajectory:
            missing_fields.append(index)
        task_names.append(task_name)
        task_checksums.append(checksum)
        task_paths.append(task_path)

    duplicate_task_names = sorted({name for name in task_names if task_names.count(name) > 1})
    duplicate_checksums = sorted({checksum for checksum in task_checksums if task_checksums.count(checksum) > 1})
    if missing_fields:
        raise ValueError(f"failure manifest rows missing required fields: {missing_fields}")
    if duplicate_task_names or duplicate_checksums:
        raise ValueError(
            f"failure manifest is not unique: names={duplicate_task_names}, checksums={duplicate_checksums}"
        )

    task_set_hash = _set_hash(task_names)
    checksum_set_hash = _set_hash(task_checksums)
    arm_receipts = [
        {
            "arm": arm,
            "paired": True,
            "task_count": len(task_names),
            "task_set_sha256": task_set_hash,
            "task_checksum_set_sha256": checksum_set_hash,
        }
        for arm in ARMS
    ]
    return {
        "schema": "frankengate.recovery_intervention_matrix.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "failure_manifest": str(manifest_path),
            "failure_manifest_sha256": _sha256_bytes(manifest_bytes),
            "raw_trace_content_committed": False,
        },
        "design": {
            "paired": True,
            "arm_count": len(ARMS),
            "arms": list(ARMS),
            "task_count": len(task_names),
            "task_set_sha256": task_set_hash,
            "task_checksum_set_sha256": checksum_set_hash,
            "cross_arm_task_leakage": False,
            "task_disjoint_final_confirmation_required": True,
        },
        "arms": arm_receipts,
        "outcomes_required": [
            "verifier_reward",
            "repair_regression",
            "first_attempt_success",
            "tool_calls",
            "latency_ms",
            "model_cost_usd",
            "false_semantic_acceptance",
        ],
        "claim_boundary": {
            "preflight_only": True,
            "recovery_outcome_measured": False,
            "skill_transfer_confirmed": False,
            "reason": "This freezes a fair paired design; Harbor/model runs and independent verifier outcomes are still required.",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_matrix(args.manifest.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["design"], sort_keys=True))


if __name__ == "__main__":
    main()
