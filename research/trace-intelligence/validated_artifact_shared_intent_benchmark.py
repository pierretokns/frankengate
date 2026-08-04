#!/usr/bin/env python3
"""Controlled shared-intent retrieval benchmark for validated SQL artifacts.

Each target is a deterministic, prompt-only paraphrase of a validated source
task.  The source artifact is therefore known to be semantically reusable; the
benchmark measures retrieval recovery rather than discovering whether the
library contains a matching task.  Raw questions/SQL remain external and the
receipt contains hashes and aggregate metrics only.
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
from nl2sql_real_alias_benchmark import cosine, post_embed


SCHEMA_VERSION = "frankengate-validated-artifact-shared-intent-v1"
SOURCE_FILES = frozenset({"data/instruct_basic_postgres.csv"})
TARGET_FILE = "controlled-paraphrase-of-source"
STOPWORDS = frozenset("a an and are as at by for from how in into is of on or per return the to what which with".split())
TOKEN_RE = re.compile(r"[a-z][a-z0-9_]+")
SQL_WORDS = frozenset("select from where join left right inner outer full on and or as group by order having limit offset with union all distinct case when then else end asc desc null is not in exists between like ilike true false count sum avg min max coalesce date interval current over partition row_number dense_rank rank".split())


def stable_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def tokens(text: str) -> frozenset[str]:
    return frozenset(token for token in TOKEN_RE.findall(text.lower()) if token not in STOPWORDS)


def sql_identifiers(sql: str) -> frozenset[str]:
    return frozenset(token for token in TOKEN_RE.findall(sql.lower()) if token not in SQL_WORDS and len(token) > 2)


def similarity(query: frozenset[str], candidate: frozenset[str]) -> float:
    return len(query & candidate) / len(query) if query else 0.0


def controlled_paraphrase(question: str, index: int) -> str:
    """Apply a fixed prompt-only rewrite; SQL/intent remain source-pinned."""
    prefixes = (
        "Please answer this business question precisely: ",
        "For an analytics request, return the requested result for: ",
        "A user is asking the following database question: ",
        "Provide the SQL answer to this request: ",
    )
    value = question.strip()
    if value.endswith("?"):
        value = value[:-1]
    return prefixes[index % len(prefixes)] + value + "."


def rank_candidates(target_question: str, target_vector: list[float], candidates: list[dict[str, Any]], source_vectors: dict[str, list[float]]) -> dict[str, list[dict[str, Any]]]:
    query_tokens = tokens(target_question)
    lexical: dict[str, float] = {}
    dense: dict[str, float] = {}
    identifier: dict[str, float] = {}
    for candidate in candidates:
        key = candidate["source_id"]
        lexical[key] = similarity(query_tokens, candidate["question_tokens"])
        dense[key] = cosine(target_vector, source_vectors[key])
        identifier[key] = similarity(query_tokens, candidate["identifier_tokens"])

    def order(scores: dict[str, float]) -> list[dict[str, Any]]:
        return [candidate for candidate in sorted(candidates, key=lambda c: (-scores[c["source_id"]], c["source_id"]))]

    lexical_order = order(lexical)
    dense_order = order(dense)
    identifier_order = order(identifier)
    lexical_rank = {c["source_id"]: i for i, c in enumerate(lexical_order, 1)}
    dense_rank = {c["source_id"]: i for i, c in enumerate(dense_order, 1)}
    hybrid = {
        key: 1.0 / (60 + lexical_rank[key]) + 1.0 / (60 + dense_rank[key])
        for key in lexical
    }
    return {
        "lexical": lexical_order,
        "dense": dense_order,
        "identifier": identifier_order,
        "hybrid": order(hybrid),
    }


def run(*, source_root: Path, cohort_manifest: Path, dataset_manifest: Path, dsn_template: str, databases: tuple[str, ...], output: Path, endpoint: str) -> dict[str, Any]:
    resolver = PinnedTaskResolver(source_root=source_root, manifest_path=cohort_manifest, dataset_manifest_path=dataset_manifest)
    metadata = json.loads(cohort_manifest.read_text(encoding="utf-8"))["tasks"]
    source_tasks = [
        resolver.resolve(row["task_id"])
        for row in metadata
        if row.get("db_name") in databases and row.get("source_file") in SOURCE_FILES
    ]
    source_tasks.sort(key=lambda task: task.task_id)
    if not source_tasks:
        raise ValueError("no controlled source tasks selected")
    authority = GovernanceAuthority(
        governance_scope="enterprise",
        authorization_epoch_ref="defog-shared-intent-authority-v1",
        user_id="shared-intent-benchmark-user",
        team_id="shared-intent-benchmark-team",
        virtual_key_id="shared-intent-benchmark-vk",
    )
    candidates: list[dict[str, Any]] = []
    failures: Counter[str] = Counter()
    for task in source_tasks:
        executor = GovernedPostgresExecutor(dsn=dsn_template.format(database=task.database), authority=authority, audit_path=None)
        try:
            executor.execute_candidate(task.gold_sql)
        except Exception as exc:
            failures[type(exc).__name__] += 1
            continue
        candidates.append({
            "source_id": task.task_id,
            "database": task.database,
            "question_tokens": tokens(task.question),
            "identifier_tokens": sql_identifiers(task.gold_sql),
            "question_sha256": sha256_text(task.question),
            "sql_sha256": sha256_text(task.gold_sql),
            "task": task,
        })
    if not candidates:
        raise ValueError("no governed source artifacts")

    targets = []
    for index, candidate in enumerate(candidates):
        task = candidate["task"]
        targets.append({
            "target_id": f"controlled:{index}:{sha256_text(task.task_id)[:16]}",
            "source_id": candidate["source_id"],
            "database": candidate["database"],
            "question": controlled_paraphrase(task.question, index),
            "question_sha256": sha256_text(controlled_paraphrase(task.question, index)),
            "gold_sql": task.gold_sql,
        })
    vectors = post_embed(endpoint, [target["question"] for target in targets] + [c["task"].question for c in candidates])
    target_vectors = vectors[: len(targets)]
    source_vectors = {candidate["source_id"]: vector for candidate, vector in zip(candidates, vectors[len(targets):])}
    gold_cache: dict[str, list[Any]] = {}
    execution_cache: dict[tuple[str, str], tuple[bool, bool, str | None]] = {}
    arms = ("lexical", "dense", "identifier", "hybrid")
    aggregate: dict[str, Counter[str]] = {arm: Counter() for arm in arms}
    rows: list[dict[str, Any]] = []
    for index, target in enumerate(targets):
        pool = [candidate for candidate in candidates if candidate["database"] == target["database"]]
        ranked = rank_candidates(target["question"], target_vectors[index], pool, source_vectors)
        if target["target_id"] not in gold_cache:
            evaluator = GovernedPostgresExecutor(dsn=dsn_template.format(database=target["database"]), authority=authority, audit_path=None)
            gold_cache[target["target_id"]] = evaluator.execute_gold_alternatives(target["gold_sql"])
        for arm in arms:
            selected = ranked[arm]
            row = {
                "target_id_sha256": sha256_text(target["target_id"]),
                "source_id_sha256": sha256_text(target["source_id"]),
                "arm": arm,
                "scope_correct_top1": bool(selected and selected[0]["database"] == target["database"]),
                "known_source_top1": bool(selected and selected[0]["source_id"] == target["source_id"]),
                "known_source_top3": any(c["source_id"] == target["source_id"] for c in selected[:3]),
                "top1_semantic": False,
                "top3_semantic": False,
                "top3_executed": 0,
                "top3_authorized": 0,
                "top3_errors": 0,
            }
            for candidate in selected[:3]:
                if candidate["database"] != target["database"]:
                    continue
                key = (target["target_id"], candidate["source_id"])
                if key not in execution_cache:
                    executor = GovernedPostgresExecutor(dsn=dsn_template.format(database=target["database"]), authority=authority, audit_path=None)
                    try:
                        _, result = executor.execute_candidate(candidate["task"].gold_sql)
                        correct = any(
                            benchmark_results_equal(
                                result,
                                gold_result,
                                order_sensitive=any(bool(select.args.get("order")) for select in statement.find_all(exp.Select)),
                            )
                            for statement, gold_result in gold_cache[target["target_id"]]
                        )
                        execution_cache[key] = (True, correct, result_content_hash(result))
                    except Exception as exc:
                        execution_cache[key] = (False, False, type(exc).__name__)
                authorized, correct, marker = execution_cache[key]
                row["top3_executed"] += 1
                row["top3_authorized"] += int(authorized)
                row["top3_errors"] += int(not authorized)
                row["top3_semantic"] = row["top3_semantic"] or correct
                if candidate is selected[0]:
                    row["top1_semantic"] = correct
            for metric in ("scope_correct_top1", "known_source_top1", "known_source_top3", "top1_semantic", "top3_semantic"):
                aggregate[arm][metric] += int(row[metric])
            aggregate[arm]["targets"] += 1
            aggregate[arm]["top3_executed"] += row["top3_executed"]
            aggregate[arm]["top3_authorized"] += row["top3_authorized"]
            aggregate[arm]["top3_errors"] += row["top3_errors"]
            rows.append(row)
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "cohort_manifest_sha256": sha256_bytes(cohort_manifest.read_bytes()),
            "dataset_manifest_sha256": sha256_bytes(dataset_manifest.read_bytes()),
            "databases": list(databases),
            "source_file": sorted(SOURCE_FILES),
            "source_task_count": len(source_tasks),
            "validated_artifact_count": len(candidates),
            "validation_failures": dict(sorted(failures.items())),
            "raw_content_committed": False,
        },
        "target": {
            "target_count": len(targets),
            "construction": "deterministic prompt-only paraphrase of each validated source question",
            "known_shared_intent": True,
            "target_gold_sql_is_source_sql": True,
        },
        "retrieval": {"arms": list(arms), "embedding_model": "nomic-embed-text:latest", "scope_filter": True, "top_k_execution": 3},
        "aggregate": {arm: dict(sorted(values.items())) for arm, values in aggregate.items()},
        "rows": rows,
        "claim_boundary": {
            "known_shared_intent_recovery_measured": True,
            "causal_agent_benefit_established": False,
            "natural_enterprise_paraphrase_quality_established": False,
            "reason": "Controlled upper-bound retrieval diagnostic; target intent is inherited from the source SQL and no regeneration or human relevance labels are included.",
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
    run(source_root=args.source_root.resolve(strict=True), cohort_manifest=args.cohort_manifest.resolve(strict=True), dataset_manifest=args.dataset_manifest.resolve(strict=True), dsn_template=args.dsn_template, databases=tuple(args.database), output=args.output, endpoint=args.endpoint)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
