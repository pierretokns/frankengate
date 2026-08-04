#!/usr/bin/env python3
"""Evaluate train-only SQL-artifact retrieval on held-out public tasks.

This is deliberately separate from the frontier pilot.  It freezes a
deterministic lexical retriever over successful source SQL artifacts, retrieves
without target-task pairing, and executes the retrieved artifact under the
governed PostgreSQL executor.  The committed receipt contains hashes and
aggregate outcomes only; task text and SQL stay in the external source tree.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from sqlglot import exp

from defog_governed_sql_replay import (
    GovernanceAuthority,
    GovernedPostgresExecutor,
    PinnedTaskResolver,
    benchmark_results_equal,
    result_content_hash,
    sha256_text,
)


SCHEMA_VERSION = "frankengate-validated-artifact-retrieval-benchmark-v1"
TOKEN_RE = re.compile(r"[a-z][a-z0-9_]+")
STOPWORDS = frozenset(
    "a an and are as at by for from how in into is of on or per return the to what which with".split()
)
SOURCE_FILES = frozenset(
    {"data/instruct_basic_postgres.csv", "data/instruct_advanced_postgres.csv"}
)
TARGET_FILE = "data/questions_gen_postgres.csv"


def stable_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def tokens(text: str) -> frozenset[str]:
    return frozenset(token for token in TOKEN_RE.findall(text.lower()) if token not in STOPWORDS)


def similarity(query: frozenset[str], candidate: frozenset[str]) -> tuple[float, int, float]:
    if not query or not candidate:
        return (0.0, 0, 0.0)
    intersection = len(query & candidate)
    union = len(query | candidate)
    return (intersection / len(query), intersection, intersection / union)


def task_metadata(manifest_path: Path) -> dict[str, dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {str(row["task_id"]): row for row in manifest.get("tasks", [])}


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
    metadata = task_metadata(cohort_manifest)
    tasks = []
    for task_id, row in metadata.items():
        if row.get("db_name") not in databases:
            continue
        source_file = row.get("source_file")
        if source_file == TARGET_FILE:
            tasks.append((task_id, resolver.resolve(task_id), row))
    if not tasks:
        raise ValueError("no target tasks selected")

    authority = GovernanceAuthority(
        governance_scope="enterprise",
        authorization_epoch_ref="defog-factorial-authority-v1",
        user_id="artifact-retrieval-benchmark-user",
        team_id="artifact-retrieval-benchmark-team",
        virtual_key_id="artifact-retrieval-benchmark-vk",
    )
    artifacts_by_db: dict[str, list[tuple[str, Any, frozenset[str]]]] = {}
    source_validation_failures: Counter[str] = Counter()
    for task_id, row in metadata.items():
        if row.get("db_name") not in databases or row.get("source_file") not in SOURCE_FILES:
            continue
        task = resolver.resolve(task_id)
        source_executor = GovernedPostgresExecutor(
            dsn=dsn_template.format(database=task.database),
            authority=authority,
            audit_path=None,
        )
        try:
            source_executor.execute_candidate(task.gold_sql)
        except Exception as exc:  # only validated successful artifacts enter the pool
            source_validation_failures[type(exc).__name__] += 1
            continue
        artifacts_by_db.setdefault(task.database, []).append(
            (task_id, task, tokens(task.question))
        )
    for db in databases:
        if not artifacts_by_db.get(db):
            raise ValueError(f"no source artifacts for {db}")

    aggregate: Counter[str] = Counter()
    rows: list[dict[str, Any]] = []
    for task_id, target, _ in tasks:
        query_tokens = tokens(target.question)
        candidates = artifacts_by_db[target.database]
        source_id, source_task, source_tokens = max(
            candidates,
            key=lambda item: (similarity(query_tokens, item[2]), item[0]),
        )
        authority_for_task = authority
        executor = GovernedPostgresExecutor(
            dsn=dsn_template.format(database=target.database),
            authority=authority_for_task,
            audit_path=None,
        )
        record: dict[str, Any] = {
            "target_task_sha256": sha256_text(task_id),
            "source_task_sha256": sha256_text(source_id),
            "database": target.database,
            "retrieval": {
                "query_token_count": len(query_tokens),
                "source_token_count": len(source_tokens),
                "overlap": similarity(query_tokens, source_tokens)[1],
                "query_recall": similarity(query_tokens, source_tokens)[0],
                "jaccard": similarity(query_tokens, source_tokens)[2],
            },
            "source_artifact_sql_sha256": sha256_text(source_task.gold_sql),
            "semantic_correct": False,
            "security_authorized": False,
            "error_class": None,
            "policy_error_code": None,
        }
        try:
            validation, candidate_result = executor.execute_candidate(source_task.gold_sql)
            record["security_authorized"] = True
            gold_results = executor.execute_gold_alternatives(target.gold_sql)
            record["semantic_correct"] = any(
                benchmark_results_equal(
                    candidate_result,
                    gold_result,
                    order_sensitive=any(bool(select.args.get("order")) for select in statement.find_all(exp.Select)),
                )
                for statement, gold_result in gold_results
            )
            record["candidate_result_sha256"] = result_content_hash(candidate_result)
            record["referenced_tables"] = len(validation.referenced_tables)
            record["referenced_columns"] = len(validation.referenced_columns)
        except Exception as exc:  # noqa: BLE001 - receipt must classify every failure
            record["error_class"] = type(exc).__name__
            record["policy_error_code"] = getattr(exc, "code", None)
        aggregate["targets"] += 1
        aggregate["semantic_correct"] += int(record["semantic_correct"])
        aggregate["security_authorized"] += int(record["security_authorized"])
        aggregate["retrieval_executed"] += 1
        if record["error_class"]:
            aggregate["errors"] += 1
        rows.append(record)

    result = {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "cohort_manifest_sha256": sha256_bytes(cohort_manifest.read_bytes()),
            "dataset_manifest_sha256": sha256_bytes(dataset_manifest.read_bytes()),
            "source_root": "external-pinned-defog-checkout",
            "target_source_file": TARGET_FILE,
            "source_artifact_files": sorted(SOURCE_FILES),
            "databases": list(databases),
            "source_validation_failures": dict(sorted(source_validation_failures.items())),
            "validated_artifact_counts": {
                database: len(artifacts_by_db.get(database, ())) for database in databases
            },
        },
        "retrieval": {
            "method": "same-database lexical token overlap; target tasks excluded from artifact pool",
            "candidate_pool": "successful source SQL from instruct_basic and instruct_advanced",
            "target_task_pairing": False,
        },
        "aggregate": dict(sorted(aggregate.items())),
        "rows": rows,
        "claim_boundary": {
            "train_only_artifact_retrieval_tested": True,
            "causal_agent_benefit_established": False,
            "semantic_alias_truth_established": False,
            "reason": "This is a deterministic retrieval-plus-execution screen; no model regeneration control, SME labels, or changed-system replay is included.",
        },
    }
    result["result_sha256"] = sha256_bytes(stable_json(result))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--cohort-manifest", type=Path, required=True)
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--dsn-template", required=True)
    parser.add_argument("--database", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(
        source_root=args.source_root.resolve(strict=True),
        cohort_manifest=args.cohort_manifest.resolve(strict=True),
        dataset_manifest=args.dataset_manifest.resolve(strict=True),
        dsn_template=args.dsn_template,
        databases=tuple(args.database),
        output=args.output,
    )
    print(json.dumps(result["aggregate"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
