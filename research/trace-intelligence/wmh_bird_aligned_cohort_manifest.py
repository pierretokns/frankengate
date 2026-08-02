#!/usr/bin/env python3
"""Freeze a content-free, replay-backed WMH-BIRD comparison cohort."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from wmh_bird_exposure_counterfactual import file_hash, load_traces
from wmh_bird_sql_explorer_cohort import select_eval_cases
from wmh_bird_sql_explorer_probe import stable_hash


SCHEMA_VERSION = "frankengate-wmh-bird-aligned-cascade-cohort-v1"


def pool_hash(trace: Any) -> str:
    value = sorted(str(table).casefold() for table in trace.exposed_tables)
    return hashlib.sha256(json.dumps(value, separators=(",", ":")).encode()).hexdigest()


def run(traces_path: Path, manifest_path: Path, db_root: Path, output: Path, per_db: int = 4) -> dict[str, Any]:
    traces = load_traces(traces_path, manifest_path)
    selected = select_eval_cases(traces, db_root, per_db)
    cases = [
        {
            "trace_hash": trace.trace_hash,
            "base_task_id_hash": hashlib.sha256(trace.base_task_id.encode()).hexdigest(),
            "db_name_hash": hashlib.sha256(trace.db_name.encode()).hexdigest(),
            "candidate_count": len(trace.exposed_tables),
            "candidate_pool_hash": pool_hash(trace),
            "target_count_external": len(trace.used_tables & trace.exposed_tables),
        }
        for trace in selected
    ]
    cases = sorted(cases, key=lambda row: (row["db_name_hash"], row["trace_hash"]))
    case_set_sha256 = stable_hash(cases)
    cohort_id = stable_hash({"source": file_hash(traces_path), "manifest": file_hash(manifest_path), "per_db": per_db, "cases": cases})
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "cohort_id": cohort_id,
        "case_set_sha256": case_set_sha256,
        "source": {
            "traces_sha256": file_hash(traces_path),
            "manifest_sha256": file_hash(manifest_path),
            "sqlite_root": "external-pinned-bird-minidev",
            "raw_content_committed": False,
        },
        "selection": {
            "algorithm": "wmh_bird_sql_explorer_cohort.select_eval_cases",
            "per_database_limit": per_db,
            "split": "within-database deterministic odd/even task split; evaluation uses odd half",
            "candidate_pool": "all tables exposed in each trace",
            "target_labels": "external evaluator only",
        },
        "arms": [
            "A0_lexical",
            "A1_schema_first",
            "A2_provenance_alias",
            "A3_typed_plus_alias",
            "A4_dense",
            "A5_authority_constrained",
            "A6_replay_backed_action",
            "A7_schema_first_bootstrap",
            "A8_frontier_review",
        ],
        "holdouts": ["database_family", "task_id", "candidate_pool"],
        "cases": cases,
        "claim_boundary": {
            "aligned_proxy_cohort_frozen": True,
            "enterprise_semantic_cohort": False,
            "reviewed_alias_labels": False,
            "principal_or_policy_epoch": False,
            "changed_system_outcomes": False,
            "promotion_ready": False,
            "reason": "This freezes a public SQL-agent comparison cohort; target labels, semantic aliases, authority, and enterprise utility remain external or unavailable.",
        },
    }
    result["result_sha256"] = stable_hash(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"cohort_id": cohort_id, "selected_cases": len(cases), "arms": result["arms"]}, sort_keys=True))
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
