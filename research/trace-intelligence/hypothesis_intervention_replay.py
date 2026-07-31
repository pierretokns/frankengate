#!/usr/bin/env python3
"""Small family-disjoint intervention replay for hypothesis policies.

The task world is deterministic and opaque to the proposer.  It exists to test
the experiment protocol, not to claim real skill or memory improvement.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


@dataclass(frozen=True)
class Task:
    task_id: str
    family: str
    required_procedure: str


TRAIN = (
    Task("train-a", "alpha", "recover-after-tool-error"),
    Task("train-b", "alpha", "recover-after-tool-error"),
)
HOLDOUT = (
    Task("holdout-a", "beta", "recover-after-tool-error"),
    Task("holdout-b", "beta", "recover-after-tool-error"),
    Task("holdout-c", "beta", "no-retry"),
)


def propose(policy: str, training: tuple[Task, ...]) -> str | None:
    if policy == "none":
        return None
    if policy == "placebo":
        return "always-retry"
    procedures = {task.required_procedure for task in training}
    return "recover-after-tool-error" if len(procedures) == 1 else None


def evaluate(task: Task, procedure: str | None) -> bool:
    return procedure == task.required_procedure


def run() -> dict[str, object]:
    arms = []
    for policy in ("none", "placebo", "evidence_policy"):
        procedure = propose(policy, TRAIN)
        outcomes = [evaluate(task, procedure) for task in HOLDOUT]
        arms.append({
            "policy": policy,
            "candidate_present": procedure is not None,
            "holdout_successes": sum(outcomes),
            "holdout_tasks": len(outcomes),
            "holdout_success_rate": sum(outcomes) / len(outcomes),
            "family_overlap": False,
        })
    result: dict[str, object] = {
        "schema_version": "fg-hypothesis-intervention-replay-v1",
        "training_families": sorted({task.family for task in TRAIN}),
        "holdout_families": sorted({task.family for task in HOLDOUT}),
        "family_disjoint": True,
        "arms": arms,
        "human_adjudication": False,
        "real_trace_outcome": False,
        "causal_enterprise_claim": False,
        "raw_content_emitted": False,
    }
    result["result_sha256"] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
    return result


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, sort_keys=True))
