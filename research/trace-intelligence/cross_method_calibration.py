#!/usr/bin/env python3
"""Calibrate independent experiment receipts without pooling unlike metrics.

This is an evidence audit, not a meta-analysis of efficacy.  It consumes only
committed aggregate receipts, keeps task-level content out of the output, and
refuses to fabricate cost, latency, or power values that a source receipt did
not measure.  The purpose is to make the remaining power/cost/null gate
concrete before any mechanism can be integrated into Frankengate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-cross-method-calibration-v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _sample_size(receipt: dict[str, Any]) -> int | None:
    for parent, keys in (
        (receipt.get("protocol"), ("heldout_tasks", "task_count", "episodes")),
        (receipt.get("dataset"), ("task_count", "episodes")),
        (receipt.get("outcome"), ("paired_rows",)),
    ):
        if isinstance(parent, dict):
            for key in keys:
                value = parent.get(key)
                if isinstance(value, list):
                    return len(value)
                if isinstance(value, int) and value > 0:
                    return value
    summary = receipt.get("summary")
    if isinstance(summary, dict):
        episode_counts = [
            item.get("episodes")
            for item in summary.values()
            if isinstance(item, dict) and isinstance(item.get("episodes"), int)
        ]
        if episode_counts:
            return max(episode_counts)
    return None


def _latency_ms(receipt: dict[str, Any]) -> dict[str, float] | None:
    summary = receipt.get("summary")
    values: list[float] = []
    if isinstance(summary, dict):
        for item in summary.values():
            if not isinstance(item, dict):
                continue
            mean_ms = _number(item.get("mean_elapsed_ms"))
            if mean_ms is not None:
                values.append(mean_ms)
    if values:
        return {
            "arm_mean_ms_min": min(values),
            "arm_mean_ms_max": max(values),
            "arm_mean_ms_mean": statistics.mean(values),
        }
    elapsed_seconds = _number(receipt.get("elapsed_seconds"))
    count = _sample_size(receipt)
    if elapsed_seconds is not None and count:
        return {"whole_run_mean_ms": elapsed_seconds * 1000.0 / count}
    return None


def _paired_power(deltas: list[float]) -> dict[str, Any]:
    if not deltas:
        return {"pairs": 0, "observed_mean_delta": None, "paired_sd": None, "estimated_pairs_for_80pct_normal_power": None}
    mean_delta = statistics.mean(deltas)
    sd = statistics.stdev(deltas) if len(deltas) > 1 else 0.0
    effect = abs(mean_delta)
    required = (
        math.ceil(((1.96 + 0.84) * sd / effect) ** 2)
        if effect > 0 and sd > 0
        else None
    )
    return {
        "pairs": len(deltas),
        "observed_mean_delta": mean_delta,
        "paired_sd": sd,
        "estimated_pairs_for_80pct_normal_power": required,
    }


def _rho_deltas(receipt: dict[str, Any]) -> list[float]:
    rows = receipt.get("outcome", {}).get("paired_rows", [])
    return [float(row["delta"]) for row in rows if isinstance(row, dict) and isinstance(row.get("delta"), (int, float))]


def _bird_deltas(receipt: dict[str, Any], left: str, right: str) -> list[float]:
    episodes = receipt.get("episodes", [])
    by_task: dict[str, dict[str, float]] = {}
    for row in episodes:
        if not isinstance(row, dict) or row.get("arm") not in {left, right}:
            continue
        task = row.get("task_hash")
        if not isinstance(task, str):
            continue
        by_task.setdefault(task, {})[str(row["arm"])] = 1.0 if row.get("exact") is True else 0.0
    return [values[left] - values[right] for values in by_task.values() if left in values and right in values]


def _null_taxonomy(disposition: str, receipt: dict[str, Any], paired: dict[str, Any] | None) -> str:
    if disposition in {"provider_unavailable", "incompatible_or_incomplete", "blocked_artifact"}:
        return "protocol_or_provider_failure"
    if disposition in {"mechanics_only", "stored_trace_assertion_only", "structural_only", "fixture_only", "shadow_backend_only", "shadow_review_only", "not_selected"}:
        return "mechanics_or_infrastructure_only"
    if disposition == "quarantined_negative_utility" or disposition == "quarantined_negative_bounded_utility":
        return "negative_utility"
    if disposition in {"quarantined_no_lift", "quarantined_utility_unproven"}:
        comparison = receipt.get("comparison", {})
        if isinstance(comparison, dict) and comparison:
            text = json.dumps(comparison, sort_keys=True).lower()
            if "zero" in text or "0.0" in text:
                return "zero_headroom_or_no_lift"
        if paired and paired.get("observed_mean_delta") == 0:
            return "zero_headroom_or_no_lift"
        return "underpowered_or_unproven"
    return "unclassified"


def calibrate(result_dir: Path, promotion_path: Path) -> dict[str, Any]:
    promotion = json.loads(promotion_path.read_text(encoding="utf-8"))
    methods: list[dict[str, Any]] = []
    missing: list[str] = []
    for row in promotion.get("rows", []):
        receipt_name = row["receipt"]
        path = result_dir / receipt_name
        if not path.exists():
            missing.append(receipt_name)
            continue
        receipt = json.loads(path.read_text(encoding="utf-8"))
        paired: dict[str, Any] | None = None
        deltas: list[float] = []
        if row["name"] == "rho_powered_candidate":
            deltas = _rho_deltas(receipt)
            paired = _paired_power(deltas)
        elif row["name"] == "skillgen_bird":
            # The SkillGen receipt is a compact summary; its held-out arm is
            # paired in the committed BIRD factorial receipt, not this receipt.
            bird_path = result_dir / "bird-sql-skill-factorial-powered-2026-07-31.json"
            if bird_path.exists():
                bird = json.loads(bird_path.read_text(encoding="utf-8"))
                deltas = _bird_deltas(bird, "trace_mined_procedure", "no_skill")
                paired = _paired_power(deltas)
        latency = _latency_ms(receipt)
        methods.append({
            "name": row["name"],
            "disposition": row["disposition"],
            "null_taxonomy": _null_taxonomy(row["disposition"], receipt, paired),
            "receipt": receipt_name,
            "receipt_sha256": sha256(path),
            "sample_size": _sample_size(receipt),
            "paired_effect": paired,
            "latency": latency,
            "cost": {
                "status": "not_measured",
                "reason": "No comparable token/currency accounting is present in the committed receipt.",
            },
        })
    if missing:
        raise ValueError(f"missing promotion receipts: {sorted(missing)}")
    taxonomy: dict[str, int] = {}
    for method in methods:
        key = method["null_taxonomy"]
        taxonomy[key] = taxonomy.get(key, 0) + 1
    with_pairs = [method for method in methods if method["paired_effect"] and method["paired_effect"]["pairs"]]
    with_latency = [method for method in methods if method["latency"] is not None]
    changed_agent_path = result_dir / "changed-agent-outcome-bird-2026-08-02.json"
    changed_agent = None
    if changed_agent_path.exists():
        changed_agent_receipt = json.loads(changed_agent_path.read_text(encoding="utf-8"))
        changed_agent = {
            "receipt": changed_agent_path.name,
            "receipt_sha256": sha256(changed_agent_path),
            "changed_agent_future_task_outcome_measured": bool(
                changed_agent_receipt.get("claim_boundary", {}).get(
                    "changed_agent_future_task_outcome_measured"
                )
            ),
            "exact_mean_delta": changed_agent_receipt.get("outcome", {})
            .get("exact_execution", {})
            .get("mean_delta"),
            "cross_user_enterprise_transfer_measured": bool(
                changed_agent_receipt.get("claim_boundary", {}).get(
                    "cross_user_enterprise_transfer_measured"
                )
            ),
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "inputs": {
            "promotion_audit": promotion_path.name,
            "promotion_audit_sha256": sha256(promotion_path),
            "promotion_rows": len(methods),
        },
        "methods": sorted(methods, key=lambda row: row["name"]),
        "coverage": {
            "methods": len(methods),
            "paired_effect_measured": len(with_pairs),
            "latency_measured": len(with_latency),
            "comparable_cost_measured": 0,
            "typed_null_taxonomy": len(methods),
            "changed_agent_outcome_receipts": 1 if changed_agent else 0,
            "power_estimate_is_planning_only": True,
        },
        "additional_outcomes": {
            "changed_agent": changed_agent,
        },
        "null_taxonomy_counts": dict(sorted(taxonomy.items())),
        "claim_boundary": {
            "cross_method_efficacy_pooling": False,
            "automatic_integration_authorized": False,
            "no_cost_fabrication": True,
            "reason": "Receipts use incompatible tasks, metrics, models, and horizons; this audit reports coverage and typed nulls, not a pooled effect or universal ranking.",
            "remaining": [
                "repeat-seed powered cohorts with predeclared outcomes",
                "comparable token/currency accounting and latency under the same harness budget",
                "independent changed-agent and enterprise-level prospective outcomes",
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result-dir", type=Path, required=True)
    parser.add_argument("--promotion", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = calibrate(args.result_dir, args.promotion)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["coverage"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
