#!/usr/bin/env python3
"""Compare lexical, local dense, and frontier table exploration on WMH-BIRD.

The cohort and evaluator are shared with the task-disjoint explorer study. The
frontier sees only the question and exposed table names; SQL, replay outcomes,
and target tables remain evaluator-only. Dense vectors come from the local
Nomic embedding service and are used only for candidate ordering.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Sequence
from urllib import request

from wmh_bird_exposure_counterfactual import execute, file_hash, load_traces, rank_metrics
from wmh_bird_equivalence_aware_retrieval import equivalent_candidates
from wmh_bird_sql_explorer_cohort import select_eval_cases
from wmh_bird_sql_explorer_probe import call_frontier, lexical_order, metric_row, prompt_for, stable_hash


SCHEMA_VERSION = "frankengate-wmh-bird-sql-dense-frontier-cohort-v1"
EMBED_MODEL = "nomic-embed-text:latest"
MAX_SHORTLIST = 8


def cosine(left: Sequence[float], right: Sequence[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(a * a for a in right))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


def post_embed(endpoint: str, texts: Sequence[str]) -> list[list[float]]:
    payload = json.dumps({"model": EMBED_MODEL, "input": list(texts), "truncate": True}).encode()
    req = request.Request(endpoint.rstrip("/") + "/api/embed", data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with request.urlopen(req, timeout=300) as response:
        value = json.loads(response.read().decode())
    vectors = value.get("embeddings")
    if not isinstance(vectors, list) or len(vectors) != len(texts):
        raise RuntimeError("embedding response count mismatch")
    return [[float(item) for item in vector] for vector in vectors]


def mean(rows: list[dict[str, Any]], key: str) -> float:
    return round(sum(float(row[key]) for row in rows) / len(rows), 6) if rows else 0.0


def run(traces_path: Path, manifest: Path, db_root: Path, output: Path, raw_dir: Path, *, endpoint: str, model: str, per_db: int, run_label: str) -> dict[str, Any]:
    traces = load_traces(traces_path, manifest)
    selected = select_eval_cases(traces, db_root, per_db)
    if not selected:
        raise ValueError("no selected cohort cases")
    raw_dir.mkdir(parents=True, exist_ok=True)
    texts: list[str] = []
    keys: list[tuple[str, int, int | None]] = []
    for case_index, trace in enumerate(selected):
        texts.append(f"database {trace.db_name} question {trace.prompt}")
        keys.append(("query", case_index, None))
        for candidate_index, table in enumerate(sorted(trace.exposed_tables)):
            texts.append(f"database {trace.db_name} table {table}")
            keys.append(("candidate", case_index, candidate_index))
    vectors = post_embed(endpoint, texts)
    query_vectors = {case_index: vectors[position] for position, (kind, case_index, _) in enumerate(keys) if kind == "query"}
    candidate_vectors = {(case_index, int(candidate_index)): vectors[position] for position, (kind, case_index, candidate_index) in enumerate(keys) if kind == "candidate"}
    rows: list[dict[str, Any]] = []
    failures = 0
    for case_index, trace in enumerate(selected):
        candidates = sorted(trace.exposed_tables)
        targets = frozenset(trace.used_tables & trace.exposed_tables)
        equivalents, _, _ = equivalent_candidates(trace, db_root)
        compatible = targets | equivalents
        lexical = lexical_order(trace)[:MAX_SHORTLIST]
        dense_order = sorted(range(len(candidates)), key=lambda index: (-cosine(query_vectors[case_index], candidate_vectors[(case_index, index)]), candidates[index]))[:MAX_SHORTLIST]
        dense = [candidates[index] for index in dense_order]
        raw_path = raw_dir / f"case-{case_index:03d}.json"
        prompt = prompt_for(trace, candidates, run_label)
        try:
            value = call_frontier(prompt, model, raw_path)
            indices = [int(item) for item in value["selected_indices"]]
            if any(item < 0 or item >= len(candidates) for item in indices):
                raise ValueError("frontier index outside candidate pool")
            frontier = [candidates[item] for item in indices]
            rows.append({
                "case_index": case_index,
                "db_name": trace.db_name,
                "trace_hash": trace.trace_hash,
                "base_task_id_hash": hashlib.sha256(trace.base_task_id.encode()).hexdigest(),
                "candidate_count": len(candidates),
                "target_count": len(targets),
                "equivalent_count": len(equivalents),
                "lexical": metric_row(lexical, targets, compatible, len(candidates)),
                "dense": metric_row(dense, targets, compatible, len(candidates)),
                "frontier": metric_row(frontier, targets, compatible, len(candidates)),
            })
        except Exception as exc:
            failures += 1
            rows.append({"case_index": case_index, "db_name": trace.db_name, "trace_hash": trace.trace_hash, "candidate_count": len(candidates), "error": type(exc).__name__, "error_message": str(exc)})
    completed = [row for row in rows if "frontier" in row]
    arms: dict[str, dict[str, Any]] = {}
    for arm in ("lexical", "dense", "frontier"):
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
        "protocol": {"embedding_endpoint": endpoint, "embedding_model": EMBED_MODEL, "frontier_model": model, "run_label": run_label, "max_shortlist": MAX_SHORTLIST, "explorer_sees_sql": False, "explorer_sees_replay_outcomes": False, "explorer_sees_gold_targets": False, "tool_endpoints_invoked": False, "raw_model_outputs_external": True},
        "arms": arms,
        "rows": rows,
        "failures": failures,
        "claim_boundary": {"dense_frontier_replay_cohort_measured": failures < len(selected), "semantic_alias_quality_established": False, "validated_artifact_utility_established": False, "enterprise_skill_transfer_measured": False, "reason": "Public WMH-BIRD proxy with independent SQLite replay. It has no enterprise principal, authority epoch, human intent, or changed-system outcome labels."},
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
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--per-db", type=int, default=4)
    parser.add_argument("--run-label", default="dense-frontier-cohort-v1")
    args = parser.parse_args()
    run(args.traces, args.manifest, args.db_root, args.output, args.raw_dir, endpoint=args.endpoint, model=args.model, per_db=args.per_db, run_label=args.run_label)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
