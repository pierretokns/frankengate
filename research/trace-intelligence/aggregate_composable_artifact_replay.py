#!/usr/bin/env python3
"""Aggregate two seeded composable-artifact frontier replays safely."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


ARMS = ("no_skill", "formatting_placebo", "trace2skill_compiled_procedure")


def stable_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def run(*, result_paths: tuple[Path, ...], verification_paths: tuple[Path, ...], output: Path) -> dict[str, Any]:
    if len(result_paths) != 2 or len(verification_paths) != 2:
        raise ValueError("exactly two seeded results and two verifications are required")
    results = [json.loads(path.read_text(encoding="utf-8")) for path in result_paths]
    verifications = [json.loads(path.read_text(encoding="utf-8")) for path in verification_paths]
    checks = {
        "two_seeds": len(results) == 2,
        "semantic_verifiers_passed": all(item.get("semantic_verification_passed") is True for item in verifications),
        "same_task_set": results[0].get("dataset", {}).get("task_id_sha256") == results[1].get("dataset", {}).get("task_id_sha256"),
        "same_candidate_text": (
            results[0].get("protocol_remediation", {}).get("trace_mined_candidate", {}).get("candidate_text_sha256")
            == results[1].get("protocol_remediation", {}).get("trace_mined_candidate", {}).get("candidate_text_sha256")
        ),
        "same_arm_set": set(results[0].get("arms", {})) == set(results[1].get("arms", {})) == set(ARMS),
        "no_unauthorized_observations": all(
            all(int(result.get("unauthorized_observation", 0)) == 0 for result in run.get("task_runs", []))
            for run in results
        ),
    }
    if not all(checks.values()):
        raise ValueError(f"replay compatibility checks failed: {checks}")

    arm_aggregate: dict[str, dict[str, int]] = {}
    for arm in ARMS:
        runs = [run for result in results for run in result.get("task_runs", []) if run.get("arm") == arm]
        arm_aggregate[arm] = {
            "episode_runs": len(runs),
            "semantic_correct": sum(bool(run.get("semantic_correct")) for run in runs),
            "authority_valid": sum(bool(run.get("authority_valid")) for run in runs),
            "policy_accepted": sum(run.get("policy_accepted") is True for run in runs),
            "unauthorized_observations": sum(int(run.get("unauthorized_observation", 0)) for run in runs),
            "sql_attempts": sum(int(run.get("sql_attempts", 0)) for run in runs),
            "tool_calls": sum(int(run.get("tool_calls", 0)) for run in runs),
            "terminal_protocol_failures": sum(run.get("terminal_action") == "none" for run in runs),
        }

    by_seed_task: dict[tuple[str, str], list[bool]] = {}
    for result in results:
        for run in result.get("task_runs", []):
            by_seed_task[(str(run["task_id_sha256"]), str(run["arm"]))] = [bool(run.get("semantic_correct"))]
    task_hashes = sorted({task_hash for task_hash, _ in by_seed_task})
    stable_comparison: dict[str, dict[str, int]] = {}
    candidate = "trace2skill_compiled_procedure"
    for control in ("no_skill", "formatting_placebo"):
        wins = losses = ties = 0
        for task_hash in task_hashes:
            candidate_values = [
                bool(run.get("semantic_correct"))
                for result in results
                for run in result.get("task_runs", [])
                if run.get("task_id_sha256") == task_hash and run.get("arm") == candidate
            ]
            control_values = [
                bool(run.get("semantic_correct"))
                for result in results
                for run in result.get("task_runs", [])
                if run.get("task_id_sha256") == task_hash and run.get("arm") == control
            ]
            # A stable win/loss requires the same direction on both seeds.
            candidate_all = bool(candidate_values) and all(candidate_values)
            control_all = bool(control_values) and all(control_values)
            if candidate_all and not control_all:
                wins += 1
            elif control_all and not candidate_all:
                losses += 1
            else:
                ties += 1
        stable_comparison[control] = {
            "unique_tasks": len(task_hashes),
            "stable_candidate_wins": wins,
            "stable_candidate_losses": losses,
            "stable_ties_or_mixed": ties,
        }

    receipt = {
        "schema_version": "frankengate-composable-artifact-replay-aggregate-v1",
        "seed_result_sha256": [hashlib.sha256(path.read_bytes()).hexdigest() for path in result_paths],
        "seed_verification_sha256": [hashlib.sha256(path.read_bytes()).hexdigest() for path in verification_paths],
        "seeds": [result.get("protocol_remediation", {}).get("seed_base") for result in results],
        "candidate_text_sha256": results[0]["protocol_remediation"]["trace_mined_candidate"]["candidate_text_sha256"],
        "dataset": {
            "unique_task_count": len(task_hashes),
            "task_set_sha256": hashlib.sha256(stable_json(task_hashes)).hexdigest(),
            "database_family": results[0].get("dataset", {}).get("database_family"),
        },
        "arms": arm_aggregate,
        "stable_task_comparisons": stable_comparison,
        "checks": checks,
        "claim_boundary": {
            "independent_semantic_verification": True,
            "causal_enterprise_skill_benefit_established": False,
            "repeated_seeds_are_not_independent_tasks": True,
            "same_database_family": True,
            "source_task_ids_disjoint_from_targets": True,
            "reason": "Two seeded frontier replays on five source-disjoint broker tasks; promising composability signal, not a powered or cross-family causal estimate.",
        },
    }
    receipt["result_sha256"] = sha256_bytes(stable_json(receipt))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"aggregate": receipt["arms"], "stable_task_comparisons": stable_comparison, "result_sha256": receipt["result_sha256"]}, sort_keys=True))
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", action="append", type=Path, required=True)
    parser.add_argument("--verification", action="append", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(result_paths=tuple(path.resolve(strict=True) for path in args.result), verification_paths=tuple(path.resolve(strict=True) for path in args.verification), output=args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
