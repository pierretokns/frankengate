#!/usr/bin/env python3
"""Compare naive and replay-confirmed negatives for WMH-BIRD table ranking.

This is a public SQL proxy experiment.  A positive is a table referenced by
the recorded successful SQL.  The naive arm treats every exposed-but-unused
table as a negative.  The replay arm keeps only exposed tables whose
counterfactual substitution produces an execution error or result mismatch;
result-preserving substitutions are excluded as uncertain.  Both arms are
trained only on the training half of each database and evaluated on a held-out
half.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from sklearn.linear_model import LogisticRegression

from modern_term_acronym_port import STOP, stable_hash, termhood, tokens
from wmh_bird_exposure_counterfactual import (
    Trace,
    execute,
    file_hash,
    lexical_score,
    load_traces,
    ngrams,
    rank_metrics,
    substitute_table,
    table_tokens,
)


SCHEMA_VERSION = "frankengate-wmh-bird-replay-negative-reranker-v1"


def replay_negative_sets(trace: Trace, db_root: Path) -> tuple[str, set[str], set[str]]:
    """Return base status, replay-confirmed negatives, and uncertain candidates."""
    db_path = db_root / trace.db_name / f"{trace.db_name}.sqlite"
    base_status, base_rows = execute(db_path, trace.sql)
    if base_status != "ok":
        return base_status, set(), set(trace.exposed_tables - trace.used_tables)
    negatives: set[str] = set()
    uncertain: set[str] = set()
    for candidate in trace.exposed_tables - trace.used_tables:
        statuses: list[tuple[str, list[tuple[Any, ...]] | None]] = []
        for old in trace.used_tables:
            try:
                counterfactual = substitute_table(trace.sql, old, candidate)
            except Exception:
                statuses.append(("error", None))
                continue
            statuses.append(execute(db_path, counterfactual))
        if any(status != "ok" or rows != base_rows for status, rows in statuses):
            negatives.add(candidate)
        else:
            uncertain.add(candidate)
    return base_status, negatives, uncertain


def alias_mapping(train: list[Trace], limit: int = 3000) -> dict[tuple[str, str], set[str]]:
    admitted = {row["term_hash"] for row in termhood([item.prompt for item in train], [item.prompt for item in train], limit=limit)}
    mapping: dict[tuple[str, str], set[str]] = defaultdict(set)
    for item in train:
        for term_hash in ngrams(item.prompt):
            if term_hash in admitted:
                mapping[(item.db_name, term_hash)].update(item.used_tables & item.exposed_tables)
    return mapping


def feature_vector(trace: Trace, table: str, mapping: dict[tuple[str, str], set[str]]) -> list[float]:
    query = set(tokens(trace.prompt)) - STOP
    terms = table_tokens(table)
    aliases = set().union(*(mapping.get((trace.db_name, key), set()) for key in ngrams(trace.prompt)))
    return [
        lexical_score(trace.prompt, table),
        float(len(query & terms)),
        float(len(terms)),
        float(table.casefold() in query),
        float(table in aliases),
    ]


def aggregate(rows: list[dict[str, float]]) -> dict[str, Any]:
    if not rows:
        return {"cases": 0, "mrr": 0.0, "recall_at_1": 0.0, "recall_at_5": 0.0, "recall_at_10": 0.0}
    return {
        "cases": len(rows),
        "mrr": round(sum(item["mrr"] for item in rows) / len(rows), 6),
        "recall_at_1": round(sum(item["recall_at_1"] for item in rows) / len(rows), 6),
        "recall_at_5": round(sum(item["recall_at_5"] for item in rows) / len(rows), 6),
        "recall_at_10": round(sum(item["recall_at_10"] for item in rows) / len(rows), 6),
    }


def run(traces_path: Path, manifest: Path, db_root: Path, output: Path, limit: int = 3000) -> dict[str, Any]:
    traces = load_traces(traces_path, manifest)
    by_db: dict[str, list[Trace]] = defaultdict(list)
    for item in traces:
        if item.used_tables & item.exposed_tables:
            by_db[item.db_name].append(item)

    arms: dict[str, list[dict[str, float]]] = defaultdict(list)
    fold_summaries: list[dict[str, Any]] = []
    replay_status_counts: Counter[str] = Counter()
    for db in sorted(by_db):
        ordered = sorted(by_db[db], key=lambda item: stable_hash(item.base_task_id))
        train, evaluation = ordered[::2], ordered[1::2]
        mapping = alias_mapping(train, limit=limit)
        naive_x: list[list[float]] = []
        naive_y: list[int] = []
        replay_x: list[list[float]] = []
        replay_y: list[int] = []
        replay_negative_count = 0
        uncertain_count = 0
        for item in train:
            candidates = item.exposed_tables & item.used_tables
            for table in sorted(item.exposed_tables):
                value = feature_vector(item, table, mapping)
                label = int(table in candidates)
                naive_x.append(value)
                naive_y.append(label)
            status, negatives, uncertain = replay_negative_sets(item, db_root)
            replay_status_counts[status] += 1
            replay_negative_count += len(negatives)
            uncertain_count += len(uncertain)
            for table in sorted(candidates | negatives):
                replay_x.append(feature_vector(item, table, mapping))
                replay_y.append(int(table in candidates))

        naive_model = LogisticRegression(max_iter=1000, solver="liblinear", random_state=0).fit(naive_x, naive_y)
        replay_model = LogisticRegression(max_iter=1000, solver="liblinear", random_state=0).fit(replay_x, replay_y)
        for item in evaluation:
            pool = sorted(item.exposed_tables)
            targets = frozenset(item.used_tables & item.exposed_tables)
            if not pool or not targets:
                continue
            lexical = sorted(pool, key=lambda table: (-lexical_score(item.prompt, table), table))
            aliases = set().union(*(mapping.get((db, key), set()) for key in ngrams(item.prompt)))
            termhood_order = sorted(pool, key=lambda table: (-lexical_score(item.prompt, table) - (20.0 if table in aliases else 0.0), table))
            naive_order = [table for _, table in sorted(((float(naive_model.predict_proba([feature_vector(item, table, mapping)])[0, 1]), table) for table in pool), key=lambda pair: (-pair[0], pair[1]))]
            replay_order = [table for _, table in sorted(((float(replay_model.predict_proba([feature_vector(item, table, mapping)])[0, 1]), table) for table in pool), key=lambda pair: (-pair[0], pair[1]))]
            for arm, order in (("lexical", lexical), ("termhood_alias", termhood_order), ("naive_exposed_negative_ranker", naive_order), ("replay_negative_ranker", replay_order)):
                arms[arm].append(rank_metrics(order, targets))
        fold_summaries.append({"db_name": db, "train_tasks": len(train), "evaluation_tasks": len(evaluation), "replay_negative_training_examples": replay_negative_count, "uncertain_training_candidates": uncertain_count, "mapped_terms": len(mapping)})

    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source": {"traces_sha256": file_hash(traces_path), "manifest_sha256": file_hash(manifest), "raw_content_committed": False, "sqlite_root": "external-pinned-bird-minidev"},
        "cohort": {"selection": "one deterministic reward=1 trace per base task", "tasks": len(traces), "database_families": len(by_db), "split": "within-database deterministic odd/even task split"},
        "replay_status_counts": dict(sorted(replay_status_counts.items())),
        "folds": fold_summaries,
        "arms": {arm: aggregate(values) for arm, values in sorted(arms.items())},
        "claim_boundary": {"replay_negative_training_evaluated": True, "semantic_negative_labels_established": False, "enterprise_quality_established": False, "embedding_promotion_authorized": False, "reason": "The positive target is a recorded SQL table reference and the evaluation is a public BIRD proxy. Replay-confirmed negatives measure incompatibility under the recorded query, not semantic intent or enterprise alias truth."},
    }
    result["result_sha256"] = stable_hash(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["arms"], sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--traces", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--db-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=3000)
    args = parser.parse_args()
    run(args.traces, args.manifest, args.db_root, args.output, limit=args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
