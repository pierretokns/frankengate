#!/usr/bin/env python3
"""Run the separate SQL explorer on a stratified task-disjoint cohort."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from wmh_bird_equivalence_aware_retrieval import equivalent_candidates
from wmh_bird_exposure_counterfactual import Trace, execute, load_traces
from wmh_bird_sql_explorer_probe import (
    call_frontier,
    file_hash,
    lexical_order,
    metric_row,
    prompt_for,
    stable_hash,
)


SCHEMA_VERSION = "frankengate-wmh-bird-sql-explorer-cohort-v1"
MAX_SHORTLIST = 8


def select_eval_cases(traces: list[Trace], db_root: Path, per_db: int) -> list[Trace]:
    by_db: dict[str, list[Trace]] = defaultdict(list)
    for trace in traces:
        db_path = db_root / trace.db_name / f"{trace.db_name}.sqlite"
        status, _ = execute(db_path, trace.sql)
        if status == "ok" and trace.used_tables & trace.exposed_tables:
            by_db[trace.db_name].append(trace)
    selected: list[Trace] = []
    for db in sorted(by_db):
        ordered = sorted(by_db[db], key=lambda item: stable_hash(item.base_task_id))
        selected.extend(ordered[1::2][:per_db])
    return selected


def mean(rows: list[dict[str, Any]], key: str) -> float:
    return round(sum(float(row[key]) for row in rows) / len(rows), 6) if rows else 0.0


def run(traces_path: Path, manifest: Path, db_root: Path, output: Path, raw_dir: Path, *, per_db: int = 4, model: str = "gpt-5.6-luna", run_label: str = "cohort") -> dict[str, Any]:
    traces = load_traces(traces_path, manifest)
    selected = select_eval_cases(traces, db_root, per_db)
    raw_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    failures = 0
    for index, trace in enumerate(selected):
        candidates = sorted(trace.exposed_tables)
        targets = frozenset(trace.used_tables & trace.exposed_tables)
        equivalent, _, _ = equivalent_candidates(trace, db_root)
        compatible = targets | equivalent
        lexical = lexical_order(trace)[:MAX_SHORTLIST]
        raw_path = raw_dir / f"case-{index:03d}.json"
        prompt = prompt_for(trace, candidates, run_label)
        try:
            value = call_frontier(prompt, model, raw_path)
            indices = [int(item) for item in value["selected_indices"]]
            if any(item < 0 or item >= len(candidates) for item in indices):
                raise ValueError("selected index outside exposed table pool")
            explorer_order = [candidates[item] for item in indices]
            rows.append({
                "case_index": index,
                "db_name": trace.db_name,
                "trace_hash": trace.trace_hash,
                "base_task_id_hash": hashlib.sha256(trace.base_task_id.encode()).hexdigest(),
                "candidate_count": len(candidates),
                "prompt_chars": len(prompt),
                "target_count": len(targets),
                "equivalent_count": len(equivalent),
                "lexical": metric_row(lexical, targets, compatible, len(candidates)),
                "explorer": metric_row(explorer_order, targets, compatible, len(candidates)),
            })
        except Exception as exc:
            failures += 1
            rows.append({"case_index": index, "db_name": trace.db_name, "trace_hash": trace.trace_hash, "candidate_count": len(candidates), "error": type(exc).__name__, "error_message": str(exc)})
    completed = [row for row in rows if "explorer" in row]
    arms: dict[str, dict[str, Any]] = {}
    for arm in ("lexical", "explorer"):
        values = [row[arm] for row in completed]
        arms[arm] = {
            "records": len(values),
            "strict_mrr": mean(values, "strict_mrr"),
            "strict_recall_at_1": mean(values, "strict_recall_at_1"),
            "strict_recall_at_5": mean(values, "strict_recall_at_5"),
            "strict_recall_at_10": mean(values, "strict_recall_at_10"),
            "compatible_mrr": mean(values, "compatible_mrr"),
            "compatible_recall_at_1": mean(values, "compatible_recall_at_1"),
            "compatible_recall_at_5": mean(values, "compatible_recall_at_5"),
            "compatible_recall_at_10": mean(values, "compatible_recall_at_10"),
            "compatible_selected_rate": mean(values, "compatible_selected_rate"),
            "invalid_selected_count": mean(values, "invalid_selected_count"),
            "selected_count": mean(values, "selected_count"),
        }
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source": {"traces_sha256": file_hash(traces_path), "manifest_sha256": file_hash(manifest), "raw_content_committed": False, "sqlite_root": "external-pinned-bird-minidev"},
        "dataset": {"selected_cases": len(selected), "database_families": sorted({row["db_name"] for row in rows}), "per_database_limit": per_db, "split": "within-database deterministic odd/even task split; evaluation uses odd half", "candidate_pool": "all tables exposed in each trace", "target": "recorded SQL tables; compatibility adds independently result-preserving substitutions"},
        "protocol": {"model": model, "run_label": run_label, "max_shortlist": MAX_SHORTLIST, "explorer_sees_sql": False, "explorer_sees_replay_outcomes": False, "explorer_sees_gold_targets": False, "tool_endpoints_invoked": False, "raw_model_outputs_external": True},
        "arms": arms,
        "rows": rows,
        "failures": failures,
        "claim_boundary": {"task_disjoint_sql_explorer_measured": failures < len(selected), "replay_compatibility_measured": True, "semantic_alias_quality_established": False, "validated_artifact_utility_established": False, "enterprise_skill_transfer_measured": False, "reason": "This is a public WMH-BIRD proxy with independent SQLite replay. It has no enterprise principal, authority epoch, human intent, changed-system outcome, or production utility label."},
    }
    result["result_sha256"] = stable_hash(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"arms": arms, "failures": failures, "selected_cases": len(selected)}, sort_keys=True))
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
    parser.add_argument("--run-label", default="cohort")
    args = parser.parse_args()
    run(args.traces, args.manifest, args.db_root, args.output, args.raw_dir, per_db=args.per_db, model=args.model, run_label=args.run_label)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
