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
from dataclasses import replace
from pathlib import Path
from typing import Any

import defog_sql_factorial as factorial
from defog_factorial_authority import StaticAuthorityEpochStore
from codex_native_cli_api import NativeCodexCLIAPI


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
    "length_matched_neutral": "",
}
SCHEMA_FIRST_CONTROLLER_PROMPT = (
    " Protocol controller: before any execute_sql call, call describe_schema "
    "and use only the returned tables and columns. If a query is rejected, "
    "repair it from the observed policy error and schema; do not repeat the "
    "same invalid identifier."
)

PARAPHRASE_MUTATIONS = {
    "defog-sql-eval:instruct_advanced_postgres:broker:11:9c7b2337a36d": (
        "How many customers have names beginning with J or ending in 'ez', "
        "and reside in states whose names end with 'a'?"
    ),
    "defog-sql-eval:instruct_advanced_postgres:broker:12:9e137a09d497": (
        "For customers joining on or after January 1, 2023, report each "
        "country's TAC and its count."
    ),
    "defog-sql-eval:instruct_advanced_postgres:broker:14:e4d51056245a": (
        "For customers who joined during 2022, report the AR for every "
        "country, including country and AR."
    ),
    "defog-sql-eval:instruct_advanced_postgres:broker:2:fcfd29423477": (
        "Among customers with at least five total transactions, report each "
        "customer's transaction success rate and name, ordered from lowest "
        "to highest success rate."
    ),
}
PARAPHRASE_MUTATION_ID = "broker-four-task-renamed-paraphrase-v1"


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _arm_prompt_addition(
    arm: str,
    require_schema_before_sql: bool,
    trace_mined_text: str | None = None,
) -> str:
    if arm == "length_matched_neutral":
        target = len(trace_mined_text or "") or 308
        sentence = (
            "For this experiment, keep the response organized, follow the "
            "stated interaction protocol, and use the supplied interface "
            "consistently. "
        )
        neutral = (sentence * ((target // len(sentence)) + 1))[:target]
        return (SCHEMA_FIRST_CONTROLLER_PROMPT if require_schema_before_sql else "") + neutral
    return (
        (SCHEMA_FIRST_CONTROLLER_PROMPT if require_schema_before_sql else "")
        + (
            trace_mined_text
            if arm == "trace_mined_terminal_discipline"
            and trace_mined_text is not None
            else ARM_ADDITIONS[arm]
        )
    )


def _arm_classification(arm: str) -> str:
    if arm == "no_skill":
        return "baseline"
    if arm == "formatting_placebo" or arm.endswith("neutral"):
        return "placebo"
    if arm == "trace_mined_terminal_discipline":
        return "trace_mined_candidate"
    return "additional_control"


def _apply_task_mutation(tasks: list[Any], mutation: str | None) -> tuple[list[Any], dict[str, Any]]:
    if mutation is None:
        return tasks, {"id": None, "changed_count": 0, "mapping_sha256": None}
    if mutation != PARAPHRASE_MUTATION_ID:
        raise factorial.FactorialError(f"unknown task mutation: {mutation}")
    mutated = []
    mapping: dict[str, str] = {}
    for task in tasks:
        question = PARAPHRASE_MUTATIONS.get(task.task_id)
        if question is None:
            raise factorial.FactorialError(
                f"{mutation}: task has no sealed paraphrase: {task.task_id}"
            )
        mutated.append(replace(task, question=question))
        mapping[task.task_id] = _sha256_text(question)
    return mutated, {
        "id": mutation,
        "changed_count": len(mutated),
        "mapping_sha256": _sha256_text(
            json.dumps(mapping, sort_keys=True, separators=(",", ":"))
        ),
    }


def _load_trace_mined_candidate(
    path: Path | None,
) -> tuple[str | None, dict[str, Any]]:
    if path is None:
        return None, {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("candidate_class") != "trace_mined_hypothesis":
        raise factorial.FactorialError("candidate artifact is not trace-mined")
    text = value.get("candidate_text")
    if not isinstance(text, str) or not text.strip():
        raise factorial.FactorialError("candidate artifact has no text")
    if value.get("candidate_text_sha256") != _sha256_text(text):
        raise factorial.FactorialError("candidate artifact text hash mismatch")
    return text, {
        "artifact_sha256": _sha256_file(path),
        "candidate_text_sha256": value["candidate_text_sha256"],
        "source_raw_directory_digest": value.get("source_raw_directory_digest"),
        "source_raw_file_count": value.get("source_raw_file_count"),
    }


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
    model_provider: str = "ollama",
    endpoint_scope: str = "loopback-only",
    raw_audit_dir: Path,
    output: Path,
    seed_base: int = 310000,
    max_model_turns: int | None = None,
    max_sql_attempts: int | None = None,
    max_tokens: int | None = None,
    request_timeout_seconds: int | None = None,
    max_generated_tokens_per_episode: int | None = None,
    protocol_remediation_id: str = "frozen-default-v1",
    require_schema_before_sql: bool = False,
    inject_authorized_schema: bool = False,
    trace_mined_candidate_file: Path | None = None,
    arms: tuple[str, ...] | None = None,
    task_mutation: str | None = None,
    harness: str = "openai-proxy",
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
    tasks, mutation_receipt = _apply_task_mutation(tasks, task_mutation)
    selected_arms = tuple(arms or ARMS)
    if not selected_arms or len(set(selected_arms)) != len(selected_arms):
        raise factorial.FactorialError("arms must be non-empty and unique")
    unknown_arms = set(selected_arms) - set(ARM_ADDITIONS)
    if unknown_arms:
        raise factorial.FactorialError(f"unknown pilot arms: {sorted(unknown_arms)}")
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
    api_class = NativeCodexCLIAPI if harness == "codex-cli-native-json-v1" else factorial.ChatAPI
    if harness not in {"openai-proxy", "codex-cli-native-json-v1"}:
        raise factorial.FactorialError(f"unknown harness: {harness}")
    api = api_class(
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
    trace_mined_text, trace_mined_artifact = _load_trace_mined_candidate(
        trace_mined_candidate_file
    )
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
            for arm in selected_arms:
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
                    + _arm_prompt_addition(
                        arm, require_schema_before_sql, trace_mined_text
                    )
                )
                receipts.append(
                    (task, authority_receipt, factorial.run_agent(
                        task=task,
                        arm=arm,
                        seed=factorial._task_seed(task.task_id, seed_base),
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
    for arm in selected_arms:
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
        "classification": (
            "family_disjoint_transfer"
            if protocol_remediation_id.startswith("family-disjoint")
            else "domain_valid_visible_selection_pilot"
        ),
        "dataset": {
            "cohort_manifest_sha256": _sha256_file(cohort_manifest),
            "dataset_manifest_sha256": _sha256_file(dataset_manifest),
            "task_count": len(tasks),
            "task_id_sha256": [_sha256_text(task.task_id) for task in tasks],
            "database_family": tasks[0].database,
        },
        "model": {
            "provider": model_provider,
            "request_model_id": model,
            "endpoint_scope": endpoint_scope,
            "harness": harness,
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
            "seed_base": seed_base,
            "authority_contract_changed": False,
            "require_schema_before_sql": require_schema_before_sql,
            "schema_first_controller_sha256": _sha256_text(
                SCHEMA_FIRST_CONTROLLER_PROMPT if require_schema_before_sql else ""
            ),
            "inject_authorized_schema": inject_authorized_schema,
            "schema_catalog_sha256": schema_catalog_sha256,
            "trace_mined_candidate": trace_mined_artifact,
            "task_mutation": mutation_receipt,
        },
        "authority": {
            "binding_sha256": sorted({receipt.binding_sha256 for receipt in authority_receipts}),
            "epoch_ref_sha256": sorted({receipt.epoch_ref_sha256 for receipt in authority_receipts}),
            "snapshot_sha256": sorted({receipt.authority_snapshot_sha256 for receipt in authority_receipts}),
            "exact_current_epoch_match": all(receipt.authority_valid for receipt in authority_receipts),
        },
        "arm_artifacts": {
            arm: {
                "classification": _arm_classification(arm),
                "sha256": _sha256_text(
                    schema_catalog_prompt
                    + _arm_prompt_addition(
                        arm, require_schema_before_sql, trace_mined_text
                    )
                ),
                "char_length": len(
                    schema_catalog_prompt
                    + _arm_prompt_addition(
                        arm, require_schema_before_sql, trace_mined_text
                    )
                ),
                "word_count": len(
                    (
                        schema_catalog_prompt
                        + _arm_prompt_addition(
                            arm, require_schema_before_sql, trace_mined_text
                        )
                    ).split()
                ),
            }
            for arm in selected_arms
        },
        "arms": by_arm,
        "task_runs": runs,
        "raw_audit_policy": "external_jsonl_only; raw SQL, prompts, rows, and model messages are not committed",
        "claim_boundary": {
            "governed_postgres_executed": True,
            "domain_valid_task_executed": True,
            "arms_executed": list(selected_arms),
            "all_arms_executed": len(receipts) == len(selected_arms) * len(tasks),
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
    parser.add_argument("--model-provider", default="ollama")
    parser.add_argument("--endpoint-scope", default="loopback-only")
    parser.add_argument("--raw-audit-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed-base", type=int, default=310000)
    parser.add_argument("--max-model-turns", type=int)
    parser.add_argument("--max-sql-attempts", type=int)
    parser.add_argument("--max-tokens", type=int)
    parser.add_argument("--request-timeout-seconds", type=int)
    parser.add_argument("--max-generated-tokens-per-episode", type=int)
    parser.add_argument("--protocol-remediation-id", default="frozen-default-v1")
    parser.add_argument("--require-schema-before-sql", action="store_true")
    parser.add_argument("--inject-authorized-schema", action="store_true")
    parser.add_argument("--trace-mined-candidate-file", type=Path)
    parser.add_argument(
        "--arm",
        action="append",
        choices=sorted(ARM_ADDITIONS),
        help="Override the default arms; repeat once per arm.",
    )
    parser.add_argument(
        "--task-mutation",
        choices=(PARAPHRASE_MUTATION_ID,),
        help="Apply a sealed prompt-only mutation while preserving task gold SQL.",
    )
    parser.add_argument(
        "--harness",
        choices=("openai-proxy", "codex-cli-native-json-v1"),
        default="openai-proxy",
    )
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
        model_provider=args.model_provider,
        endpoint_scope=args.endpoint_scope,
        raw_audit_dir=args.raw_audit_dir,
        output=args.output,
        seed_base=args.seed_base,
        max_model_turns=args.max_model_turns,
        max_sql_attempts=args.max_sql_attempts,
        max_tokens=args.max_tokens,
        request_timeout_seconds=args.request_timeout_seconds,
        max_generated_tokens_per_episode=args.max_generated_tokens_per_episode,
        protocol_remediation_id=args.protocol_remediation_id,
        require_schema_before_sql=args.require_schema_before_sql,
        inject_authorized_schema=args.inject_authorized_schema,
        trace_mined_candidate_file=(
            args.trace_mined_candidate_file.resolve(strict=True)
            if args.trace_mined_candidate_file is not None
            else None
        ),
        arms=tuple(args.arm) if args.arm else None,
        task_mutation=args.task_mutation,
        harness=args.harness,
    )
    print(json.dumps({"status": "ok", "arms": result["arms"], "causal_skill_benefit_established": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
