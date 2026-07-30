#!/usr/bin/env python3
"""Run content-free conformance checks over the pinned Defog SQL cohort.

This is a verifier/policy self-check, not a model-quality experiment. Each
task's first gold alternative is treated as a candidate to prove that the
governed execution and semantic comparator agree. Policy-denied gold is
reported separately and rechecked only under an explicit conformance
entitlement or an explicit-column rewrite. No prompt, SQL, row, column name,
credential, or raw audit record is emitted to the aggregate result.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from typing import Any

import psycopg2
import sqlglot
from sqlglot import exp, parse

from defog_governed_sql_replay import (
    GovernanceAuthority,
    GovernedPostgresExecutor,
    PinnedTaskResolver,
    SQLPolicyError,
    SENSITIVE_NAME_PATTERN,
    evaluate_candidate,
    normalize_source_postgres_sql,
    split_sql_statements,
)


SCHEMA_VERSION = "frankengate-defog-replay-conformance-v1"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _authority() -> GovernanceAuthority:
    return GovernanceAuthority(
        governance_scope="enterprise",
        authorization_epoch_ref="conformance-epoch-v1",
        user_id="conformance-user",
        team_id="conformance-team",
        virtual_key_id="conformance-vk",
    )


def _executor(
    *,
    dsn_template: str,
    database: str,
    raw_audit_dir: Path | None,
    sensitive_entitlements: frozenset[str] = frozenset(),
) -> GovernedPostgresExecutor:
    audit_path = (
        raw_audit_dir / f"{database}.jsonl"
        if raw_audit_dir is not None
        else None
    )
    return GovernedPostgresExecutor(
        dsn=dsn_template.format(database=database),
        authority=_authority(),
        audit_path=audit_path,
        allowed_sensitive_projections=sensitive_entitlements,
    )


def sensitive_projection_names(statement: exp.Query) -> frozenset[str]:
    names: set[str] = set()
    for select in statement.find_all(exp.Select):
        for projection in select.expressions:
            output_name = (projection.alias_or_name or "").lower()
            if SENSITIVE_NAME_PATTERN.search(output_name):
                names.add(output_name)
            names.update(
                column.name.lower()
                for column in projection.find_all(exp.Column)
                if SENSITIVE_NAME_PATTERN.search(column.name)
            )
    return frozenset(names)


def expand_outer_wildcard(
    statement: exp.Query,
    output_columns: tuple[str, ...],
) -> exp.Query:
    """Replace an outer SELECT * with explicit result columns.

    This rewrite is used only to prove that the strict wildcard policy does not
    prevent the task from being semantically evaluable. Production candidates
    must name columns themselves.
    """

    rewritten = statement.copy()
    if not isinstance(rewritten, exp.Select):
        raise ValueError("only an outer SELECT wildcard can be expanded")
    expressions: list[exp.Expression] = []
    expanded = False
    for projection in rewritten.expressions:
        if isinstance(projection, exp.Star):
            expressions.extend(
                exp.Column(this=exp.Identifier(this=column, quoted=True))
                for column in output_columns
            )
            expanded = True
        else:
            expressions.append(projection)
    if not expanded:
        raise ValueError("outer SELECT does not contain a wildcard")
    rewritten.set("expressions", expressions)
    return rewritten


def _security_controls(
    executor: GovernedPostgresExecutor,
) -> dict[str, bool]:
    catalog = executor.catalog()
    table = sorted(catalog)[0]
    table_name = table.split(".", 1)[-1].replace('"', '""')
    column_name = sorted(catalog[table])[0].replace('"', '""')
    parser_controls = {
        "multiple_statements_denied": (
            f'SELECT "{column_name}" FROM "{table_name}"; '
            f'SELECT "{column_name}" FROM "{table_name}"'
        ),
        "mutation_denied": f'DELETE FROM "{table_name}"',
        "system_function_denied": (
            f"SELECT pg_read_file('/etc/passwd') FROM \"{table_name}\""
        ),
        "unknown_table_denied": "SELECT value FROM must_not_exist",
        "wildcard_denied": f'SELECT * FROM "{table_name}"',
    }
    outcomes: dict[str, bool] = {}
    for name, sql in parser_controls.items():
        try:
            executor.execute_candidate(sql)
        except SQLPolicyError:
            outcomes[name] = True
        else:
            outcomes[name] = False
    try:
        executor._execute_unchecked(
            "CREATE TABLE frankengate_conformance_must_not_exist(value integer)"
        )
    except Exception:
        outcomes["database_read_only_denied_mutation"] = True
    else:
        outcomes["database_read_only_denied_mutation"] = False
    return outcomes


def run(
    *,
    source_root: Path,
    manifest_path: Path,
    dataset_manifest_path: Path,
    dsn_template: str,
    raw_audit_dir: Path | None = None,
) -> dict[str, Any]:
    resolver = PinnedTaskResolver(
        source_root=source_root,
        manifest_path=manifest_path,
        dataset_manifest_path=dataset_manifest_path,
    )
    default_counts: Counter[str] = Counter()
    remediation_counts: Counter[str] = Counter()
    database_counts: dict[str, Counter[str]] = defaultdict(Counter)
    semantic_matches = 0
    executable_tasks = 0
    result_hashes: list[str] = []
    source_repair_counts: Counter[str] = Counter()
    source_invalid_task_ids: list[str] = []

    for task_id in sorted(resolver.tasks):
        task = resolver.resolve(task_id)
        candidate_sql, repairs = normalize_source_postgres_sql(
            split_sql_statements(task.gold_sql)[0]
        )
        source_repair_counts.update(repairs)
        candidate_statement = parse(candidate_sql, read="postgres")[0]
        executor = _executor(
            dsn_template=dsn_template,
            database=task.database,
            raw_audit_dir=raw_audit_dir,
        )
        receipt = evaluate_candidate(
            task=task,
            candidate_sql=candidate_sql,
            executor=executor,
        )
        if receipt.security_authorized and receipt.candidate_result_sha256:
            executable_tasks += 1
        if receipt.semantic_correct and receipt.security_authorized:
            outcome = "semantic_match"
            semantic_matches += 1
            if receipt.candidate_result_sha256:
                result_hashes.append(receipt.candidate_result_sha256)
        else:
            outcome = receipt.policy_error_code or receipt.error_class or "mismatch"
        default_counts[outcome] += 1
        database_counts[task.database][outcome] += 1

        if outcome == "sensitive_projection":
            entitlements = sensitive_projection_names(candidate_statement)
            entitled_executor = _executor(
                dsn_template=dsn_template,
                database=task.database,
                raw_audit_dir=raw_audit_dir,
                sensitive_entitlements=entitlements,
            )
            entitled = evaluate_candidate(
                task=task,
                candidate_sql=candidate_sql,
                executor=entitled_executor,
            )
            remediated = (
                "explicit_entitlement_semantic_match"
                if entitled.semantic_correct and entitled.security_authorized
                else "explicit_entitlement_failed"
            )
            remediation_counts[remediated] += 1
            if entitled.security_authorized and entitled.candidate_result_sha256:
                executable_tasks += 1
            if entitled.semantic_correct:
                semantic_matches += 1
                if entitled.candidate_result_sha256:
                    result_hashes.append(entitled.candidate_result_sha256)
        elif outcome == "wildcard_projection":
            try:
                gold_result = executor.execute_gold_alternatives(
                    task.gold_sql
                )[0][1]
            except Exception:
                remediation_counts[
                    "source_postgres_invalid_after_dialect_repair"
                ] += 1
                source_invalid_task_ids.append(task.task_id)
                continue
            rewritten = expand_outer_wildcard(
                candidate_statement, gold_result.columns
            )
            explicit = evaluate_candidate(
                task=task,
                candidate_sql=rewritten.sql(dialect="postgres"),
                executor=executor,
            )
            remediated = (
                "explicit_columns_semantic_match"
                if explicit.semantic_correct and explicit.security_authorized
                else "explicit_columns_failed"
            )
            remediation_counts[remediated] += 1
            if explicit.security_authorized and explicit.candidate_result_sha256:
                executable_tasks += 1
            if explicit.semantic_correct:
                semantic_matches += 1
                if explicit.candidate_result_sha256:
                    result_hashes.append(explicit.candidate_result_sha256)

    security_by_database = {}
    for database in sorted(database_counts):
        executor = _executor(
            dsn_template=dsn_template,
            database=database,
            raw_audit_dir=raw_audit_dir,
        )
        security_by_database[database] = _security_controls(executor)

    missing_epoch_denied = False
    try:
        GovernanceAuthority(
            governance_scope="enterprise",
            authorization_epoch_ref=None,
            user_id="conformance-user",
        ).validate()
    except Exception:
        missing_epoch_denied = True

    dataset_manifest = json.loads(
        dataset_manifest_path.read_text(encoding="utf-8")
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment_date": "2026-07-30",
        "classification": "verifier_and_policy_self_check_not_model_factorial",
        "source": {
            "dataset_id": dataset_manifest["dataset_id"],
            "dataset_revision": dataset_manifest["dataset_revision"],
            "cohort_tasks": len(resolver.tasks),
            "cohort_manifest_sha256": sha256_file(manifest_path),
            "dataset_manifest_sha256": sha256_file(dataset_manifest_path),
            "runner_sha256": sha256_file(Path(__file__).resolve()),
            "policy_module_sha256": sha256_file(
                Path(__file__).with_name("defog_governed_sql_replay.py")
            ),
        },
        "runtime": {
            "database_engine": "postgresql",
            "sqlglot": sqlglot.__version__,
            "psycopg2": psycopg2.__version__.split()[0],
        },
        "default_policy": {
            "outcomes": dict(sorted(default_counts.items())),
            "by_database": {
                database: dict(sorted(counts.items()))
                for database, counts in sorted(database_counts.items())
            },
        },
        "source_dialect_repairs": dict(sorted(source_repair_counts.items())),
        "explicit_policy_remediation": dict(
            sorted(remediation_counts.items())
        ),
        "semantic_comparator": {
            "all_executable_tasks_matched_under_valid_policy": (
                semantic_matches == executable_tasks
            ),
            "matched_tasks": semantic_matches,
            "executable_tasks": executable_tasks,
            "source_postgres_invalid_tasks": len(source_invalid_task_ids),
            "source_postgres_invalid_task_set_sha256": hashlib.sha256(
                "\n".join(sorted(source_invalid_task_ids)).encode("ascii")
            ).hexdigest(),
            "result_receipt_set_sha256": hashlib.sha256(
                "\n".join(sorted(result_hashes)).encode("ascii")
            ).hexdigest(),
        },
        "security_controls": {
            "governance_scope_without_epoch_denied": missing_epoch_denied,
            "by_database": security_by_database,
            "all_controls_passed": missing_epoch_denied
            and all(
                all(outcomes.values())
                for outcomes in security_by_database.values()
            ),
        },
        "limits": asdict(
            _executor(
                dsn_template=dsn_template,
                database=sorted(database_counts)[0],
                raw_audit_dir=None,
            ).limits
        ),
        "interpretation": {
            "default_sensitive_projection_denials_are_expected": True,
            "default_wildcard_denial_is_expected": True,
            "explicit_entitlements_are_conformance_only_not_inferred_from_gold_in_production": True,
            "source_invalid_tasks_require_manual_adjudication_or_exclusion": True,
            "proves_model_quality": False,
            "proves_aurora_compatibility": False,
            "proves_rls_policy_correctness": False,
        },
        "raw_data_committed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--dsn-template", required=True)
    parser.add_argument("--raw-audit-dir", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(
        source_root=args.source_root,
        manifest_path=args.manifest,
        dataset_manifest_path=args.dataset_manifest,
        dsn_template=args.dsn_template,
        raw_audit_dir=args.raw_audit_dir,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "output": str(args.output),
                "cohort_tasks": result["source"]["cohort_tasks"],
                "all_tasks_matched": result["semantic_comparator"][
                    "all_executable_tasks_matched_under_valid_policy"
                ],
                "all_security_controls_passed": result["security_controls"][
                    "all_controls_passed"
                ],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
