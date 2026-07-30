#!/usr/bin/env python3
"""Freeze leakage-safe schema-family rotations for the Defog SQL factorial.

The output is content-free: it contains task IDs, database roles, policy
adjudications, arm contracts, and hashes, but no question, SQL, instruction, or
database content. Hidden-test families are never used by the pilot stage.
"""

from __future__ import annotations

import argparse
import hashlib
from itertools import permutations
import json
from pathlib import Path
from typing import Any

from defog_sql_factorial_contract import (
    ANALYSIS_PLAN,
    ARM_ARTIFACTS,
    ARM_CONTRACTS,
    BASE_SYSTEM_PROMPT,
    FAILURE_TAXONOMY,
    LIMITS,
    TOOLS,
)


SCHEMA_VERSION = "frankengate-defog-factorial-design-v2"
SEED = 20260730
DATABASES = (
    "broker",
    "car_dealership",
    "derm_treatment",
    "ewallet",
)
POLICY_ADJUDICATIONS = {
    "defog-sql-eval:questions_gen_postgres:car_dealership:205:e8faa9b21e95": (
        "explicit_sensitive_field_entitlement_required"
    ),
    "defog-sql-eval:questions_gen_postgres:ewallet:201:a1e58a7f57dc": (
        "explicit_sensitive_field_entitlement_required"
    ),
    "defog-sql-eval:instruct_advanced_postgres:ewallet:53:fd3d5ce5739c": (
        "source_postgresql_invalid_quarantined"
    ),
}
class DesignError(ValueError):
    """Raised when the cohort cannot support the frozen rotation."""


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _source_stratum(source_file: str) -> str:
    name = Path(source_file).name
    if name == "questions_gen_postgres.csv":
        return "general"
    if name == "instruct_basic_postgres.csv":
        return "basic"
    if name == "instruct_advanced_postgres.csv":
        return "advanced"
    raise DesignError(f"unknown source stratum: {source_file}")


def _rank(task_id: str, fold_id: str) -> str:
    return sha256_text(f"{SEED}\0{fold_id}\0{task_id}")


def _pilot_tasks(
    tasks: list[dict[str, Any]],
    *,
    database: str,
    fold_id: str,
) -> list[str]:
    eligible = [
        task
        for task in tasks
        if task["db_name"] == database
        and task["task_id"] not in POLICY_ADJUDICATIONS
    ]
    by_stratum = {"general": [], "basic": [], "advanced": []}
    for task in eligible:
        by_stratum[_source_stratum(task["source_file"])].append(task["task_id"])
    for task_ids in by_stratum.values():
        task_ids.sort(key=lambda task_id: _rank(task_id, fold_id))
    if not by_stratum["general"] or not by_stratum["basic"]:
        raise DesignError(f"{database}: missing general or basic pilot stratum")
    if len(by_stratum["advanced"]) < 2:
        raise DesignError(f"{database}: fewer than two advanced pilot tasks")
    return sorted(
        [
            by_stratum["general"][0],
            by_stratum["basic"][0],
            by_stratum["advanced"][0],
            by_stratum["advanced"][1],
        ]
    )


def _eligible_task_ids(
    tasks: list[dict[str, Any]],
    databases: set[str],
) -> list[str]:
    return sorted(
        task["task_id"]
        for task in tasks
        if task["db_name"] in databases
        and task["task_id"] not in POLICY_ADJUDICATIONS
    )


def _balanced_arm_order(
    task_ids: list[str],
    *,
    fold_id: str,
    stage: str,
) -> dict[str, list[str]]:
    arm_permutations = sorted(permutations(sorted(ARM_CONTRACTS)))
    ranked = sorted(
        task_ids,
        key=lambda task_id: sha256_text(
            f"{SEED}\0{fold_id}\0{stage}\0{task_id}"
        ),
    )
    return {
        task_id: list(arm_permutations[index % len(arm_permutations)])
        for index, task_id in enumerate(ranked)
    }


def build_design(
    cohort_manifest: dict[str, Any],
    *,
    model_manifest_sha256: str,
    authority_manifest_sha256: str,
) -> dict[str, Any]:
    if len(model_manifest_sha256) != 64:
        raise DesignError("model manifest SHA-256 must be frozen")
    if len(authority_manifest_sha256) != 64:
        raise DesignError("authority manifest SHA-256 must be frozen")
    tasks = cohort_manifest.get("tasks", [])
    if len(tasks) != 96:
        raise DesignError(f"expected 96 cohort tasks, found {len(tasks)}")
    task_ids = {task["task_id"] for task in tasks}
    missing = set(POLICY_ADJUDICATIONS) - task_ids
    if missing:
        raise DesignError(f"policy task IDs absent from cohort: {sorted(missing)}")

    database_counts = {
        database: sum(task["db_name"] == database for task in tasks)
        for database in DATABASES
    }
    if set(database_counts.values()) != {24}:
        raise DesignError(f"expected 24 tasks per database: {database_counts}")

    primary_counts = {
        database: sum(
            task["db_name"] == database
            and task["task_id"] not in POLICY_ADJUDICATIONS
            for task in tasks
        )
        for database in DATABASES
    }
    if sum(primary_counts.values()) != 93:
        raise DesignError(
            f"expected 93 primary-eligible tasks: {primary_counts}"
        )

    folds = []
    for index, hidden_test in enumerate(DATABASES):
        fold_id = f"fold-{index}"
        visible_selection = DATABASES[(index + 1) % len(DATABASES)]
        evidence = sorted(
            set(DATABASES) - {hidden_test, visible_selection}
        )
        evidence_task_ids = _eligible_task_ids(tasks, set(evidence))
        selection_task_ids = _eligible_task_ids(
            tasks, {visible_selection}
        )
        hidden_task_ids = _eligible_task_ids(tasks, {hidden_test})
        mechanics_task_ids = _pilot_tasks(
            tasks,
            database=visible_selection,
            fold_id=fold_id,
        )
        sentinel_task_ids = sorted(
            selection_task_ids,
            key=lambda task_id: sha256_text(
                f"{SEED}\0{fold_id}\0sentinel\0{task_id}"
            ),
        )[:6]
        folds.append(
            {
                "fold_id": fold_id,
                "evidence_database_families": evidence,
                "visible_selection_database_family": visible_selection,
                "hidden_test_database_family": hidden_test,
                "evidence_task_ids": evidence_task_ids,
                "visible_selection_task_ids": selection_task_ids,
                "hidden_test_task_ids": hidden_task_ids,
                "mechanics_smoke_task_ids": mechanics_task_ids,
                # Compatibility alias for the first draft runner. Remove after
                # every external consumer reads mechanics_smoke_task_ids.
                "pilot_selection_task_ids": mechanics_task_ids,
                "nondeterminism_sentinel_task_ids": sentinel_task_ids,
                "arm_order": {
                    "mechanics_smoke": _balanced_arm_order(
                        mechanics_task_ids,
                        fold_id=fold_id,
                        stage="mechanics_smoke",
                    ),
                    "visible_selection_effect_screen": _balanced_arm_order(
                        selection_task_ids,
                        fold_id=fold_id,
                        stage="visible_selection_effect_screen",
                    ),
                    "hidden_test": _balanced_arm_order(
                        hidden_task_ids,
                        fold_id=fold_id,
                        stage="hidden_test",
                    ),
                },
            }
        )

    adjudications = [
        {
            "task_id": task_id,
            "classification": classification,
            "primary_quality_eligible": False,
        }
        for task_id, classification in sorted(POLICY_ADJUDICATIONS.items())
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "seed": SEED,
        "cohort_manifest_sha256": hashlib.sha256(
            canonical_bytes(cohort_manifest)
        ).hexdigest(),
        "database_counts": database_counts,
        "primary_quality_counts": primary_counts,
        "primary_quality_tasks": sum(primary_counts.values()),
        "policy_adjudications": adjudications,
        "model_manifest_sha256": model_manifest_sha256,
        "authority_manifest_sha256": authority_manifest_sha256,
        "prompt_contract": {
            "base_system_prompt": BASE_SYSTEM_PROMPT,
            "base_system_prompt_sha256": sha256_text(BASE_SYSTEM_PROMPT),
            "arm_artifacts": {
                arm: {
                    **ARM_CONTRACTS[arm],
                    "artifact": ARM_ARTIFACTS[arm],
                    "artifact_sha256": sha256_text(ARM_ARTIFACTS[arm]),
                }
                for arm in sorted(ARM_CONTRACTS)
            },
            "only_arm_specific_bytes": "procedure_artifact",
        },
        "arm_contracts": {
            arm: {
                **ARM_CONTRACTS[arm],
                "artifact_sha256": sha256_text(ARM_ARTIFACTS[arm]),
            }
            for arm in sorted(ARM_CONTRACTS)
        },
        "tool_contract": {
            "tools": TOOLS,
            "tools_sha256": hashlib.sha256(
                canonical_bytes(TOOLS)
            ).hexdigest(),
            "terminal_tools": ["submit_sql", "abstain"],
            "implicit_last_query_submission": False,
            "submission_reexecutes_sql": False,
        },
        "limits": LIMITS,
        "analysis_plan": ANALYSIS_PLAN,
        "failure_taxonomy": list(FAILURE_TAXONOMY),
        "stages": {
            "mechanics_smoke": {
                "tasks_per_fold": 4,
                "episodes_per_fold": 12,
                "effect_estimate_allowed": False,
            },
            "visible_selection_effect_screen": {
                "fold_0_primary_eligible_tasks": primary_counts[
                    "car_dealership"
                ],
                "fold_0_episodes": (
                    primary_counts["car_dealership"]
                    * len(ARM_CONTRACTS)
                ),
                "hidden_results_opened": False,
            },
            "hidden_test": {
                "requires_preregistered_selection_gate": True,
                "artifact_edits_after_selection": False,
            },
            "complete_four_fold_study": {
                "out_of_fold_primary_tasks": 93,
                "episodes": 93 * len(ARM_CONTRACTS),
            },
        },
        "folds": folds,
        "leakage_contract": {
            "pilot_uses_hidden_test_tasks": False,
            "candidate_generation_can_read_visible_selection": False,
            "candidate_generation_can_read_hidden_test": False,
            "skill_mining_may_read_only_evidence_families": True,
            "selection_scores_only_frozen_candidates": True,
            "hidden_test_runs_only_after_selection": True,
            "fresh_proposer_namespace_per_fold": True,
            "cross_fold_memory_cache_and_retrieval_disabled": True,
            "solver_has_source_checkout_access": False,
            "solver_has_evaluator_access": False,
            "proposer_has_selection_or_test_access": False,
            "hidden_outcomes_sealed_until_all_fold_artifacts_are_signed": True,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cohort-manifest", type=Path, required=True)
    parser.add_argument("--model-manifest", type=Path, required=True)
    parser.add_argument("--authority-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expect-sha256")
    args = parser.parse_args()
    cohort = json.loads(args.cohort_manifest.read_text(encoding="utf-8"))
    payload = canonical_bytes(
        build_design(
            cohort,
            model_manifest_sha256=hashlib.sha256(
                args.model_manifest.read_bytes()
            ).hexdigest(),
            authority_manifest_sha256=hashlib.sha256(
                args.authority_manifest.read_bytes()
            ).hexdigest(),
        )
    )
    actual = hashlib.sha256(payload).hexdigest()
    if args.expect_sha256 and actual != args.expect_sha256:
        raise SystemExit(
            f"design sha256 {actual} != expected {args.expect_sha256}"
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(payload)
    print(
        json.dumps(
            {
                "status": "ok",
                "output": str(args.output),
                "bytes": len(payload),
                "sha256": actual,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
