#!/usr/bin/env python3
"""Compare full-pool frontier review with typed-retrieval -> frontier review."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from ontology_projection_cohort import build_alias_edges, rank_arm, recorded_schema_terms, split_by_db
from wmh_bird_equivalence_aware_retrieval import equivalent_candidates
from wmh_bird_exposure_counterfactual import file_hash, load_traces
from wmh_bird_sql_explorer_cohort import select_eval_cases
from wmh_bird_sql_explorer_probe import call_frontier, metric_row, prompt_for, stable_hash


SCHEMA_VERSION = "frankengate-wmh-bird-sequential-cascade-v1"
MAX_SHORTLIST = 8


def aggregate(rows: list[dict[str, Any]], arm: str) -> dict[str, Any]:
    values = [row[arm] for row in rows if arm in row]
    if not values:
        return {"records": 0}
    names = (
        "strict_mrr", "strict_recall_at_1", "strict_recall_at_5", "strict_recall_at_10",
        "compatible_mrr", "compatible_recall_at_1", "compatible_recall_at_5", "compatible_recall_at_10",
        "compatible_selected_rate", "invalid_selected_count", "selected_count",
    )
    return {"records": len(values), **{name: round(sum(float(row[name]) for row in values) / len(values), 6) for name in names}}


def run(
    traces_path: Path,
    manifest_path: Path,
    db_root: Path,
    output: Path,
    raw_dir: Path,
    *,
    per_db: int = 4,
    model: str = "gpt-5.6-luna",
    run_label: str = "typed-sequential-cascade-v1",
) -> dict[str, Any]:
    traces = load_traces(traces_path, manifest_path)
    train, _ = split_by_db(traces)
    selected = select_eval_cases(traces, db_root, per_db)
    if len(selected) != 44:
        raise ValueError(f"expected 44 selected cases, got {len(selected)}")
    schema_by_trace = recorded_schema_terms(traces_path)
    alias_edges = build_alias_edges(train)
    action_edges = build_alias_edges(train, replay_only=True, db_root=db_root)
    raw_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    frontier_calls = 0
    for case_index, trace in enumerate(selected):
        candidates = sorted(trace.exposed_tables)
        targets = frozenset(trace.used_tables & trace.exposed_tables)
        equivalents, _, _ = equivalent_candidates(trace, db_root)
        compatible = targets | equivalents
        typed_order = rank_arm("A1", trace, candidates, db_root, alias_edges, action_edges, schema_by_trace)[:MAX_SHORTLIST]
        lexical_order = sorted(candidates, key=lambda item: (item not in typed_order, item))[:MAX_SHORTLIST]
        row: dict[str, Any] = {
            "case_index": case_index,
            "trace_hash": trace.trace_hash,
            "base_task_id_hash": hashlib.sha256(trace.base_task_id.encode()).hexdigest(),
            "candidate_count": len(candidates),
            "target_count": len(targets),
            "equivalent_count": len(equivalents),
            "typed_schema": metric_row(typed_order, targets, compatible, len(candidates)),
        }
        # Full-pool frontier control and typed-shortlist sequential arm use the
        # same model, prompt contract, task order, and replay evaluator.
        for arm, pool in (("frontier_full_pool", candidates), ("typed_then_frontier", typed_order)):
            raw_path = raw_dir / f"case-{case_index:03d}-{arm}.json"
            prompt = prompt_for(trace, pool, f"{run_label}:{arm}")
            frontier_calls += 1
            try:
                value = call_frontier(prompt, model, raw_path)
                indices = [int(item) for item in value["selected_indices"]]
                if any(item < 0 or item >= len(pool) for item in indices):
                    raise ValueError("frontier index outside candidate pool")
                selected_tables = [pool[index] for index in indices]
                row[arm] = metric_row(selected_tables, targets, compatible, len(candidates))
            except Exception as exc:
                failures.append({"case_index": case_index, "arm": arm, "error": type(exc).__name__})
        rows.append(row)
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source": {"traces_sha256": file_hash(traces_path), "manifest_sha256": file_hash(manifest_path), "sqlite_root": "external-pinned-bird-minidev", "raw_content_committed": False},
        "dataset": {"selected_cases": len(selected), "database_families": sorted({trace.db_name for trace in selected}), "per_database_limit": per_db, "split": "within-database deterministic odd/even task split; evaluation uses odd half", "candidate_pool": "all tables exposed in each trace", "target": "recorded SQL tables; compatibility adds independently result-preserving substitutions"},
        "protocol": {"model": model, "frontier_calls": frontier_calls, "max_shortlist": MAX_SHORTLIST, "frontier_sees_sql": False, "frontier_sees_replay_outcomes": False, "frontier_sees_gold_targets": False, "typed_shortlist_before_review": True, "raw_model_outputs_external": True, "run_label": run_label},
        "arms": {arm: aggregate(rows, arm) for arm in ("typed_schema", "frontier_full_pool", "typed_then_frontier")},
        "failures": failures,
        "claim_boundary": {"aligned_sequential_cascade_measured": not failures, "semantic_alias_quality_established": False, "validated_artifact_utility_established": False, "enterprise_skill_transfer_measured": False, "reason": "Frozen public WMH-BIRD proxy with SQLite replay; no human alias labels, principal scopes, authority epochs, or changed-system outcomes."},
    }
    result["result_sha256"] = stable_hash(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"arms": result["arms"], "frontier_calls": frontier_calls, "failures": len(failures)}, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--traces", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--db-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--per-db", type=int, default=4)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--run-label", default="typed-sequential-cascade-v1")
    args = parser.parse_args()
    run(args.traces, args.manifest, args.db_root, args.output, args.raw_dir, per_db=args.per_db, model=args.model, run_label=args.run_label)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
