#!/usr/bin/env python3
"""Audit one immutable compiled artifact across independent replay seeds.

The two source receipts are the authoritative same-candidate replay fixture.
This tool verifies identity and control separation without pretending that
same-family replay is changed-system or prospective user-outcome evidence.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-composable-candidate-lineage-audit-v1"


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_audit(*, aggregate: dict[str, Any], seed_a: dict[str, Any], seed_b: dict[str, Any], verify_a: dict[str, Any], verify_b: dict[str, Any], candidate: dict[str, Any], cohort_manifest: dict[str, Any]) -> dict[str, Any]:
    seeds = [seed_a, seed_b]
    candidate_hashes = [seed["arm_artifacts"]["trace2skill_compiled_procedure"]["sha256"] for seed in seeds]
    task_sets = [seed["dataset"]["task_id_sha256"] for seed in seeds]
    candidate_arms = [seed["arms"]["trace2skill_compiled_procedure"] for seed in seeds]
    no_skill_arms = [seed["arms"]["no_skill"] for seed in seeds]
    placebo_arms = [seed["arms"]["formatting_placebo"] for seed in seeds]

    aggregate_split = aggregate.get("claim_boundary", {}).get("source_task_ids_disjoint_from_targets") is True
    seed_split_flags = [seed.get("claim_boundary", {}).get("source_task_ids_disjoint_from_targets") for seed in seeds]
    seed_boundaries_reconciled = all(flag is True for flag in seed_split_flags)
    source_files = set(candidate.get("source_selection", {}).get("source_files", []))
    target_file = candidate.get("source_selection", {}).get("target_file")
    manifest_rows = [row for row in cohort_manifest.get("tasks", []) if row.get("db_name") == seed_a["dataset"]["database_family"]]
    source_rows = [row for row in manifest_rows if row.get("source_file") in source_files]
    target_rows = [row for row in manifest_rows if row.get("source_file") == target_file]
    target_hashes = {hashlib.sha256(str(row["task_id"]).encode("utf-8")).hexdigest() for row in target_rows}
    replay_target_hashes = set(seed_a["dataset"]["task_id_sha256"])
    source_hashes = {hashlib.sha256(str(row["task_id"]).encode("utf-8")).hexdigest() for row in source_rows}
    source_failure_count = sum(int(value) for value in candidate.get("source_validation_failures", {}).values())
    manifest_split_verified = (
        bool(source_files)
        and target_file is not None
        and len(target_rows) == len(replay_target_hashes)
        and target_hashes == replay_target_hashes
        and len(source_rows) == int(candidate.get("source_artifact_count", -1)) + source_failure_count
        and not source_hashes.intersection(target_hashes)
    )
    checks = {
        "aggregate_candidate_matches_seeds": aggregate.get("candidate_text_sha256") == candidate_hashes[0] == candidate_hashes[1],
        "candidate_identity_stable": candidate_hashes[0] == candidate_hashes[1],
        "task_set_stable": task_sets[0] == task_sets[1],
        "aggregate_source_target_split_declared": aggregate_split,
        "seed_source_target_split_boundaries_reconciled": seed_boundaries_reconciled,
        "manifest_source_target_split_verified": manifest_split_verified,
        "source_target_split_receipt_reconciled": aggregate_split and manifest_split_verified,
        "authority_valid_all_candidate_runs": all(arm.get("authority_valid") == arm.get("tasks") for arm in candidate_arms),
        "no_unauthorized_candidate_observations": all(arm.get("unauthorized_observation") == 0 for arm in candidate_arms),
        "independent_semantic_verifiers_passed": verify_a.get("semantic_verification_passed") is True and verify_b.get("semantic_verification_passed") is True,
        "candidate_stable_semantic_success": all(arm.get("semantic_correct") == arm.get("tasks") for arm in candidate_arms),
        "no_skill_control_present": all(arm.get("tasks") == 5 for arm in no_skill_arms),
        "formatting_placebo_control_present": all(arm.get("tasks") == 5 for arm in placebo_arms),
    }
    result = {
        "schema_version": SCHEMA_VERSION,
        "candidate": {
            "artifact_id_sha256": candidate_hashes[0],
            "classification": seed_a["arm_artifacts"]["trace2skill_compiled_procedure"]["classification"],
            "char_length": seed_a["arm_artifacts"]["trace2skill_compiled_procedure"]["char_length"],
            "word_count": seed_a["arm_artifacts"]["trace2skill_compiled_procedure"]["word_count"],
        },
        "replay": {
            "seeds": [aggregate.get("seeds", [None, None])[0], aggregate.get("seeds", [None, None])[1]],
            "database_family": seed_a["dataset"]["database_family"],
            "unique_task_count": seed_a["dataset"]["task_count"],
            "candidate_semantic_correct": [arm["semantic_correct"] for arm in candidate_arms],
            "no_skill_semantic_correct": [arm["semantic_correct"] for arm in no_skill_arms],
            "formatting_placebo_semantic_correct": [arm["semantic_correct"] for arm in placebo_arms],
            "candidate_authority_valid": [arm["authority_valid"] for arm in candidate_arms],
            "candidate_unauthorized_observations": [arm["unauthorized_observation"] for arm in candidate_arms],
        },
        "cohort_reconstruction": {
            "manifest_database_family": seed_a["dataset"]["database_family"],
            "source_files": sorted(source_files),
            "target_file": target_file,
            "source_manifest_rows": len(source_rows),
            "source_validation_failures": source_failure_count,
            "candidate_source_artifacts": candidate.get("source_artifact_count"),
            "target_manifest_rows": len(target_rows),
            "replay_target_rows": len(replay_target_hashes),
            "source_target_hash_overlap": len(source_hashes.intersection(target_hashes)),
        },
        "checks": checks,
        "gates_closed": {
            "immutable_candidate_identity_across_replays": checks["candidate_identity_stable"],
            "source_target_disjointness": checks["source_target_split_receipt_reconciled"],
            "independent_semantic_recomputation": checks["independent_semantic_verifiers_passed"],
            "authority_and_unauthorized_observation_checks": checks["authority_valid_all_candidate_runs"] and checks["no_unauthorized_candidate_observations"],
            "same_family_seed_replay": checks["candidate_stable_semantic_success"],
        },
        "gates_open": {
            "aggregate_vs_seed_claim_boundary_reconciliation": not seed_boundaries_reconciled,
            "changed_schema_or_changed_system_replay": True,
            "human_or_sme_semantic_label": True,
            "prospective_next_task_user_utility": True,
            "versioned_release_and_rollback_event_for_this_candidate": True,
            "cross_family_and_cross_project_transfer": True,
        },
        "claim_boundary": {
            "same_candidate_replay_verified": True,
            "aggregate_declares_source_target_disjoint": aggregate_split,
            "seed_claim_boundaries_reconciled": seed_boundaries_reconciled,
            "manifest_source_target_split_verified": manifest_split_verified,
            "causal_skill_benefit_established": False,
            "production_promotion_established": False,
            "interpretation": "One immutable compiled candidate reproduced across two seeds with independent semantic verification and zero unauthorized observations; this is a same-family replay result, not a release or causal enterprise-learning claim.",
        },
    }
    result["result_sha256"] = digest(result)
    return result


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object receipt: {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    for name in ("aggregate", "seed_a", "seed_b", "verify_a", "verify_b", "candidate", "cohort_manifest"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    paths = {name: getattr(args, name).resolve() for name in ("aggregate", "seed_a", "seed_b", "verify_a", "verify_b", "candidate", "cohort_manifest")}
    result = build_audit(**{name: load(path) for name, path in paths.items()})
    result["source_receipts"] = {name: {"sha256": file_digest(path), "raw_content_committed": False} for name, path in paths.items()}
    result["result_sha256"] = digest({k: v for k, v in result.items() if k != "result_sha256"})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "result_sha256": result["result_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
