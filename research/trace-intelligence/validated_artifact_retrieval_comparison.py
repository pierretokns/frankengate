#!/usr/bin/env python3
"""Compare train-only validated SQL-artifact retrieval families.

The source artifact library is admitted only after governed execution.  Target
questions are never used to construct the library.  Receipts contain hashes and
aggregates only; raw questions, SQL, and rows remain outside the repository.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable

from sqlglot import exp

from sqlglot import exp

from defog_governed_sql_replay import (
    GovernanceAuthority,
    GovernedPostgresExecutor,
    PinnedTaskResolver,
    benchmark_results_equal,
    result_content_hash,
    sha256_text,
)
from nl2sql_real_alias_benchmark import cosine, post_embed, stable_hash


SCHEMA_VERSION = "frankengate-validated-artifact-retrieval-comparison-v1"
SOURCE_FILES = frozenset({"data/instruct_basic_postgres.csv", "data/instruct_advanced_postgres.csv"})
TARGET_FILE = "data/questions_gen_postgres.csv"
STOPWORDS = frozenset(
    "a an and are as at by for from how in into is of on or per return the to what which with".split()
)
TOKEN_RE = re.compile(r"[a-z][a-z0-9_]+")
SQL_WORDS = frozenset(
    "select from where join left right inner outer full on and or as group by order having limit offset with union all distinct case when then else end asc desc null is not in exists between like ilike true false count sum avg min max coalesce date interval current over partition row_number dense_rank rank".split()
)


def stable_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def tokens(text: str) -> frozenset[str]:
    return frozenset(token for token in TOKEN_RE.findall(text.lower()) if token not in STOPWORDS)


def sql_identifiers(sql: str) -> frozenset[str]:
    return frozenset(token for token in TOKEN_RE.findall(sql.lower()) if token not in SQL_WORDS and len(token) > 2)


def similarity(query: frozenset[str], candidate: frozenset[str]) -> tuple[float, int, float]:
    if not query or not candidate:
        return (0.0, 0, 0.0)
    intersection = len(query & candidate)
    return intersection / len(query), intersection, intersection / len(query | candidate)


def task_metadata(manifest_path: Path) -> dict[str, dict[str, Any]]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {str(row["task_id"]): row for row in manifest.get("tasks", [])}


def rrf_order(scores: dict[str, float]) -> list[str]:
    return [key for key, _ in sorted(scores.items(), key=lambda item: (-item[1], item[0]))]


def rank_candidates(
    *,
    target_question: str,
    target_database: str,
    candidates: list[dict[str, Any]],
    target_vector: list[float],
    source_vectors: dict[str, list[float]],
    scope_filtered: bool,
) -> dict[str, list[dict[str, Any]]]:
    pool = [candidate for candidate in candidates if not scope_filtered or candidate["database"] == target_database]
    query_tokens = tokens(target_question)
    lexical: dict[str, float] = {}
    dense: dict[str, float] = {}
    identifier: dict[str, float] = {}
    for candidate in pool:
        key = candidate["source_id"]
        lexical[key] = similarity(query_tokens, candidate["question_tokens"])[0]
        dense[key] = cosine(target_vector, source_vectors[key])
        identifier[key] = similarity(query_tokens, candidate["identifier_tokens"])[0]

    def ordered(scores: dict[str, float]) -> list[dict[str, Any]]:
        return [next(candidate for candidate in pool if candidate["source_id"] == key) for key in rrf_order(scores)]

    lexical_order = ordered(lexical)
    dense_order = ordered(dense)
    identifier_order = ordered(identifier)
    lexical_rank = {key: index for index, key in enumerate(lexical, 1)}
    dense_rank = {key: index for index, key in enumerate(dense, 1)}
    hybrid_scores = {
        key: 1.0 / (60 + lexical_rank[key]) + 1.0 / (60 + dense_rank[key])
        for key in lexical
    }
    gate = [
        candidate
        for candidate in identifier_order
        if identifier[candidate["source_id"]] > 0
    ]
    return {
        "lexical": lexical_order,
        "dense": dense_order,
        "identifier": identifier_order,
        "hybrid": ordered(hybrid_scores),
        "identifier_gate": gate,
    }


def run(
    *,
    source_root: Path,
    cohort_manifest: Path,
    dataset_manifest: Path,
    dsn_template: str,
    databases: tuple[str, ...],
    output: Path,
    endpoint: str,
) -> dict[str, Any]:
    resolver = PinnedTaskResolver(
        source_root=source_root,
        manifest_path=cohort_manifest,
        dataset_manifest_path=dataset_manifest,
    )
    metadata = task_metadata(cohort_manifest)
    target_rows = [
        (task_id, resolver.resolve(task_id), row)
        for task_id, row in metadata.items()
        if row.get("db_name") in databases and row.get("source_file") == TARGET_FILE
    ]
    if not target_rows:
        raise ValueError("no target tasks selected")

    authority = GovernanceAuthority(
        governance_scope="enterprise",
        authorization_epoch_ref="defog-factorial-authority-v1",
        user_id="artifact-retrieval-comparison-user",
        team_id="artifact-retrieval-comparison-team",
        virtual_key_id="artifact-retrieval-comparison-vk",
    )
    candidates: list[dict[str, Any]] = []
    admission_failures: Counter[str] = Counter()
    for source_id, row in metadata.items():
        if row.get("db_name") not in databases or row.get("source_file") not in SOURCE_FILES:
            continue
        source_task = resolver.resolve(source_id)
        executor = GovernedPostgresExecutor(dsn=dsn_template.format(database=source_task.database), authority=authority, audit_path=None)
        try:
            executor.execute_candidate(source_task.gold_sql)
        except Exception as exc:  # only governed-success artifacts enter pool
            admission_failures[type(exc).__name__] += 1
            continue
        candidates.append(
            {
                "source_id": source_id,
                "database": source_task.database,
                "question_tokens": tokens(source_task.question),
                "identifier_tokens": sql_identifiers(source_task.gold_sql),
                "sql_sha256": sha256_text(source_task.gold_sql),
                "question_sha256": sha256_text(source_task.question),
                "task": source_task,
            }
        )
    if not candidates:
        raise ValueError("no validated source artifacts")

    target_questions = [target.question for _, target, _ in target_rows]
    source_questions = [candidate["task"].question for candidate in candidates]
    vectors = post_embed(endpoint, target_questions + source_questions)
    target_vectors = vectors[: len(target_rows)]
    source_vectors = {
        candidate["source_id"]: vector
        for candidate, vector in zip(candidates, vectors[len(target_rows) :])
    }

    arms = ("lexical", "dense", "identifier", "hybrid", "identifier_gate")
    modes = ("scope_filtered", "pooled")
    aggregate: dict[str, dict[str, Counter[str]]] = {
        mode: {arm: Counter() for arm in arms} for mode in modes
    }
    rows: list[dict[str, Any]] = []
    execution_cache: dict[tuple[str, str], tuple[bool, bool, str | None]] = {}
    gold_cache: dict[str, list[Any]] = {}

    for index, (target_id, target, metadata_row) in enumerate(target_rows):
        for mode in modes:
            ranked = rank_candidates(
                target_question=target.question,
                target_database=target.database,
                candidates=candidates,
                target_vector=target_vectors[index],
                source_vectors=source_vectors,
                scope_filtered=mode == "scope_filtered",
            )
            for arm in arms:
                selected = ranked[arm]
                arm_key = f"{mode}:{arm}"
                summary: dict[str, Any] = {
                    "target_task_sha256": sha256_text(target_id),
                    "mode": mode,
                    "arm": arm,
                    "selected_count": len(selected),
                    "scope_correct_top1": False,
                    "top1_semantic": False,
                    "top3_semantic": False,
                    "top3_executed": 0,
                    "top3_authorized": 0,
                    "top3_errors": 0,
                    "abstained": not bool(selected),
                }
                if selected:
                    summary["scope_correct_top1"] = selected[0]["database"] == target.database
                    if target_id not in gold_cache:
                        gold_executor = GovernedPostgresExecutor(dsn=dsn_template.format(database=target.database), authority=authority, audit_path=None)
                        gold_cache[target_id] = gold_executor.execute_gold_alternatives(target.gold_sql)
                    first_semantic = False
                    for candidate_index, candidate in enumerate(selected[:3]):
                        if candidate["database"] != target.database:
                            continue
                        cache_key = (target_id, candidate["source_id"])
                        if cache_key not in execution_cache:
                            executor = GovernedPostgresExecutor(dsn=dsn_template.format(database=target.database), authority=authority, audit_path=None)
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
                                    for statement, gold_result in gold_cache[target_id]
                                )
                                execution_cache[cache_key] = (True, correct, result_content_hash(candidate_result))
                            except Exception as exc:  # classify every candidate
                                execution_cache[cache_key] = (False, False, type(exc).__name__)
                        authorized, correct, marker = execution_cache[cache_key]
                        summary["top3_executed"] += 1
                        summary["top3_authorized"] += int(authorized)
                        summary["top3_semantic"] = summary["top3_semantic"] or correct
                        if candidate_index == 0:
                            first_semantic = correct
                        summary["top3_errors"] += int(not authorized)
                    summary["top1_semantic"] = first_semantic and selected[0]["database"] == target.database
                for metric in ("scope_correct_top1", "top1_semantic", "top3_semantic", "abstained"):
                    aggregate[mode][arm][metric] += int(summary[metric])
                aggregate[mode][arm]["targets"] += 1
                aggregate[mode][arm]["top3_executed"] += summary["top3_executed"]
                aggregate[mode][arm]["top3_authorized"] += summary["top3_authorized"]
                aggregate[mode][arm]["top3_errors"] += summary["top3_errors"]
                rows.append(summary)

    receipt = {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "cohort_manifest_sha256": sha256_bytes(cohort_manifest.read_bytes()),
            "dataset_manifest_sha256": sha256_bytes(dataset_manifest.read_bytes()),
            "databases": list(databases),
            "target_source_file": TARGET_FILE,
            "source_artifact_files": sorted(SOURCE_FILES),
            "target_count": len(target_rows),
            "synthetic_nil_count": 0,
            "validated_artifact_count": len(candidates),
            "source_validation_failures": dict(sorted(admission_failures.items())),
            "raw_content_committed": False,
        },
        "retrieval": {
            "methods": list(arms),
            "modes": list(modes),
            "embedding_model": "nomic-embed-text:latest",
            "target_task_pairing": False,
            "top_k_execution": 3,
        },
        "aggregate": {
            mode: {arm: dict(sorted(values.items())) for arm, values in arm_map.items()}
            for mode, arm_map in aggregate.items()
        },
        "rows": rows,
        "claim_boundary": {
            "train_only_artifact_retrieval_tested": True,
            "governed_top3_execution_tested": True,
            "causal_agent_benefit_established": False,
            "semantic_alias_truth_established": False,
            "reason": "Retrieval-plus-governed-execution diagnostic; no regeneration control, SME labels, changed-system replay, or NIL labels are included.",
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
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    args = parser.parse_args()
    run(
        source_root=args.source_root.resolve(strict=True),
        cohort_manifest=args.cohort_manifest.resolve(strict=True),
        dataset_manifest=args.dataset_manifest.resolve(strict=True),
        dsn_template=args.dsn_template,
        databases=tuple(args.database),
        output=args.output,
        endpoint=args.endpoint,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
