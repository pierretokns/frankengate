#!/usr/bin/env python3
"""Compare lexical, identifier, and precomputed dense retrieval on BIRD traces.

This is an outcome-backed *candidate retrieval* study over the validated
artifacts from ``bird_trace_artifact_reuse.py``.  A candidate is useful only if
executing its recorded SQL returns the target's independently executed gold
result.  The metric is intentionally a proxy: equal result sets can collide,
and no human intent labels exist in the public corpus.

The World Model Harness ships a pinned ``state_action`` embedding matrix for
the trace steps.  It is used only to rank candidates; it is never treated as
authority, a correctness judge, or a skill-release signal.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from sqlglot import exp, parse_one

from bird_trace_artifact_reuse import (
    Artifact,
    execute,
    extract_sql,
    load_tasks,
    question_tokens,
    sql_template,
)


SCHEMA_VERSION = "frankengate-bird-trace-retrieval-cascade-v1"
IDENTIFIER_RE = re.compile(r"[a-z][a-z0-9_]+")
SQL_STOPWORDS = frozenset(
    "select from where join on as and or not null is by group order having limit offset distinct case when then else end asc desc inner left right outer cross union all exists in like between over partition rows range preceding following with true false count sum avg min max cast coalesce"
    .split()
)


def stable_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def identifiers(sql: str) -> frozenset[str]:
    try:
        parsed = parse_one(sql, read="sqlite")
        values: set[str] = set()
        for node in parsed.walk():
            if isinstance(node, exp.Table):
                values.add(node.name.lower())
            elif isinstance(node, exp.Column):
                values.add(node.name.lower())
        return frozenset(values)
    except Exception:
        return frozenset(t for t in IDENTIFIER_RE.findall(sql.lower()) if t not in SQL_STOPWORDS)


def jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def cosine(left: np.ndarray, right: np.ndarray) -> float:
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    return float(np.dot(left, right) / denominator) if denominator else 0.0


def trace_step_indices(harness_root: Path) -> tuple[dict[str, int], int]:
    path = harness_root / "packages/environment-capture/bird-sql/models/bird-sql/index/steps.jsonl"
    indices: dict[str, int] = {}
    count = 0
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines()):
        count += 1
        row = json.loads(line)
        sql = extract_sql(row["action"].get("arguments", {}).get("command", ""))
        if sql and not row["observation"].get("is_error"):
            indices[row["task"].strip()] = index
    return indices, count


def validated_artifacts(harness_root: Path) -> list[tuple[Artifact, int]]:
    tasks = load_tasks(harness_root)
    sql_candidates = {}
    steps = harness_root / "packages/environment-capture/bird-sql/models/bird-sql/index/steps.jsonl"
    for index, line in enumerate(steps.read_text(encoding="utf-8").splitlines()):
        row = json.loads(line)
        prompt = row["task"].strip()
        sql = extract_sql(row["action"].get("arguments", {}).get("command", ""))
        if prompt in tasks and sql and not row["observation"].get("is_error"):
            sql_candidates[prompt] = (sql, index)
    artifacts: list[tuple[Artifact, int]] = []
    for prompt, (sql, index) in sql_candidates.items():
        task = tasks[prompt]
        trace_result = execute(task.db_path, sql)
        gold_result = execute(task.db_path, task.gold_sql)
        if trace_result is None or gold_result is None or trace_result != gold_result:
            continue
        try:
            template, literals = sql_template(sql)
        except Exception:
            continue
        artifacts.append(
            (
                Artifact(
                    task=task,
                    sql=sql,
                    result=trace_result,
                    template=template,
                    literals=tuple(literals),
                    tokens=question_tokens(task.prompt),
                ),
                index,
            )
        )
    return artifacts


def rank(target: Artifact, target_embedding: np.ndarray, candidates: list[tuple[Artifact, np.ndarray]], arm: str) -> list[Artifact]:
    scored: list[tuple[float, float, str, Artifact]] = []
    target_ids = identifiers(target.sql)
    for candidate, embedding in candidates:
        if arm == "lexical":
            primary = len(target.tokens & candidate.tokens) / (len(target.tokens) or 1)
            secondary = jaccard(target_ids, identifiers(candidate.sql))
        elif arm == "identifier":
            primary = jaccard(target_ids, identifiers(candidate.sql))
            secondary = len(target.tokens & candidate.tokens) / (len(target.tokens) or 1)
        elif arm == "dense":
            primary = cosine(target_embedding, embedding)
            secondary = jaccard(target_ids, identifiers(candidate.sql))
        elif arm == "hybrid":
            lexical = len(target.tokens & candidate.tokens) / (len(target.tokens) or 1)
            ident = jaccard(target_ids, identifiers(candidate.sql))
            primary = 0.45 * lexical + 0.55 * ident
            secondary = cosine(target_embedding, embedding)
        else:
            raise ValueError(f"unknown arm: {arm}")
        scored.append((primary, secondary, candidate.task.task_id, candidate))
    scored.sort(key=lambda item: (-item[0], -item[1], item[2]))
    return [item[3] for item in scored]


def summarize_targets(targets: list[Artifact], candidate_map: dict[str, list[tuple[Artifact, np.ndarray]]], embeddings: np.ndarray, index_map: dict[str, int]) -> dict[str, Any]:
    arms = ("lexical", "identifier", "dense", "hybrid")
    aggregate: dict[str, Counter[str]] = {arm: Counter() for arm in arms}
    for target in targets:
        pool = candidate_map[target.task.database]
        pool = [(artifact, vector) for artifact, vector in pool if artifact.task.task_id != target.task.task_id]
        if not pool:
            continue
        target_vector = embeddings[index_map[target.task.task_id]]
        for arm in arms:
            ranked = rank(target, target_vector, pool, arm)
            aggregate[arm]["targets"] += 1
            for k in (1, 5, 10):
                aggregate[arm][f"result_match_at_{k}"] += int(
                    any(execute(target.task.db_path, candidate.sql) == target.result for candidate in ranked[:k])
                )
            aggregate[arm]["same_template_at_1"] += int(ranked[0].template == target.template)
            aggregate[arm]["same_template_at_5"] += int(any(candidate.template == target.template for candidate in ranked[:5]))
    return {arm: dict(sorted(values.items())) for arm, values in aggregate.items()}


def run(harness_root: Path, output: Path) -> dict[str, Any]:
    harness_root = harness_root.resolve()
    artifacts_with_indices = validated_artifacts(harness_root)
    artifacts = [item[0] for item in artifacts_with_indices]
    index_map = {artifact.task.task_id: index for artifact, index in artifacts_with_indices}
    embedding_path = harness_root / "packages/environment-capture/bird-sql/models/bird-sql/index/embeddings.npy"
    embeddings = np.load(embedding_path)
    steps_path = harness_root / "packages/environment-capture/bird-sql/models/bird-sql/index/steps.jsonl"
    step_count = len(steps_path.read_text(encoding="utf-8").splitlines())
    if embeddings.shape[0] != step_count:
        raise ValueError("embedding and step row counts differ")
    if any(index >= embeddings.shape[0] for index in index_map.values()):
        raise ValueError("artifact step index exceeds embedding matrix")

    by_db: defaultdict[str, list[tuple[Artifact, np.ndarray]]] = defaultdict(list)
    for artifact in artifacts:
        by_db[artifact.task.database].append((artifact, embeddings[index_map[artifact.task.task_id]]))
    aggregate = summarize_targets(artifacts, by_db, embeddings, index_map)
    receipt: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "harness_root": "world-model-harness-v0.2.2",
            "trace_index_sha256": sha256_file(steps_path),
            "embedding_index_sha256": sha256_file(embedding_path),
            "embedding_key_mode": "state_action",
            "embedding_dimension": int(embeddings.shape[1]),
            "raw_content_committed": False,
        },
        "cohort": {
            "validated_artifacts": len(artifacts),
            "database_families": len(by_db),
            "candidate_scope": "same database family; leave-one-out",
        },
        "aggregate": aggregate,
        "claim_boundary": {
            "outcome_backed_candidate_retrieval_measured": True,
            "dense_authority_established": False,
            "human_intent_quality_established": False,
            "enterprise_quality_established": False,
            "skill_release_authorized": False,
            "reason": "Public BIRD traces provide gold execution outcomes but no natural intent labels, enterprise identities, or prospective utility outcomes; result-set matches can collide.",
        },
    }
    receipt["result_sha256"] = hashlib.sha256(stable_json(receipt)).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"aggregate": aggregate, "result_sha256": receipt["result_sha256"]}, sort_keys=True))
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--harness-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.harness_root, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
