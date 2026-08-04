#!/usr/bin/env python3
"""Measure exact-target versus replay-equivalent artifact retrieval.

The ordinary BIRD retrieval score treats only the recorded SQL table set as a
positive.  This probe adds a second, explicitly weaker target set: exposed
tables whose deterministic substitution preserves the recorded result.  Such
tables are *execution-equivalent under this query*, not proven semantic
aliases.  Keeping both metrics prevents a strict exact-label benchmark from
mistaking a valid reusable artifact for a retrieval failure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from modern_term_acronym_port import STOP, stable_hash, termhood, tokens
from wmh_bird_exposure_counterfactual import (
    Trace,
    execute,
    file_hash,
    load_traces,
    lexical_score,
    ngrams,
    substitute_table,
)


SCHEMA_VERSION = "frankengate-wmh-bird-equivalence-aware-retrieval-v1"


def rank_metrics(order: list[str], targets: set[str]) -> dict[str, float]:
    positions = [index for index, item in enumerate(order, 1) if item in targets]
    first = positions[0] if positions else None
    return {
        "mrr": round(1.0 / first, 6) if first else 0.0,
        "recall_at_1": float(first == 1),
        "recall_at_5": float(first is not None and first <= 5),
        "recall_at_10": float(first is not None and first <= 10),
    }


def aggregate(rows: list[dict[str, float]]) -> dict[str, Any]:
    if not rows:
        return {"cases": 0, "mrr": 0.0, "recall_at_1": 0.0, "recall_at_5": 0.0, "recall_at_10": 0.0}
    return {
        "cases": len(rows),
        **{key: round(sum(row[key] for row in rows) / len(rows), 6) for key in ("mrr", "recall_at_1", "recall_at_5", "recall_at_10")},
    }


def equivalent_candidates(trace: Trace, db_root: Path) -> tuple[set[str], int, int]:
    """Return candidates with at least one result-preserving table swap."""
    db_path = db_root / trace.db_name / f"{trace.db_name}.sqlite"
    status, base_rows = execute(db_path, trace.sql)
    if status != "ok":
        return set(), 0, 0
    equivalent: set[str] = set()
    errors = mismatches = 0
    for candidate in sorted(trace.exposed_tables - trace.used_tables):
        candidate_match = False
        for old in sorted(trace.used_tables):
            try:
                counterfactual = substitute_table(trace.sql, old, candidate)
            except Exception:
                errors += 1
                continue
            cf_status, rows = execute(db_path, counterfactual)
            if cf_status != "ok":
                errors += 1
            elif rows == base_rows:
                candidate_match = True
            else:
                mismatches += 1
        if candidate_match:
            equivalent.add(candidate)
    return equivalent, errors, mismatches


def run(traces_path: Path, manifest: Path, db_root: Path, output: Path, limit: int = 3000) -> dict[str, Any]:
    selected = load_traces(traces_path, manifest)
    by_db: dict[str, list[Trace]] = defaultdict(list)
    replay_equivalent_count = 0
    replay_pairs = replay_errors = replay_mismatches = 0
    equivalence_by_trace: dict[str, set[str]] = {}
    for trace in selected:
        equivalent, errors, mismatches = equivalent_candidates(trace, db_root)
        replay_equivalent_count += len(equivalent)
        replay_errors += errors
        replay_mismatches += mismatches
        replay_pairs += errors + mismatches + len(equivalent)
        equivalence_by_trace[trace.trace_hash] = equivalent
        if trace.used_tables & trace.exposed_tables:
            by_db[trace.db_name].append(trace)

    arms: dict[str, dict[str, list[dict[str, float]]]] = defaultdict(lambda: {"exact": [], "execution_equivalent": [], "execution_equivalent_only": []})
    fold_rows: list[dict[str, Any]] = []
    for db in sorted(by_db):
        ordered = sorted(by_db[db], key=lambda item: stable_hash(item.base_task_id))
        train, evaluation = ordered[::2], ordered[1::2]
        admitted = {item["term_hash"] for item in termhood([row.prompt for row in train], [row.prompt for row in train], limit=limit)}
        mapping: dict[tuple[str, str], set[str]] = defaultdict(set)
        for row in train:
            for term_hash in ngrams(row.prompt):
                if term_hash in admitted:
                    mapping[(db, term_hash)].update(row.used_tables & row.exposed_tables)
        for row in evaluation:
            pool = sorted(row.exposed_tables)
            exact = set(row.used_tables & row.exposed_tables)
            equivalent = exact | equivalence_by_trace.get(row.trace_hash, set())
            equivalent_only = equivalent - exact
            aliases = set().union(*(mapping.get((db, key), set()) for key in ngrams(row.prompt)))
            lexical = sorted(pool, key=lambda table: (-lexical_score(row.prompt, table), table))
            enriched = sorted(pool, key=lambda table: (-lexical_score(row.prompt, table) - (20.0 if table in aliases else 0.0), table))
            for arm, order in (("lexical", lexical), ("termhood_alias", enriched)):
                arms[arm]["exact"].append(rank_metrics(order, exact))
                arms[arm]["execution_equivalent"].append(rank_metrics(order, equivalent))
                # Empty target sets are retained as an explicit zero rather
                # than silently changing the denominator; this measures how
                # often an alternate executable artifact is independently
                # discoverable, not just whether the recorded target wins.
                arms[arm]["execution_equivalent_only"].append(rank_metrics(order, equivalent_only))
        fold_rows.append({"db_name": db, "train_tasks": len(train), "evaluation_tasks": len(evaluation), "mapped_terms": len(mapping)})

    metrics = {
        arm: {target: aggregate(rows) for target, rows in targets.items()}
        for arm, targets in sorted(arms.items())
    }
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "traces_sha256": file_hash(traces_path),
            "manifest_sha256": file_hash(manifest),
            "raw_content_committed": False,
            "sqlite_root": "external-pinned-bird-minidev",
        },
        "cohort": {
            "selected_successful_tasks": len(selected),
            "database_families": len(by_db),
            "split": "within-database deterministic odd/even task split",
            "exact_target": "recorded SQL table references",
            "execution_equivalent_target": "recorded references plus exposed tables with at least one result-preserving substitution",
        },
        "replay": {
            "counterfactual_pairs": replay_pairs,
            "execution_errors": replay_errors,
            "result_mismatches": replay_mismatches,
            "result_preserving_candidates": replay_equivalent_count,
        },
        "folds": fold_rows,
        "metrics": metrics,
        "claim_boundary": {
            "execution_equivalence_is_semantic_alias": False,
            "enterprise_intent_labels_established": False,
            "validated_artifact_utility_established": False,
            "reason": "Result preservation is a deterministic compatibility label for this SQL/database pair, not human intent or a general replacement guarantee.",
        },
    }
    result["result_sha256"] = stable_hash(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"replay": result["replay"], "metrics": metrics}, sort_keys=True))
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
