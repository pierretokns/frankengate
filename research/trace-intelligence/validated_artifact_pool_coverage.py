#!/usr/bin/env python3
"""Measure the semantic-reuse ceiling of a validated SQL-artifact pool.

This is an evaluation-only oracle diagnostic. It uses each target's gold SQL to
rank/label source artifacts, so it is not a deployable retriever. Its purpose is
to distinguish "retrieval failed" from "the admitted artifact pool contains no
semantically reusable artifact at all." Only hashes and aggregate metrics are
written to the receipt.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any

from sqlglot import exp, parse_one

from defog_governed_sql_replay import (
    GovernanceAuthority,
    GovernedPostgresExecutor,
    PinnedTaskResolver,
    benchmark_results_equal,
    result_content_hash,
    sha256_text,
)


SCHEMA_VERSION = "frankengate-validated-artifact-pool-coverage-v1"
SOURCE_FILES = frozenset(
    {"data/instruct_basic_postgres.csv", "data/instruct_advanced_postgres.csv"}
)
TARGET_FILE = "data/questions_gen_postgres.csv"


def stable_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sql_surface(sql: str) -> tuple[frozenset[str], frozenset[str]]:
    try:
        tree = parse_one(sql, read="postgres")
    except Exception:
        return frozenset(), frozenset()
    tables = frozenset(str(item.name).strip('"').lower() for item in tree.find_all(exp.Table))
    columns = frozenset(str(item.name).strip('"').lower() for item in tree.find_all(exp.Column))
    return tables, columns


def jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    return len(left & right) / len(left | right) if left or right else 0.0


def run(
    *,
    source_root: Path,
    cohort_manifest: Path,
    dataset_manifest: Path,
    dsn_template: str,
    databases: tuple[str, ...],
    output: Path,
) -> dict[str, Any]:
    resolver = PinnedTaskResolver(
        source_root=source_root,
        manifest_path=cohort_manifest,
        dataset_manifest_path=dataset_manifest,
    )
    metadata = json.loads(cohort_manifest.read_text(encoding="utf-8"))["tasks"]
    targets = [
        resolver.resolve(row["task_id"])
        for row in metadata
        if row.get("db_name") in databases and row.get("source_file") == TARGET_FILE
    ]
    targets.sort(key=lambda task: task.task_id)
    if not targets:
        raise ValueError("no targets selected")
    authority = GovernanceAuthority(
        governance_scope="enterprise",
        authorization_epoch_ref="defog-artifact-pool-coverage-v1",
        user_id="artifact-pool-coverage-user",
        team_id="artifact-pool-coverage-team",
        virtual_key_id="artifact-pool-coverage-vk",
    )
    artifacts: list[dict[str, Any]] = []
    admission_failures: Counter[str] = Counter()
    for row in metadata:
        if row.get("db_name") not in databases or row.get("source_file") not in SOURCE_FILES:
            continue
        task = resolver.resolve(row["task_id"])
        executor = GovernedPostgresExecutor(
            dsn=dsn_template.format(database=task.database), authority=authority, audit_path=None
        )
        try:
            executor.execute_candidate(task.gold_sql)
        except Exception as exc:
            admission_failures[type(exc).__name__] += 1
            continue
        tables, columns = sql_surface(task.gold_sql)
        artifacts.append(
            {
                "source_id": task.task_id,
                "database": task.database,
                "task": task,
                "tables": tables,
                "columns": columns,
            }
        )
    if not artifacts:
        raise ValueError("no validated artifacts")

    gold_cache: dict[str, list[tuple[Any, Any]]] = {}
    execution_cache: dict[tuple[str, str], dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    aggregate: Counter[str] = Counter()
    for target in targets:
        target_tables, target_columns = sql_surface(target.gold_sql)
        same_scope = [candidate for candidate in artifacts if candidate["database"] == target.database]
        ranked = sorted(
            same_scope,
            key=lambda candidate: (
                jaccard(target_tables, candidate["tables"]),
                jaccard(target_columns, candidate["columns"]),
                candidate["source_id"],
            ),
            reverse=True,
        )
        if target.task_id not in gold_cache:
            evaluator = GovernedPostgresExecutor(
                dsn=dsn_template.format(database=target.database), authority=authority, audit_path=None
            )
            gold_cache[target.task_id] = evaluator.execute_gold_alternatives(target.gold_sql)
        semantic_matches: list[str] = []
        authorized_count = 0
        error_count = 0
        for candidate in same_scope:
            key = (target.task_id, candidate["source_id"])
            if key not in execution_cache:
                executor = GovernedPostgresExecutor(
                    dsn=dsn_template.format(database=target.database), authority=authority, audit_path=None
                )
                try:
                    validation, candidate_result = executor.execute_candidate(candidate["task"].gold_sql)
                    correct = any(
                        benchmark_results_equal(
                            candidate_result,
                            gold_result,
                            order_sensitive=any(
                                bool(select.args.get("order"))
                                for select in statement.find_all(exp.Select)
                            ),
                        )
                        for statement, gold_result in gold_cache[target.task_id]
                    )
                    execution_cache[key] = {
                        "authorized": True,
                        "correct": correct,
                        "result_sha256": result_content_hash(candidate_result),
                        "referenced_tables": len(validation.referenced_tables),
                    }
                except Exception as exc:  # classify every pool member
                    execution_cache[key] = {
                        "authorized": False,
                        "correct": False,
                        "result_sha256": None,
                        "error_class": type(exc).__name__,
                    }
            result = execution_cache[key]
            authorized_count += int(result["authorized"])
            error_count += int(not result["authorized"])
            if result["correct"]:
                semantic_matches.append(candidate["source_id"])

        top1 = ranked[0] if ranked else None
        top3 = ranked[:3]
        top1_correct = bool(top1 and top1["source_id"] in semantic_matches)
        top3_correct = any(candidate["source_id"] in semantic_matches for candidate in top3)
        aggregate["targets"] += 1
        aggregate["source_artifacts_checked"] += len(same_scope)
        aggregate["authorized_executions"] += authorized_count
        aggregate["execution_errors"] += error_count
        aggregate["targets_with_any_semantic_match"] += int(bool(semantic_matches))
        aggregate["oracle_structured_top1_semantic"] += int(top1_correct)
        aggregate["oracle_structured_top3_semantic"] += int(top3_correct)
        aggregate["semantic_match_artifacts"] += len(semantic_matches)
        rows.append(
            {
                "target_task_sha256": sha256_text(target.task_id),
                "database": target.database,
                "same_scope_artifact_count": len(same_scope),
                "authorized_executions": authorized_count,
                "execution_errors": error_count,
                "semantic_match_count": len(semantic_matches),
                "semantic_match_source_task_sha256": [sha256_text(item) for item in semantic_matches],
                "oracle_structured_top1_source_task_sha256": sha256_text(top1["source_id"]) if top1 else None,
                "oracle_structured_top1_semantic": top1_correct,
                "oracle_structured_top3_semantic": top3_correct,
                "max_table_jaccard": round(jaccard(target_tables, ranked[0]["tables"]), 8) if ranked else 0.0,
                "max_column_jaccard": round(jaccard(target_columns, ranked[0]["columns"]), 8) if ranked else 0.0,
            }
        )

    receipt = {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "cohort_manifest_sha256": sha256_bytes(cohort_manifest.read_bytes()),
            "dataset_manifest_sha256": sha256_bytes(dataset_manifest.read_bytes()),
            "source_root": "external-pinned-defog-checkout",
            "target_source_file": TARGET_FILE,
            "source_artifact_files": sorted(SOURCE_FILES),
            "databases": list(databases),
            "target_count": len(targets),
            "validated_artifact_count": len(artifacts),
            "source_validation_failures": dict(sorted(admission_failures.items())),
        },
        "evaluation": {
            "oracle_uses_target_gold_for_ranking": True,
            "all_same_scope_validated_artifacts_executed": True,
            "retrieval_deployable": False,
            "semantic_matching": "independent governed PostgreSQL result comparison",
        },
        "aggregate": dict(sorted(aggregate.items())),
        "rows": rows,
        "claim_boundary": {
            "pool_coverage_ceiling_measured": True,
            "retriever_quality_measured": False,
            "causal_agent_benefit_established": False,
            "enterprise_alias_truth_established": False,
            "reason": "Evaluation-only oracle coverage diagnostic; target gold is never available to a deployable retriever.",
        },
    }
    receipt["result_sha256"] = sha256_bytes(stable_json(receipt))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"aggregate": receipt["aggregate"], "result_sha256": receipt["result_sha256"]}, sort_keys=True))
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--cohort-manifest", type=Path, required=True)
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--dsn-template", required=True)
    parser.add_argument("--database", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(
        source_root=args.source_root.resolve(strict=True),
        cohort_manifest=args.cohort_manifest.resolve(strict=True),
        dataset_manifest=args.dataset_manifest.resolve(strict=True),
        dsn_template=args.dsn_template,
        databases=tuple(args.database),
        output=args.output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
