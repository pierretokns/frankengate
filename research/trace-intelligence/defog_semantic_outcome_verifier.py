#!/usr/bin/env python3
"""Recompute Defog semantic outcomes in a separate PostgreSQL process.

The runner's stored ``semantic_correct`` field is not treated as an authority.
This verifier resolves the pinned task, re-executes each submitted candidate
under the governed role, independently executes the sealed gold alternatives,
and compares result values. Raw SQL/results stay in an external verifier audit
directory; the committed receipt contains hashes and aggregate counts only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from sqlglot import exp

import defog_sql_factorial as factorial
from defog_factorial_authority import StaticAuthorityEpochStore
from defog_governed_sql_replay import (
    GovernedPostgresExecutor,
    GovernanceAuthority,
    results_equal,
    sha256_text,
)


def _load_end(path: Path) -> dict[str, Any]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    ends = [row for row in rows if row.get("event") == "factorial_task_end"]
    if len(ends) != 1:
        raise ValueError(f"{path}: expected one task-end event")
    return ends[0]


def _raw_path(raw_dir: Path, task_id: str, arm: str) -> Path:
    prefix = sha256_text(task_id)[:16]
    matches = sorted(raw_dir.glob(f"{prefix}-{arm}.jsonl"))
    if len(matches) != 1:
        raise ValueError(f"missing or duplicate raw audit for {prefix}-{arm}")
    return matches[0]


def _semantic_match(
    *, task: Any, candidate_sql: str, executor: GovernedPostgresExecutor
) -> tuple[bool, str | None]:
    try:
        _, candidate_result = executor.execute_candidate(candidate_sql)
        gold_results = executor.execute_gold_alternatives(task.gold_sql)
    except Exception as exc:
        return False, type(exc).__name__
    for statement, gold_result in gold_results:
        order_sensitive = any(
            bool(select.args.get("order"))
            for select in statement.find_all(exp.Select)
        )
        if results_equal(
            candidate_result, gold_result, order_sensitive=order_sensitive
        ):
            return True, None
    return False, None


def verify(
    *,
    result_path: Path,
    raw_dir: Path,
    source_root: Path,
    cohort_manifest: Path,
    dataset_manifest: Path,
    authority_manifest: Path,
    task_ids: list[str],
    dsn_template: str,
    verifier_audit_dir: Path,
) -> dict[str, Any]:
    result_bytes = result_path.read_bytes()
    result = json.loads(result_bytes)
    resolver = factorial.PinnedTaskResolver(
        source_root=source_root,
        manifest_path=cohort_manifest,
        dataset_manifest_path=dataset_manifest,
    )
    tasks = {task_id: resolver.resolve(task_id) for task_id in task_ids}
    task_by_hash = {sha256_text(task_id): task for task_id, task in tasks.items()}
    authority_store = StaticAuthorityEpochStore.from_path(authority_manifest)
    verifier_audit_dir.mkdir(parents=True, exist_ok=True)
    rows_by_arm: dict[str, list[dict[str, Any]]] = {}
    mismatches: list[str] = []
    errors: list[str] = []
    for row in result.get("task_runs", []):
        task_hash = str(row.get("task_id_sha256"))
        arm = str(row.get("arm"))
        task = task_by_hash.get(task_hash)
        if task is None:
            errors.append(f"unknown_task_hash:{task_hash}")
            continue
        raw_path = _raw_path(raw_dir, task.task_id, arm)
        end = _load_end(raw_path)
        candidate_sql = end.get("candidate_sql")
        recomputed = False
        error_class: str | None = None
        if candidate_sql:
            authority = GovernanceAuthority(
                governance_scope=factorial.AUTHORITY_SCOPE,
                authorization_epoch_ref=factorial.AUTHORIZATION_EPOCH_REF,
                user_id=factorial.AUTHORITY_USER_ID,
                team_id=factorial.AUTHORITY_TEAM_ID,
                virtual_key_id=factorial.AUTHORITY_VIRTUAL_KEY_ID,
            )
            receipt = authority_store.validate(
                database=task.database,
                governance_scope=authority.governance_scope,
                authorization_epoch_ref=authority.authorization_epoch_ref,
                user_id=authority.user_id,
                team_id=authority.team_id,
                virtual_key_id=authority.virtual_key_id,
            )
            audit_path = verifier_audit_dir / f"{task_hash[:16]}-{arm}.jsonl"
            executor = GovernedPostgresExecutor(
                dsn=dsn_template.format(database=task.database),
                authority=authority,
                audit_path=audit_path,
            )
            if not receipt.authority_valid:
                errors.append(f"authority_invalid:{task_hash}:{arm}")
            recomputed, error_class = _semantic_match(
                task=task, candidate_sql=str(candidate_sql), executor=executor
            )
        stored = bool(row.get("semantic_correct", False))
        if stored != recomputed:
            mismatches.append(f"{task_hash}:{arm}:stored={stored}:recomputed={recomputed}")
        record = {
            "task_id_sha256": task_hash,
            "arm": arm,
            "stored_semantic_correct": stored,
            "recomputed_semantic_correct": recomputed,
            "candidate_present": bool(candidate_sql),
            "candidate_sql_sha256": sha256_text(str(candidate_sql)) if candidate_sql else None,
            "error_class": error_class,
        }
        rows_by_arm.setdefault(arm, []).append(record)

    arms = {
        arm: {
            "tasks": len(rows),
            "stored_semantic_correct": sum(r["stored_semantic_correct"] for r in rows),
            "recomputed_semantic_correct": sum(
                r["recomputed_semantic_correct"] for r in rows
            ),
            "candidate_present": sum(r["candidate_present"] for r in rows),
            "error_rows": sum(r["error_class"] is not None for r in rows),
        }
        for arm, rows in sorted(rows_by_arm.items())
    }
    return {
        "schema_version": "frankengate-defog-semantic-independent-verification-v1",
        "source_result_sha256": hashlib.sha256(result_bytes).hexdigest(),
        "task_count": len(task_ids),
        "trajectory_count": sum(len(rows) for rows in rows_by_arm.values()),
        "arms": arms,
        "stored_vs_recomputed_mismatches": mismatches,
        "errors": errors,
        "semantic_recomputation": "executed_against_pinned_governed_postgres",
        "semantic_verification_passed": not mismatches and not errors,
        "raw_content_committed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--raw-audit-dir", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--cohort-manifest", type=Path, required=True)
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--authority-manifest", type=Path, required=True)
    parser.add_argument("--task-id", action="append", required=True)
    parser.add_argument("--dsn-template", required=True)
    parser.add_argument("--verifier-audit-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = verify(
        result_path=args.result.resolve(strict=True),
        raw_dir=args.raw_audit_dir.resolve(strict=True),
        source_root=args.source_root.resolve(strict=True),
        cohort_manifest=args.cohort_manifest.resolve(strict=True),
        dataset_manifest=args.dataset_manifest.resolve(strict=True),
        authority_manifest=args.authority_manifest.resolve(strict=True),
        task_ids=args.task_id,
        dsn_template=args.dsn_template,
        verifier_audit_dir=args.verifier_audit_dir.resolve(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(value, sort_keys=True))
    return 0 if value["semantic_verification_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
