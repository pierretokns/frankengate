#!/usr/bin/env python3
"""Build a content-minimized lifecycle audit from existing artifact receipts.

This is intentionally a cohort-level audit.  The source receipts come from
different public/local fixtures and do not share candidate IDs, so this tool
must never claim that a frontier-reviewed candidate also passed replay.  It
reports the gates separately and makes the missing join explicit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-artifact-lifecycle-audit-v1"


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def classify_frontier_candidate(row: dict[str, Any]) -> str:
    labels = {str(call.get("label")) for call in row.get("calls", [])}
    if "unsafe_or_sensitive" in labels:
        return "blocked_safety"
    if "insufficient_evidence" in labels:
        return "blocked_evidence"
    if len(labels) != 1:
        return "blocked_disagreement"
    label = next(iter(labels))
    if label == "reusable_procedure":
        return "replay_pending"
    if label == "context_specific":
        return "scope_bound"
    return "blocked_unknown_label"


def build_audit(
    *,
    frontier: dict[str, Any],
    replay: dict[str, Any],
    stress: dict[str, Any],
    promotion: dict[str, Any],
    drift: dict[str, Any],
    memory: dict[str, Any],
) -> dict[str, Any]:
    rows = frontier.get("rows", [])
    states: dict[str, int] = {}
    for row in rows:
        state = classify_frontier_candidate(row)
        states[state] = states.get(state, 0) + 1

    replay_aggregate = replay.get("aggregate", {})
    stress_aggregate = stress.get("aggregate", {})
    promotion_obs = promotion.get("observations", {})
    drift_comparison = drift.get("comparison", {})
    ledger = memory.get("ledger_aggregate", {})

    # These are deliberately separate cohorts.  The output says whether each
    # gate has evidence, not that any individual candidate crossed all gates.
    gates = {
        "recurrence_candidate_generation": {
            "status": "supported_as_candidate_signal",
            "same_project_exact_lift": drift_comparison.get("early_same_project_lift_vs_no_early_prior"),
            "same_project_keyshape_lift": drift_comparison.get("early_same_project_keyshape_lift_vs_no_early_prior_keyshape"),
            "interpretation": "Exact, scoped recurrence is a ranking feature; coarse key-shape recurrence is a negative control.",
        },
        "frontier_semantic_review": {
            "status": "review_queue_only",
            "candidate_count": len(rows),
            "agreement_count": int(frontier.get("agreement_count", 0)),
            "disagreement_count": len(rows) - int(frontier.get("agreement_count", 0)),
            "states": states,
            "interpretation": "Unanimous labels still require replay; disagreement, unsafe, and insufficient-evidence labels block promotion.",
        },
        "changed_system_replay": {
            "status": "compatibility_gate_supported",
            "cases": replay_aggregate.get("cases"),
            "strict_accepts": replay_aggregate.get("strict_accepts"),
            "semantic_accepts": replay_aggregate.get("semantic_compatibility_accepts"),
            "semantic_false_accepts": replay_aggregate.get("semantic_compatibility_false_semantic_accepts"),
            "name_false_accepts": replay_aggregate.get("name_compatibility_false_semantic_accepts"),
            "interpretation": "Semantic-ID compatibility prevented the tested false accepts; name-only compatibility did not.",
        },
        "stress_replay": {
            "status": "name_only_policy_rejected",
            "name_accepted": stress_aggregate.get("name_only_subplan", {}).get("accepted"),
            "name_semantic_correct": stress_aggregate.get("name_only_subplan", {}).get("semantic_correct"),
            "name_unsafe_accept": stress_aggregate.get("name_only_subplan", {}).get("unsafe_accept"),
            "semantic_accepted": stress_aggregate.get("semantic_subplan", {}).get("accepted"),
            "semantic_semantic_correct": stress_aggregate.get("semantic_subplan", {}).get("semantic_correct"),
            "semantic_unsafe_accept": stress_aggregate.get("semantic_subplan", {}).get("unsafe_accept"),
            "interpretation": "Name-only transfer accepted unsafe cases in the stress fixture; semantic compatibility was conservative and safe there.",
        },
        "versioned_release_ledger": {
            "status": "state_machine_conformance_only",
            "release_rows": ledger.get("release_rows"),
            "promotions": ledger.get("release_kinds", {}).get("promotion"),
            "rollbacks": ledger.get("release_kinds", {}).get("rollback"),
            "withdrawals": ledger.get("release_kinds", {}).get("deletion_withdrawal"),
            "interpretation": "Versioning, rollback, and withdrawal are representable; extraction quality and user benefit remain unmeasured.",
        },
    }

    result = {
        "schema_version": SCHEMA_VERSION,
        "protocol": {
            "cohort_joined_by_candidate_id": False,
            "frontier_and_replay_are_independent_receipts": True,
            "raw_candidate_content_committed": False,
            "promotion_requires_all_gates": True,
        },
        "frontier_lifecycle": {
            "candidate_count": len(rows),
            "states": states,
            "promotion_ready_count": 0,
            "promotion_ready_definition": "unanimous reusable label + authorized semantic replay + changed-system result check + versioned release",
        },
        "gates": gates,
        "invariants": {
            "disagreement_blocks_promotion": states.get("blocked_disagreement", 0) > 0,
            "unsafe_label_blocks_promotion": states.get("blocked_safety", 0) > 0,
            "insufficient_evidence_blocks_promotion": states.get("blocked_evidence", 0) > 0,
            "name_only_false_accepts_observed": int(replay_aggregate.get("name_compatibility_false_semantic_accepts", 0)) > 0,
            "semantic_false_accepts_absent": int(replay_aggregate.get("semantic_compatibility_false_semantic_accepts", 0)) == 0,
            "stress_name_only_unsafe_accepts_observed": int(stress_aggregate.get("name_only_subplan", {}).get("unsafe_accept", 0)) > 0,
            "stress_semantic_unsafe_accepts_observed": int(stress_aggregate.get("semantic_subplan", {}).get("unsafe_accept", 0)) == 0,
            "causal_user_benefit_established": False,
            "cross_user_intent_equivalence_established": False,
        },
        "claim_boundary": {
            "recurrence_is_correctness": False,
            "frontier_review_is_promotion": False,
            "replay_receipts_share_candidate_ids_with_frontier": False,
            "skill_or_artifact_user_benefit_established": False,
            "interpretation": "The safe product boundary is a provenance-aware candidate and review/replay queue; no automatic skill or artifact promotion is established.",
        },
        "source_receipts": {},
    }
    result["result_sha256"] = digest(result)
    return result


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected object receipt: {path}")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    for name in ("frontier", "replay", "stress", "promotion", "drift", "memory"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    paths = {name: getattr(args, name).resolve() for name in ("frontier", "replay", "stress", "promotion", "drift", "memory")}
    receipts = {name: load(path) for name, path in paths.items()}
    result = build_audit(**receipts)
    result["source_receipts"] = {
        name: {"sha256": file_digest(path), "raw_content_committed": False}
        for name, path in paths.items()
    }
    result["result_sha256"] = digest({k: v for k, v in result.items() if k != "result_sha256"})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "result_sha256": result["result_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
