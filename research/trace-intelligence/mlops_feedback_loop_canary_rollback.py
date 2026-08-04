#!/usr/bin/env python3
"""Deterministic MLOps release/monitor/rollback lifecycle experiment.

This is an architecture-neutral mechanics test.  It uses a sealed synthetic
outcome fixture to exercise the full loop, including the path that cannot be
observed when every real candidate is quarantined: release after a verified
positive result, canary monitoring, regression detection, and rollback to the
previous artifact.  It makes no model, database, or network calls and is not
an efficacy result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def monitor_window(window: dict, *, min_lift: float, max_invalid_delta: int) -> dict:
    baseline = float(window["baseline_success_rate"])
    candidate = float(window["candidate_success_rate"])
    invalid_delta = int(window["candidate_invalid_actions"]) - int(window["baseline_invalid_actions"])
    security_violation = bool(window.get("security_violation", False))
    positive = candidate - baseline >= min_lift and invalid_delta <= max_invalid_delta
    return {
        "window_id": window["window_id"],
        "success_lift": round(candidate - baseline, 6),
        "invalid_delta": invalid_delta,
        "security_violation": security_violation,
        "healthy": bool(positive and not security_violation),
    }


def run() -> dict:
    previous = {"artifact_id": "skill-v0", "sha256": digest("skill-v0")}
    candidate = {"artifact_id": "skill-v1", "sha256": digest("skill-v1")}
    admission = {
        "candidate_success": 8,
        "baseline_success": 5,
        "placebo_success": 6,
        "candidate_invalid_actions": 0,
        "baseline_invalid_actions": 0,
        "placebo_invalid_actions": 0,
        "verification_passed": True,
    }
    release_predicate = (
        admission["verification_passed"]
        and admission["candidate_success"] > admission["baseline_success"]
        and admission["candidate_success"] >= admission["placebo_success"]
        and admission["candidate_invalid_actions"] <= admission["baseline_invalid_actions"]
        and admission["candidate_invalid_actions"] <= admission["placebo_invalid_actions"]
    )
    if not release_predicate:
        raise AssertionError("fixture must satisfy the predeclared release predicate")

    windows = [
        {
            "window_id": "canary-1",
            "baseline_success_rate": 0.60,
            "candidate_success_rate": 0.70,
            "baseline_invalid_actions": 1,
            "candidate_invalid_actions": 1,
        },
        {
            "window_id": "canary-2",
            "baseline_success_rate": 0.60,
            "candidate_success_rate": 0.40,
            "baseline_invalid_actions": 1,
            "candidate_invalid_actions": 2,
        },
    ]
    observations = [monitor_window(w, min_lift=0.0, max_invalid_delta=0) for w in windows]
    rollback_reason = None
    if not observations[0]["healthy"]:
        rollback_reason = "first_canary_unhealthy"
    elif not observations[1]["healthy"]:
        rollback_reason = "second_canary_unhealthy"
    active_after_rollback = previous if rollback_reason else candidate

    result = {
        "schema_version": "frankengate-mlops-feedback-canary-rollback-v1",
        "mode": "deterministic_sealed_mechanics_fixture",
        "network_or_model_calls": False,
        "artifacts": {"previous": previous, "candidate": candidate, "active_after_rollback": active_after_rollback},
        "admission": admission,
        "release": {
            "predicate": "verified candidate success > baseline, candidate >= placebo, no validity regression",
            "passed": release_predicate,
            "canary_percent_initial": 10,
        },
        "monitor": {
            "rule": "candidate lift >= 0 and candidate invalid-action delta <= 0; any security violation fails",
            "windows": observations,
            "all_windows_healthy": all(item["healthy"] for item in observations),
        },
        "rollback": {
            "triggered": rollback_reason is not None,
            "reason": rollback_reason,
            "restored_previous": active_after_rollback["sha256"] == previous["sha256"],
            "canary_percent_after": 0 if rollback_reason else 10,
        },
        "stages": {
            "collect": "complete", "segment": "complete", "cluster": "complete",
            "retrieve": "complete", "propose": "complete", "replay": "complete",
            "evaluate": "complete", "release": "complete", "monitor": "complete",
            "rollback": "complete",
        },
        "claim_boundary": {
            "mechanics_passed": True,
            "causal_model_utility_confirmed": False,
            "production_release_authorized": False,
            "reason": "Synthetic fixture validates lifecycle state transitions only; no model or user outcome is measured.",
        },
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"release": result["release"], "rollback": result["rollback"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
