#!/usr/bin/env python3
"""Run a bounded, faithful AgentRx static-checker audit on bundled Tau traces.

This intentionally does not call the AgentRx LLM invariant generators or judge.
It executes the pinned upstream IR converter and checker against the upstream
static invariant artifact, then compares checker coverage with the bundled
ground-truth failure steps. The result is a compatibility/coverage receipt,
not a diagnosis-quality claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def step_matches(verify: Any, invariant: dict[str, Any], trajectory: dict[str, Any], step_pos: int) -> bool:
    """Use AgentRx's own trigger matcher; no local reimplementation."""
    matched, _reason, _substeps = verify._should_check_invariant_with_debug(
        invariant, trajectory, step_pos
    )
    return bool(matched)


def run(agent_root: Path, output: Path) -> dict[str, Any]:
    os.environ["SKIP_NL"] = "1"
    os.environ["DEBUG"] = "0"
    sys.path.insert(0, str(agent_root))
    from agentrx.invariants.checker import AllVerifier
    from agentrx.ir.trajectory_ir import load_trajectories, tau_bench_ir, validate_ir
    static_path = agent_root / "agentrx" / "invariants" / "out" / "static_tau.json"
    ground_truth_path = agent_root / "data" / "ground_truth" / "tau_ground_truth.json"
    trajectory_dir = agent_root / "trajectories" / "tau-retail"
    policy_path = agent_root / "data" / "policies" / "retail_policy.txt"

    static = json.loads(static_path.read_text(encoding="utf-8"))
    ground_truth = json.loads(ground_truth_path.read_text(encoding="utf-8"))
    ground_by_id = {str(row["trajectory_id"]): row for row in ground_truth}
    verifier = AllVerifier(
        invariants_path=str(static_path),
        policy_document_path=str(policy_path),
        client="azure",
    )

    rows: list[dict[str, Any]] = []
    for raw_path in sorted(trajectory_dir.glob("*.json")):
        raw = load_trajectories(str(raw_path))
        converted = tau_bench_ir(raw)
        trajectories = converted if isinstance(converted, list) else [converted]
        if len(trajectories) != 1:
            raise AssertionError(f"expected one trajectory in {raw_path}")
        trajectory = trajectories[0]
        validate_ir(trajectory)
        task_id = str(trajectory.get("trajectory_id"))
        gt = ground_by_id.get(task_id, {})
        failures = gt.get("failures", [])
        failure_steps = [int(f["step_number"]) for f in failures]
        matched_steps: list[int] = []
        violations = verifier.verify_trajectory(task_id=task_id, traj=trajectory)
        for pos, step in enumerate(trajectory.get("steps", [])):
            if any(
                step_matches(verifier, invariant, trajectory, pos)
                for invariant in verifier.invariants
            ):
                matched_steps.append(int(step.get("index", pos + 1)))
        covered_failures = [step for step in failure_steps if step in matched_steps]
        rows.append(
            {
                "source_file": raw_path.name,
                "task_id": task_id,
                "ir_valid": True,
                "step_count": len(trajectory.get("steps", [])),
                "ground_truth_failure_count": len(failures),
                "ground_truth_failure_steps": failure_steps,
                "static_triggered_step_count": len(matched_steps),
                "static_triggered_steps": matched_steps,
                "ground_truth_failure_steps_with_static_coverage": covered_failures,
                "static_checker_violation_count": len(violations),
                "static_checker_violation_steps": [int(v.step_index) for v in violations],
            }
        )

    result = {
        "schema_version": "frankengate-agentrx-independent-static-audit-v1",
        "upstream": {
            "repository": "microsoft/AgentRx",
            "source_path": str(agent_root),
            "source_commit": __import__("subprocess").check_output(
                ["git", "-C", str(agent_root), "rev-parse", "HEAD"], text=True
            ).strip(),
            "static_invariants_sha256": sha256(static_path),
            "ground_truth_sha256": sha256(ground_truth_path),
        },
        "protocol": {
            "domain": "tau",
            "trajectory_count": len(rows),
            "llm_generation_called": False,
            "llm_judge_called": False,
            "nl_checks_disabled": True,
            "dynamic_invariants_loaded": False,
            "checker": "pinned AgentRx AllVerifier.verify_trajectory",
        },
        "summary": {
            "ir_valid_count": sum(int(row["ir_valid"]) for row in rows),
            "ground_truth_failure_count": sum(row["ground_truth_failure_count"] for row in rows),
            "covered_ground_truth_failure_count": sum(
                len(row["ground_truth_failure_steps_with_static_coverage"]) for row in rows
            ),
            "static_checker_violation_count": sum(row["static_checker_violation_count"] for row in rows),
            "trajectories_with_any_static_trigger": sum(
                int(bool(row["static_triggered_steps"])) for row in rows
            ),
        },
        "episodes": rows,
        "claim_boundary": {
            "faithful_upstream_ir_and_static_checker_executed": True,
            "diagnosis_quality_established": False,
            "reason": "This is a bounded static-stage compatibility/coverage audit. Dynamic invariant generation, LLM judging, and blinded diagnosis labels were not run.",
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--agentrx-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.agentrx_root.resolve(), args.output)
    print(json.dumps(result["summary"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
