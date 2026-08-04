#!/usr/bin/env python3
"""Evaluate a governed trace-query readiness policy from redacted receipts.

The gate consumes the paired local planner experiment rather than querying a
live database. It deliberately treats pre-refresh and post-refresh phases as
separate decisions: a freshly bulk-loaded phase must fail readiness when its
plans or latency violate the frozen policy, while the post-ANALYZE phase may
pass only when authorization, plan, and latency checks all pass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping


SCHEMA_VERSION = "frankengate.postgres-planner-readiness-gate.v1"


class ReadinessError(ValueError):
    """Raised when a policy or paired planner receipt is malformed."""


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _digest(value: Mapping[str, Any]) -> str:
    body = dict(value)
    body.pop("result_sha256", None)
    return hashlib.sha256(_stable_json(body).encode("utf-8")).hexdigest()


def verify_result(result: Mapping[str, Any]) -> bool:
    digest = result.get("result_sha256")
    return isinstance(digest, str) and digest == _digest(result)


def _require_policy(policy: Mapping[str, Any]) -> tuple[list[str], list[str], dict[str, float]]:
    required = policy.get("required_queries")
    plans = policy.get("required_redacted_plan_queries")
    budgets = policy.get("p50_ms_budget")
    if not isinstance(required, list) or not required:
        raise ReadinessError("required queries are missing")
    if not isinstance(plans, list) or not plans:
        raise ReadinessError("required plan queries are missing")
    if not isinstance(budgets, Mapping):
        raise ReadinessError("latency budgets are missing")
    if any(query not in budgets for query in required):
        raise ReadinessError("every required query needs a latency budget")
    return (
        [str(query) for query in required],
        [str(query) for query in plans],
        {str(query): float(budgets[query]) for query in required},
    )


def evaluate_phase(
    paired: Mapping[str, Any],
    policy: Mapping[str, Any],
    *,
    phase: str,
) -> dict[str, Any]:
    if phase not in ("before", "after"):
        raise ReadinessError("phase must be before or after")
    required, required_plans, budgets = _require_policy(policy)
    queries = paired.get("queries")
    if not isinstance(queries, Mapping) or set(queries) != set(required):
        raise ReadinessError("paired receipt query set does not match policy")
    denial_key = f"denied_pre_ranking_candidates_{phase}"
    denial_count = paired.get(denial_key)
    required_denial_count = policy.get("required_denied_pre_ranking_candidates")
    if not isinstance(denial_count, int) or not isinstance(required_denial_count, int):
        raise ReadinessError("denial receipt is invalid")
    checks: dict[str, Any] = {
        "statistics_intervention_receipted": paired.get("intervention")
        == policy.get("statistics_intervention"),
        "denied_pre_ranking_candidates_zero": denial_count
        == required_denial_count,
        "queries": {},
    }
    for query in required:
        row = queries[query]
        if not isinstance(row, Mapping):
            raise ReadinessError(f"query receipt is invalid: {query}")
        p50_key = f"{phase}_p50_ms"
        p50 = row.get(p50_key)
        if not isinstance(p50, (int, float)) or isinstance(p50, bool):
            raise ReadinessError(f"p50 receipt is invalid: {query}")
        plan_key = f"{phase}_plan_signature"
        signature = row.get(plan_key)
        plan_present = isinstance(signature, list) and bool(signature)
        checks["queries"][query] = {
            "p50_ms": p50,
            "p50_budget_ms": budgets[query],
            "p50_within_budget": float(p50) <= budgets[query],
            "plan_required": query in required_plans,
            "redacted_plan_present": plan_present if query in required_plans else None,
            "plan_signature_changed": row.get("plan_signature_changed"),
        }
    checks["all_query_latency_budgets"] = all(
        item["p50_within_budget"] for item in checks["queries"].values()
    )
    checks["all_required_redacted_plans"] = all(
        checks["queries"][query]["redacted_plan_present"]
        for query in required_plans
    )
    passed = all(
        (
            checks["statistics_intervention_receipted"],
            checks["denied_pre_ranking_candidates_zero"],
            checks["all_query_latency_budgets"],
            checks["all_required_redacted_plans"],
        )
    )
    return {
        "phase": phase,
        "status": "ready" if passed else "not_ready",
        "checks": checks,
        "claim_boundary": policy["claim_boundary"],
    }


def evaluate(paired: Mapping[str, Any], policy: Mapping[str, Any]) -> dict[str, Any]:
    before = evaluate_phase(paired, policy, phase="before")
    after = evaluate_phase(paired, policy, phase="after")
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "policy_id": policy.get("policy_id"),
        "policy_sha256": hashlib.sha256(_stable_json(policy).encode("utf-8")).hexdigest(),
        "source_result_sha256": paired.get("result_sha256"),
        "paired_unit": paired.get("paired_unit"),
        "before": before,
        "after": after,
        "decision": {
            "fresh_bulk_load_must_fail": before["status"] == "not_ready",
            "post_statistics_refresh_ready": after["status"] == "ready",
            "release_gate": before["status"] == "not_ready" and after["status"] == "ready",
        },
        "claim_boundary": [
            "This is a deterministic readiness check over one local PostgreSQL paired receipt.",
            "It does not establish Aurora failover, replica, PITR, scale, or managed-extension behavior.",
            "A ready result permits bounded latency certification only; it does not authorize a query or bypass RLS.",
        ],
    }
    result["result_sha256"] = _digest(result)
    return result


def _summary(result: Mapping[str, Any]) -> str:
    decision = result["decision"]
    return f"""# Governed trace-query planner readiness gate

The frozen local policy evaluates the same four-query paired PostgreSQL
receipt before and after the recorded statistics refresh.

| phase | status | denied candidates | latency budgets | required plans |
| --- | --- | --- | --- | --- |
| before refresh | {result['before']['status']} | {result['before']['checks']['denied_pre_ranking_candidates_zero']} | {result['before']['checks']['all_query_latency_budgets']} | {result['before']['checks']['all_required_redacted_plans']} |
| after refresh | {result['after']['status']} | {result['after']['checks']['denied_pre_ranking_candidates_zero']} | {result['after']['checks']['all_query_latency_budgets']} | {result['after']['checks']['all_required_redacted_plans']} |

The release gate is **{'passed' if decision['release_gate'] else 'not passed'}**:
fresh bulk-load receipts must fail readiness, while the post-refresh receipt
must pass all authorization, redacted-plan, and frozen latency checks.

This is local PostgreSQL readiness evidence only. It does not claim Aurora
failover, replication, PITR, RDS Proxy, storage scale, or production SLOs.

Machine-readable result: `experiments/results/planner-readiness-gate-2026-08-02.json`.
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--paired", type=Path, required=True)
    parser.add_argument("--policy", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()
    paired = json.loads(args.paired.read_text(encoding="utf-8"))
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    result = evaluate(paired, policy)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.summary.write_text(_summary(result), encoding="utf-8")
    print(json.dumps({"status": result["decision"], "result_sha256": result["result_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
