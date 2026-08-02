#!/usr/bin/env python3
"""Compose the existing same-cohort alias cascade receipts.

The real Defog alias cohort already evaluated lexical, exact-identifier, dense,
and Luna frontier arms on the same 22 cases.  This audit makes that comparison
explicit and keeps the synthetic structured-adjudication gate separate.  It
emits only metrics and hashes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-nl2sql-alias-cascade-audit-v1"


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run(real_path: Path, synthetic_path: Path, output: Path) -> dict[str, Any]:
    real = load(real_path)
    synthetic = load(synthetic_path)
    aggregate = real.get("aggregate", {})
    required = {"lexical_scope", "exact_scope", "dense_scope", "frontier_scope"}
    if set(aggregate) != required:
        raise ValueError(f"unexpected real cascade arms: {sorted(aggregate)}")
    arms = {}
    per_case = real.get("per_case", [])
    for name in sorted(aggregate):
        row = aggregate[name]
        nil_rows = [item for item in per_case if item.get("category") == "scope_swapped_nil"]
        nil_top1 = [item.get("metrics", {}).get(name, {}).get("top1_is_any_candidate") for item in nil_rows]
        nil_top1 = [float(value) for value in nil_top1 if value is not None]
        arms[name] = {
            "targeted_cases": row["targeted_cases"],
            "targeted_mrr": row["targeted_mrr"],
            "targeted_recall_at_1": row["targeted_recall_at_1"],
            "targeted_recall_at_5": row["targeted_recall_at_5"],
            "targeted_wrong_system_before_target": row["targeted_wrong_system_before_target"],
            "nil_cases": row["nil_cases"],
            "nil_top1_candidate_rate": round(sum(nil_top1) / len(nil_top1), 6) if nil_top1 else row.get("nil_top1_candidate_rate"),
        }
    def delta(left: str, right: str, field: str) -> float:
        return round(arms[left][field] - arms[right][field], 6)
    stratified: dict[str, dict[str, dict[str, float | None]]] = {}
    for category in sorted({item.get("category") for item in per_case}):
        stratified[category] = {}
        category_rows = [item for item in per_case if item.get("category") == category]
        for arm in sorted(required):
            stratified[category][arm] = {}
            for field in ("mrr", "recall_at_1", "recall_at_5", "wrong_system_before_target", "top1_is_any_candidate"):
                values = [item.get("metrics", {}).get(arm, {}).get(field) for item in category_rows]
                values = [float(value) for value in values if value is not None]
                stratified[category][arm][field] = round(sum(values) / len(values), 6) if values else None
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "inputs": {
            "real_alias_receipt_sha256": digest(real),
            "synthetic_adjudication_receipt_sha256": digest(synthetic),
            "real_schema_version": real.get("schema_version"),
            "synthetic_schema_version": synthetic.get("schema_version"),
            "raw_content_committed": False,
        },
        "same_cohort": {
            "selected_cases": real.get("dataset", {}).get("selected_cases"),
            "targeted_cases": arms["lexical_scope"]["targeted_cases"],
            "nil_cases": arms["lexical_scope"]["nil_cases"],
            "frontier_calls_completed": real.get("frontier_calls", {}).get("completed"),
            "frontier_decision_accuracy": real.get("frontier_decision", {}).get("accuracy"),
        },
        "arms": arms,
        "stratified": stratified,
        "deltas_vs_dense": {
            "lexical_mrr": delta("lexical_scope", "dense_scope", "targeted_mrr"),
            "exact_mrr": delta("exact_scope", "dense_scope", "targeted_mrr"),
            "frontier_mrr": delta("frontier_scope", "dense_scope", "targeted_mrr"),
            "exact_recall_at_1": delta("exact_scope", "dense_scope", "targeted_recall_at_1"),
            "frontier_recall_at_1": delta("frontier_scope", "dense_scope", "targeted_recall_at_1"),
        },
        "synthetic_gate": {
            "cases": synthetic.get("cases", {}).get("count"),
            "surface_accuracy_primary": synthetic.get("arms", [{}])[0].get("score", {}).get("surface_accuracy"),
            "candidate_accuracy_primary": synthetic.get("arms", [{}])[0].get("score", {}).get("candidate_accuracy"),
            "nil_unclear_abstention_primary": synthetic.get("arms", [{}])[0].get("score", {}).get("nil_unclear_abstention"),
            "inter_judge_surface_agreement": synthetic.get("inter_judge", {}).get("surface_agreement"),
            "inter_judge_candidate_agreement": synthetic.get("inter_judge", {}).get("candidate_agreement"),
        },
        "interpretation": {
            "same_cohort_frontier_vs_dense": "Frontier ranking improves target ordering on this small public proxy but does not establish semantic alias truth; the retrieval benchmark's gold targets come from SQL.",
            "same_cohort_dense_vs_structured": "Dense retrieval is below exact structured retrieval on this cohort, so it remains candidate recall rather than authority.",
            "nil_behavior": "All retrieval arms still return a candidate on constructed NIL cases; only the frontier decision arm abstains. Candidate retrieval and refusal must therefore be measured separately.",
            "synthetic_gate": "The 23-case structured adjudication result is a capability/abstention gate, not enterprise ground truth.",
        },
        "claim_boundary": {
            "same_cohort_comparison": True,
            "enterprise_alias_quality": False,
            "human_truth": False,
            "changed_system_utility": False,
            "promotion_authorized": False,
        },
    }
    result["result_sha256"] = digest(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"same_cohort": result["same_cohort"], "arms": arms, "deltas_vs_dense": result["deltas_vs_dense"]}, sort_keys=True))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--real", type=Path, required=True)
    parser.add_argument("--synthetic", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.real, args.synthetic, args.output)
