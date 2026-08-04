#!/usr/bin/env python3
"""Run deterministic ontology arms on the frozen 44-case WMH-BIRD cohort."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from modern_term_acronym_port import stable_hash
from ontology_projection_cohort import (
    build_alias_edges,
    rank_arm,
    recorded_schema_terms,
    split_by_db,
)
from wmh_bird_equivalence_aware_retrieval import equivalent_candidates
from wmh_bird_exposure_counterfactual import file_hash, load_traces
from wmh_bird_sql_explorer_cohort import select_eval_cases


SCHEMA_VERSION = "frankengate-wmh-bird-ontology-aligned-cohort-v1"
MAX_SHORTLIST = 8


def row_metrics(order: list[str], exact: set[str], compatible: set[str]) -> dict[str, float]:
    exact_positions = [index for index, candidate in enumerate(order, 1) if candidate in exact]
    compatible_positions = [index for index, candidate in enumerate(order, 1) if candidate in compatible]
    first = exact_positions[0] if exact_positions else None
    compatible_first = compatible_positions[0] if compatible_positions else None
    return {
        "strict_mrr": 1.0 / first if first else 0.0,
        "strict_recall_at_1": float(first == 1),
        "strict_recall_at_5": float(first is not None and first <= 5),
        "strict_recall_at_10": float(first is not None and first <= 10),
        "compatible_mrr": 1.0 / compatible_first if compatible_first else 0.0,
        "compatible_recall_at_1": float(compatible_first == 1),
        "compatible_recall_at_5": float(compatible_first is not None and compatible_first <= 5),
        "compatible_recall_at_10": float(compatible_first is not None and compatible_first <= 10),
    }


def mean(rows: list[dict[str, float]], key: str) -> float:
    return round(sum(row[key] for row in rows) / len(rows), 6) if rows else 0.0


def run(traces_path: Path, manifest_path: Path, db_root: Path, output: Path, per_db: int = 4) -> dict[str, Any]:
    traces = load_traces(traces_path, manifest_path)
    train, _ = split_by_db(traces)
    selected = select_eval_cases(traces, db_root, per_db)
    if len(selected) != 44:
        raise ValueError(f"expected frozen 44-case cohort, got {len(selected)}")
    schema_by_trace = recorded_schema_terms(traces_path)
    alias_edges = build_alias_edges(train)
    action_edges = build_alias_edges(train, replay_only=True, db_root=db_root)
    arms = ("A0", "A1", "A2", "A3", "A6", "A7")
    rows_by_arm: dict[str, list[dict[str, float]]] = defaultdict(list)
    for trace in selected:
        candidates = sorted(trace.exposed_tables)
        exact = set(trace.used_tables & trace.exposed_tables)
        equivalents, _, _ = equivalent_candidates(trace, db_root)
        compatible = exact | equivalents
        for arm in arms:
            order = rank_arm(arm, trace, candidates, db_root, alias_edges, action_edges, schema_by_trace)[:MAX_SHORTLIST]
            rows_by_arm[arm].append(row_metrics(order, exact, compatible))
    metric_names = (
        "strict_mrr", "strict_recall_at_1", "strict_recall_at_5", "strict_recall_at_10",
        "compatible_mrr", "compatible_recall_at_1", "compatible_recall_at_5", "compatible_recall_at_10",
    )
    aggregate = {
        arm: {"records": len(rows), **{name: mean(rows, name) for name in metric_names}}
        for arm, rows in sorted(rows_by_arm.items())
    }
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "traces_sha256": file_hash(traces_path),
            "manifest_sha256": file_hash(manifest_path),
            "sqlite_root": "external-pinned-bird-minidev",
            "raw_content_committed": False,
        },
        "dataset": {
            "selected_cases": len(selected),
            "database_families": sorted({trace.db_name for trace in selected}),
            "per_database_limit": per_db,
            "split": "within-database deterministic odd/even task split; evaluation uses odd half",
            "candidate_pool": "all tables exposed in each trace",
            "target": "recorded SQL tables; compatibility adds independently result-preserving substitutions",
        },
        "protocol": {
            "arms": list(arms),
            "schema_identifiers": "recorded gen_ai.tool.message DDL only",
            "frontier_or_embedding_invoked": False,
            "target_labels_external": True,
        },
        "arms": aggregate,
        "claim_boundary": {
            "aligned_proxy_cohort_measured": True,
            "semantic_alias_quality_established": False,
            "authority_safety_established": False,
            "validated_artifact_utility_established": False,
            "enterprise_skill_transfer_measured": False,
            "reason": "The frozen public cohort has SQL table references and SQLite replay, but no reviewed aliases, principals, authority epochs, or changed-system outcomes.",
        },
    }
    result["result_sha256"] = stable_hash(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"selected_cases": len(selected), "arms": aggregate}, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--traces", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--db-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--per-db", type=int, default=4)
    args = parser.parse_args()
    run(args.traces, args.manifest, args.db_root, args.output, per_db=args.per_db)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
