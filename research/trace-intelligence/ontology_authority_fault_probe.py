#!/usr/bin/env python3
"""Exercise the authority-constrained retrieval gate with synthetic faults.

WMH-BIRD has no principal or policy-epoch labels, so this is an infrastructure
probe, not an authorization result.  Each held-out task receives a synthetic
scope that always permits its recorded target table(s) and permits a
deterministic subset of distractors.  A deliberately injected alias edge
points at a non-permitted distractor.  The unconstrained arm may select it;
the constrained arm must remove it while retaining the permitted target.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from modern_term_acronym_port import stable_hash
from ontology_projection_cohort import (
    build_alias_edges,
    rank_arm,
    split_by_db,
)
from wmh_bird_exposure_counterfactual import Trace, file_hash, load_traces


SCHEMA_VERSION = "frankengate-ontology-authority-fault-probe-v1"


def allowed_for(trace: Trace, candidate: str, targets: set[str]) -> bool:
    if candidate in targets:
        return True
    digest = int(stable_hash(f"scope:{trace.trace_hash}:{candidate}"), 16)
    return digest % 4 == 0


def choose_unauthorized(trace: Trace, candidates: list[str], targets: set[str]) -> str | None:
    choices = [candidate for candidate in candidates if candidate not in targets and not allowed_for(trace, candidate, targets)]
    return sorted(choices, key=lambda candidate: stable_hash(f"fault:{trace.trace_hash}:{candidate}"))[0] if choices else None


def run(traces_path: Path, manifest: Path, output: Path) -> dict[str, Any]:
    traces = load_traces(traces_path, manifest)
    train, evaluation = split_by_db(traces)
    clean_edges = build_alias_edges(train)
    rows: list[dict[str, Any]] = []
    injected = filtered = unconstrained_unsafe = constrained_unsafe = 0
    target_at_1_before = target_at_1_after = 0
    for trace in evaluation:
        candidates = sorted(trace.exposed_tables)
        targets = set(trace.used_tables & trace.exposed_tables)
        if not targets:
            continue
        fault = choose_unauthorized(trace, candidates, targets)
        if fault is None:
            continue
        injected += 1
        fault_edges = {key: set(values) for key, values in clean_edges.items()}
        for key in list(fault_edges):
            if key[0] == trace.db_name:
                fault_edges[key].add(fault)
        unconstrained = rank_arm("A3", trace, candidates, Path("/does/not/read"), fault_edges, fault_edges)
        allowed = {candidate for candidate in candidates if allowed_for(trace, candidate, targets)}
        constrained = [candidate for candidate in unconstrained if candidate in allowed]
        if unconstrained and unconstrained[0] not in allowed:
            unconstrained_unsafe += 1
        if constrained and constrained[0] not in allowed:
            constrained_unsafe += 1
        filtered += len(unconstrained) - len(constrained)
        target_at_1_before += int(bool(unconstrained) and unconstrained[0] in targets)
        target_at_1_after += int(bool(constrained) and constrained[0] in targets)
        rows.append({
            "trace_hash": trace.trace_hash,
            "candidate_count": len(candidates),
            "target_count": len(targets),
            "injected_unauthorized_edge": True,
            "unconstrained_top1_allowed": bool(unconstrained and unconstrained[0] in allowed),
            "constrained_top1_allowed": bool(constrained and constrained[0] in allowed),
            "constrained_top1_target": bool(constrained and constrained[0] in targets),
            "filtered_candidate_count": len(unconstrained) - len(constrained),
        })
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "traces_sha256": file_hash(traces_path),
            "manifest_sha256": file_hash(manifest),
            "raw_content_committed": False,
        },
        "cohort": {
            "selected_successful_tasks": len(traces),
            "train_tasks": len(train),
            "evaluation_tasks": len(evaluation),
            "evaluated_fault_cases": len(rows),
            "split": "within-database deterministic even/odd task split",
        },
        "fault_fixture": {
            "mutation": "unauthorized_edge",
            "policy": "synthetic scope always permits recorded target tables and deterministic distractor subset",
            "injected_edges": injected,
            "unconstrained_unsafe_top1": unconstrained_unsafe,
            "constrained_unsafe_top1": constrained_unsafe,
            "filtered_candidates": filtered,
            "target_recall_at_1_before": round(target_at_1_before / len(rows), 6) if rows else 0.0,
            "target_recall_at_1_after": round(target_at_1_after / len(rows), 6) if rows else 0.0,
        },
        "claim_boundary": {
            "authority_gate_mechanics_measured": True,
            "unauthorized_edge_count_zero_after_filter": constrained_unsafe == 0,
            "real_enterprise_authorization_established": False,
            "rls_or_policy_epoch_established": False,
            "reason": "The public trace proxy has no principal, team, tenant, or policy-epoch labels; this fixture only tests fail-closed filtering mechanics.",
        },
        "rows": rows,
    }
    result["rows"] = [{"trace_hash": row["trace_hash"], "filtered_candidate_count": row["filtered_candidate_count"], "constrained_top1_target": row["constrained_top1_target"]} for row in rows]
    result["result_sha256"] = stable_hash(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"cohort": result["cohort"], "fault_fixture": result["fault_fixture"], "claim_boundary": result["claim_boundary"]}, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--traces", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.traces, args.manifest, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
