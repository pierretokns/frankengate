#!/usr/bin/env python3
"""Run the Codex host-harness probe over multiple held-out task instances."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from skilllearnbench_frontier_subset import load_expected, resolve_skill_root, run_arm


def run_family(
    *,
    dataset_root: Path,
    task_ids: list[str],
    arms: list[str],
    work_root: Path,
    model: str,
    timeout: int,
) -> dict[str, Any]:
    skill_base = dataset_root / "skills"
    tasks: list[dict[str, Any]] = []
    for task_id in task_ids:
        task_root = dataset_root / "tasks" / task_id
        if not task_root.is_dir():
            raise ValueError(f"task not found: {task_root}")
        task_work_root = work_root / task_id.replace("/", "__")
        expected = load_expected(task_root)
        arm_results: list[dict[str, Any]] = []
        for arm in arms:
            skill_root = None if arm == "none" else resolve_skill_root(skill_base, arm, task_id)
            if skill_root is not None and not skill_root.exists():
                raise ValueError(f"skill path not found for {arm}: {skill_root}")
            arm_results.append(
                run_arm(
                    task_root=task_root,
                    arm=arm,
                    work_root=task_work_root,
                    skill_root=skill_root,
                    model=model,
                    timeout=timeout,
                    expected=expected,
                )
            )
        tasks.append({"task_id": task_id, "arms": arm_results})
    return {
        "schema": "frankengate-skilllearnbench-frontier-family-v1",
        "source": {
            "dataset": "cxcscmu/SkillLearnBench",
            "dataset_revision": subprocess.check_output(
                ["git", "-C", str(dataset_root), "rev-parse", "HEAD"], text=True
            ).strip(),
            "task_ids": task_ids,
            "raw_content_committed": False,
        },
        "harness": {
            "provider": "Codex subscription",
            "model": model,
            "docker_runner": False,
            "adaptation": "host-path portability probe; not the benchmark's Docker runner",
        },
        "tasks": tasks,
        "claim_boundary": {
            "verifier_outcomes_measured": True,
            "skill_learning_causal_effect_proven": False,
            "enterprise_transfer_proven": False,
            "reason": "Three public instances from one task family and a host-harness adaptation; directional within-family evidence only.",
        },
        "receipt_input_sha256": hashlib.sha256(
            json.dumps({"task_ids": task_ids, "arms": arms, "model": model}, sort_keys=True).encode()
        ).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--task-ids", nargs="+", required=True)
    parser.add_argument("--arms", nargs="+", default=["none", "human_authored"])
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_family(
        dataset_root=args.dataset_root.resolve(),
        task_ids=args.task_ids,
        arms=args.arms,
        work_root=args.work_root.resolve(),
        model=args.model,
        timeout=args.timeout,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                task["task_id"]: {arm["arm"]: arm["answer"] for arm in task["arms"]}
                for task in result["tasks"]
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
