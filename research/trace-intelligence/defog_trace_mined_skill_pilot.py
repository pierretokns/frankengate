"""Run a bounded domain-valid Defog no-skill/placebo/mined-skill pilot.

The task and database are pinned by the supplied manifests.  Raw model
messages, SQL, schema observations, and rows are required to live in an
external audit directory; the committed result contains only hashes and
content-free outcome receipts.  The default invocation uses a small visible
selection pilot and cannot establish general skill benefit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import defog_sql_factorial as factorial
from defog_factorial_authority import StaticAuthorityEpochStore


SCHEMA_VERSION = "frankengate-defog-trace-mined-skill-pilot-v2"
ARMS = ("no_skill", "formatting_placebo", "trace_mined_terminal_discipline")
ARM_ADDITIONS = {
    "no_skill": "",
    "formatting_placebo": (
        " Use compact headings, short sentences, and stable SQL indentation. "
        "Preserve tool names exactly as supplied."
    ),
    "trace_mined_terminal_discipline": (
        " Trace-mined procedure: inspect each schema/result observation before "
        "acting; preserve the successful attempt identifier; after a successful "
        "query, submit that exact attempt; never emit a prose-only response and "
        "never issue another execute_sql after the attempt budget is exhausted."
    ),
}
SCHEMA_FIRST_CONTROLLER_PROMPT = (
    " Protocol controller: before any execute_sql call, call describe_schema "
    "and use only the returned tables and columns. If a query is rejected, "
    "repair it from the observed policy error and schema; do not repeat the "
    "same invalid identifier."
)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _arm_prompt_addition(arm: str, require_schema_before_sql: bool) -> str:
    return (
        (SCHEMA_FIRST_CONTROLLER_PROMPT if require_schema_before_sql else "")
        + ARM_ADDITIONS[arm]
    )


def run_pilot(
    *,
    source_root: Path,
    cohort_manifest: Path,
    dataset_manifest: Path,
    authority_manifest: Path,
    task_ids: list[str],
    dsn: str,
    endpoint: str,
    model: str,
    raw_audit_dir: Path,
    output: Path,
    max_model_turns: int | None = None,
    max_sql_attempts: int | None = None,
    max_tokens: int | None = None,
    request_timeout_seconds: int | None = None,
    max_generated_tokens_per_episode: int | None = None,
    protocol_remediation_id: str = "frozen-default-v1",
    require_schema_before_sql: bool = False,
    inject_authorized_schema: bool = False,
) -> dict[str, Any]:
    factorial._require_external_raw_audit_dir(raw_audit_dir)
    if output.exists():
        raise factorial.FactorialError(f"refusing to overwrite {output}")
    resolver = factorial.PinnedTaskResolver(
        source_root=source_root,
        manifest_path=cohort_manifest,
        dataset_manifest_path=dataset_manifest,
    )
    tasks = [resolver.resolve(task_id) for task_id in task_ids]
    if not tasks:
        raise factorial.FactorialError("at least one task is required")
    database_families = {task.database for task in tasks}
    if len(database_families) != 1:
        raise factorial.FactorialError("pilot tasks must share one database family")
    authority = factorial.GovernanceAuthority(
        governance_scope=factorial.AUTHORITY_SCOPE,
        authorization_epoch_ref=factorial.AUTHORIZATION_EPOCH_REF,
        user_id=factorial.AUTHORITY_USER_ID,
        team_id=factorial.AUTHORITY_TEAM_ID,
        virtual_key_id=factorial.AUTHORITY_VIRTUAL_KEY_ID,
    )
    authority_store = StaticAuthorityEpochStore.from_path(authority_manifest)
    api = factorial.ChatAPI(
        endpoint=endpoint,
        request_model_id=model,
        timeout_seconds=(
            request_timeout_seconds
            if request_timeout_seconds is not None
            else factorial.FROZEN_LIMITS["model_wall_seconds"]
        ),
        max_tokens=(
            max_tokens
            if max_tokens is not None
            else factorial.FROZEN_LIMITS["max_generated_tokens_per_call"]
        ),
    )
    resolved_turns = (
        max_model_turns
        if max_model_turns is not None
        else factorial.FROZEN_LIMITS["max_model_turns"]
    )
    resolved_sql_attempts = (
        max_sql_attempts
        if max_sql_attempts is not None
        else factorial.FROZEN_LIMITS["max_sql_attempts"]
    )
    resolved_episode_tokens = (
        max_generated_tokens_per_episode
        if max_generated_tokens_per_episode is not None
        else factorial.FROZEN_LIMITS["max_generated_tokens_per_episode"]
    )
    limits = factorial.AgentLimits(
        max_model_turns=resolved_turns,
        max_sql_attempts=resolved_sql_attempts,
        max_generated_tokens_per_episode=resolved_episode_tokens,
        model_wall_seconds=(
            request_timeout_seconds
            if request_timeout_seconds is not None
            else factorial.FROZEN_LIMITS["model_wall_seconds"]
        ),
    )
    previous_prompts = dict(factorial.ARM_PROMPTS)
    receipts = []
    schema_catalog_prompt = ""
    schema_catalog_sha256 = ""
    try:
        for task in tasks:
            authority_receipt = authority_store.validate(
                database=task.database,
                governance_scope=authority.governance_scope,
                authorization_epoch_ref=authority.authorization_epoch_ref,
                user_id=authority.user_id,
                team_id=authority.team_id,
                virtual_key_id=authority.virtual_key_id,
            )
            task_hash = _sha256_text(task.task_id)[:16]
            for arm in ARMS:
                raw_path = raw_audit_dir / f"{task_hash}-{arm}.jsonl"
                executor = factorial.GovernedPostgresExecutor(
                    dsn=dsn,
                    authority=authority,
                    audit_path=raw_path,
                )
                if inject_authorized_schema and not schema_catalog_prompt:
                    catalog = executor.catalog()
                    schema_catalog_prompt = (
                        " Authorized schema catalog (use only these identifiers): "
                        + json.dumps(
                            {
                                table: sorted(columns)
                                for table, columns in sorted(catalog.items())
                            },
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                    )
                    schema_catalog_sha256 = _sha256_text(schema_catalog_prompt)
                factorial.ARM_PROMPTS[arm] = (
                    schema_catalog_prompt
                    + _arm_prompt_addition(arm, require_schema_before_sql)
                )
                receipts.append(
                    (task, authority_receipt, factorial.run_agent(
                        task=task,
                        arm=arm,
                        seed=factorial._task_seed(task.task_id, 310000),
                        api=api,
                        executor=executor,
                        limits=limits,
                        raw_audit_path=raw_path,
                        authority_receipt=authority_receipt,
                        terminal_fallback=True,
                    ))
                )
    finally:
        factorial.ARM_PROMPTS.clear()
        factorial.ARM_PROMPTS.update(previous_prompts)
    def content_free(task: Any, authority_receipt: Any, receipt: Any) -> dict[str, Any]:
        return {
            "task_id_sha256": _sha256_text(task.task_id),
            "arm": receipt.arm,
            "semantic_correct": receipt.semantic_correct,
            "strict_answer_shape_correct": receipt.strict_answer_shape_correct,
            "authority_valid": receipt.authority_valid,
            "policy_accepted": receipt.policy_accepted,
            "execution_completed": receipt.execution_completed,
            "unauthorized_observation": receipt.unauthorized_observation,
            "outcome": receipt.outcome,
            "terminal_action": receipt.terminal_action,
            "terminal_fallback_used": receipt.terminal_fallback_used,
            "protocol_failure_code": receipt.protocol_failure_code,
            "tool_calls": receipt.tool_calls,
            "schema_calls": receipt.schema_calls,
            "sql_attempts": receipt.sql_attempts,
            "successful_sql_attempts": receipt.successful_sql_attempts,
            "prompt_tokens": receipt.prompt_tokens,
            "completion_tokens": receipt.completion_tokens,
            "elapsed_ms": receipt.elapsed_ms,
            "authority_binding_sha256": authority_receipt.binding_sha256,
            "attempt_receipt_chain_sha256": receipt.attempt_receipt_chain_sha256,
            "raw_audit_sha256": receipt.raw_audit_sha256,
        }

    runs = [content_free(task, authority_receipt, receipt) for task, authority_receipt, receipt in receipts]
    by_arm: dict[str, Any] = {}
    for arm in ARMS:
        rows = [row for row in runs if row["arm"] == arm]
        by_arm[arm] = {
            "tasks": len(rows),
            "semantic_correct": sum(row["semantic_correct"] for row in rows),
            "strict_answer_shape_correct": sum(row["strict_answer_shape_correct"] for row in rows),
            "authority_valid": sum(row["authority_valid"] for row in rows),
            "policy_accepted": sum(row["policy_accepted"] is True for row in rows),
            "execution_completed": sum(row["execution_completed"] for row in rows),
            "unauthorized_observation": sum(row["unauthorized_observation"] for row in rows),
            "terminal_submissions": sum(row["terminal_action"] == "submit_sql" for row in rows),
            "terminal_fallback_used": sum(row["terminal_fallback_used"] for row in rows),
            "missing_terminal_action": sum(row["terminal_action"] == "none" for row in rows),
            "successful_sql_attempts": sum(row["successful_sql_attempts"] for row in rows),
            "tool_calls": sum(row["tool_calls"] for row in rows),
            "sql_attempts": sum(row["sql_attempts"] for row in rows),
            "outcomes": {outcome: sum(row["outcome"] == outcome for row in rows) for outcome in sorted({row["outcome"] for row in rows})},
        }
    authority_receipts = [authority_receipt for _, authority_receipt, _ in receipts]
    result = {
        "schema_version": SCHEMA_VERSION,
        "classification": "domain_valid_visible_selection_pilot",
        "dataset": {
            "cohort_manifest_sha256": _sha256_file(cohort_manifest),
            "dataset_manifest_sha256": _sha256_file(dataset_manifest),
            "task_count": len(tasks),
            "task_id_sha256": [_sha256_text(task.task_id) for task in tasks],
            "database_family": tasks[0].database,
        },
        "model": {
            "provider": "ollama",
            "request_model_id": model,
            "endpoint_scope": "loopback-only",
        },
        "protocol_remediation": {
            "id": protocol_remediation_id,
            "max_model_turns": resolved_turns,
            "max_sql_attempts": resolved_sql_attempts,
            "max_generated_tokens_per_episode": resolved_episode_tokens,
            "max_generated_tokens_per_call": api.max_tokens,
            "request_timeout_seconds": api.timeout_seconds,
            "applies_identically_across_arms": True,
            "base_prompt_changed": False,
            "arm_artifacts_changed": False,
            "task_selection_changed": False,
            "authority_contract_changed": False,
            "require_schema_before_sql": require_schema_before_sql,
            "schema_first_controller_sha256": _sha256_text(
                SCHEMA_FIRST_CONTROLLER_PROMPT if require_schema_before_sql else ""
            ),
            "inject_authorized_schema": inject_authorized_schema,
            "schema_catalog_sha256": schema_catalog_sha256,
        },
        "authority": {
            "binding_sha256": sorted({receipt.binding_sha256 for receipt in authority_receipts}),
            "epoch_ref_sha256": sorted({receipt.epoch_ref_sha256 for receipt in authority_receipts}),
            "snapshot_sha256": sorted({receipt.authority_snapshot_sha256 for receipt in authority_receipts}),
            "exact_current_epoch_match": all(receipt.authority_valid for receipt in authority_receipts),
        },
        "arm_artifacts": {
            arm: {
                "classification": "baseline" if arm == "no_skill" else "placebo" if arm == "formatting_placebo" else "trace_mined_candidate",
                "sha256": _sha256_text(
                    schema_catalog_prompt
                    + _arm_prompt_addition(arm, require_schema_before_sql)
                ),
            }
            for arm in ARMS
        },
        "arms": by_arm,
        "task_runs": runs,
        "raw_audit_policy": "external_jsonl_only; raw SQL, prompts, rows, and model messages are not committed",
        "claim_boundary": {
            "governed_postgres_executed": True,
            "domain_valid_task_executed": True,
            "three_arms_executed": len(receipts) == 3 * len(tasks),
            "causal_skill_benefit_established": False,
            "reason": "This is a visible-selection pilot; no family-disjoint held-out quality estimate or independent verifier comparison is claimed.",
            "next_required": "Rerun after protocol remediation on a family-disjoint fold with sealed outcomes, independent semantic/security verifier, and paired repair/regression analysis.",
        },
        "terminal_fallback_policy": {
            "id": "submit-most-recent-successful-authorized-attempt-or-abstain-v1",
            "applies_identically_across_arms": True,
            "reads_gold_or_hidden_outcomes": False,
            "selection_rule": "most recent successful authorized candidate; abstain when none exists",
            "purpose": "Separate SQL generation quality from model terminal-tool formatting.",
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--cohort-manifest", type=Path, required=True)
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--authority-manifest", type=Path, required=True)
    parser.add_argument("--task-id", action="append", required=True)
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--raw-audit-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-model-turns", type=int)
    parser.add_argument("--max-sql-attempts", type=int)
    parser.add_argument("--max-tokens", type=int)
    parser.add_argument("--request-timeout-seconds", type=int)
    parser.add_argument("--max-generated-tokens-per-episode", type=int)
    parser.add_argument("--protocol-remediation-id", default="frozen-default-v1")
    parser.add_argument("--require-schema-before-sql", action="store_true")
    parser.add_argument("--inject-authorized-schema", action="store_true")
    args = parser.parse_args()
    result = run_pilot(
        source_root=args.source_root.resolve(strict=True),
        cohort_manifest=args.cohort_manifest.resolve(strict=True),
        dataset_manifest=args.dataset_manifest.resolve(strict=True),
        authority_manifest=args.authority_manifest.resolve(strict=True),
        task_ids=args.task_id,
        dsn=args.dsn,
        endpoint=args.endpoint,
        model=args.model,
        raw_audit_dir=args.raw_audit_dir,
        output=args.output,
        max_model_turns=args.max_model_turns,
        max_sql_attempts=args.max_sql_attempts,
        max_tokens=args.max_tokens,
        request_timeout_seconds=args.request_timeout_seconds,
        max_generated_tokens_per_episode=args.max_generated_tokens_per_episode,
        protocol_remediation_id=args.protocol_remediation_id,
        require_schema_before_sql=args.require_schema_before_sql,
        inject_authorized_schema=args.inject_authorized_schema,
    )
    print(json.dumps({"status": "ok", "arms": result["arms"], "causal_skill_benefit_established": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
