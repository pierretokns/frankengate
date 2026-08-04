#!/usr/bin/env python3
"""Replay a composite reviewed + generated SkillLearnBench arm."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from skilllearnbench_frontier_subset import _parse_events, _validate_answer, load_expected, run_arm


def run_composite(
    *,
    dataset_root: Path,
    composite_root: Path,
    task_ids: list[str],
    work_root: Path,
    model: str,
    timeout: int,
    existing_only: bool = False,
) -> dict[str, Any]:
    family = Path(task_ids[0]).parent if task_ids else Path(".")
    skill_root = composite_root / family
    if not skill_root.is_dir():
        raise ValueError(f"composite skill root not found: {skill_root}")
    tasks: list[dict[str, Any]] = []
    for task_id in task_ids:
        task_root = dataset_root / "tasks" / task_id
        if not task_root.is_dir():
            raise ValueError(f"task not found: {task_root}")
        if Path(task_id).parent != family:
            raise ValueError("all composite tasks must come from one skill family")
        arm = "composite-human-plus-b1"
        task_work_root = work_root / task_id.replace("/", "__")
        if existing_only:
            arm_root = task_work_root / arm
            if not ((arm_root / "codex-events.jsonl").exists() and (arm_root / "answer.json").exists()):
                tasks.append({"task_id": task_id, "arms": [], "status": "not_completed"})
                continue
        result = run_arm(
            task_root=task_root,
            arm=arm,
            work_root=task_work_root,
            skill_root=skill_root,
            model=model,
            timeout=timeout,
            expected=load_expected(task_root),
        )
        tasks.append({"task_id": task_id, "arms": [result]})
    return {
        "schema": "frankengate-skilllearnbench-frontier-composite-v1",
        "source": {
            "dataset": "cxcscmu/SkillLearnBench",
            "dataset_revision": subprocess.check_output(
                ["git", "-C", str(dataset_root), "rev-parse", "HEAD"], text=True
            ).strip(),
            "task_ids": task_ids,
            "composite_skill_root_sha256": _tree_hash(skill_root),
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
            "composite_utility_proven": False,
            "enterprise_transfer_proven": False,
            "reason": "Composite of two public skill artifacts on one family; no causal or changed-system outcome.",
        },
    }


def summarize_existing(
    *, dataset_root: Path, work_root: Path, task_ids: list[str], model: str
) -> dict[str, Any]:
    """Summarize a completed/partial run without rerunning frontier calls."""
    tasks: list[dict[str, Any]] = []
    for task_id in task_ids:
        task_root = dataset_root / "tasks" / task_id
        arm_root = work_root / task_id.replace("/", "__") / "composite-human-plus-b1"
        answer_path = arm_root / "answer.json"
        events_path = arm_root / "codex-events.jsonl"
        if answer_path.exists():
            expected = load_expected(task_root)
            answer = _validate_answer(answer_path, expected)
            usage, message_count = _parse_events(events_path.read_text(encoding="utf-8", errors="replace")) if events_path.exists() else ({}, 0)
            tasks.append({"task_id": task_id, "status": "completed", "answer": answer, "usage": usage, "agent_message_count": message_count, "events_sha256": hashlib.sha256(events_path.read_bytes()).hexdigest() if events_path.exists() else None})
        else:
            tasks.append({"task_id": task_id, "status": "timeout_or_missing_answer", "answer": {"answer_exists": False}, "usage": {}, "agent_message_count": 0, "events_sha256": hashlib.sha256(events_path.read_bytes()).hexdigest() if events_path.exists() else None})
    return {
        "schema": "frankengate-skilllearnbench-frontier-composite-v1",
        "source": {"dataset": "cxcscmu/SkillLearnBench", "dataset_revision": subprocess.check_output(["git", "-C", str(dataset_root), "rev-parse", "HEAD"], text=True).strip(), "task_ids": task_ids, "raw_content_committed": False},
        "harness": {"provider": "Codex subscription", "model": model, "docker_runner": False, "adaptation": "host-path portability probe; not the benchmark's Docker runner"},
        "tasks": tasks,
        "execution": {"completed_tasks": sum(task["status"] == "completed" for task in tasks), "incomplete_tasks": sum(task["status"] != "completed" for task in tasks), "full_paired_run": all(task["status"] == "completed" for task in tasks)},
        "claim_boundary": {"verifier_outcomes_measured": any(task["status"] == "completed" for task in tasks), "composite_utility_proven": False, "enterprise_transfer_proven": False, "reason": "Partial composite run summarized from existing work directories; one or more frontier calls timed out before an answer. No quality aggregate is claimed for the incomplete arm."},
    }


def merge_receipts(receipts: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge non-overlapping receipts without recomputing or imputing tasks."""
    if not receipts:
        raise ValueError("at least one receipt is required")
    merged = copy.deepcopy(receipts[0])
    tasks_by_id: dict[str, dict[str, Any]] = {}
    for receipt in receipts:
        for task in receipt.get("tasks", []):
            task_id = task["task_id"]
            if task_id in tasks_by_id:
                previous = tasks_by_id[task_id]
                previous_status = previous.get("status", "completed")
                current_status = task.get("status", "completed")
                if previous_status != "completed" and current_status == "completed":
                    tasks_by_id[task_id] = task
                    continue
                raise ValueError(f"duplicate completed task in receipts: {task_id}")
            tasks_by_id[task_id] = task
    merged["tasks"] = [tasks_by_id[task_id] for task_id in sorted(tasks_by_id)]
    source = merged.setdefault("source", {})
    source["task_ids"] = [task["task_id"] for task in merged["tasks"]]
    statuses = [task.get("status", "completed") for task in merged["tasks"]]
    merged["execution"] = {
        "completed_tasks": sum(status == "completed" for status in statuses),
        "incomplete_tasks": sum(status != "completed" for status in statuses),
        "full_paired_run": all(status == "completed" for status in statuses),
        "receipt_count": len(receipts),
    }
    boundary = merged.setdefault("claim_boundary", {})
    boundary["verifier_outcomes_measured"] = any(
        task.get("arms") or task.get("answer") for task in merged["tasks"]
    )
    boundary["composite_utility_proven"] = False
    boundary["enterprise_transfer_proven"] = False
    boundary["reason"] = (
        "Merged non-overlapping receipts from one public task family; "
        "no causal or changed-system outcome."
    )
    return merged


def _tree_hash(root: Path) -> str:
    entries: list[str] = []
    for path in sorted(path for path in root.rglob("*") if path.is_file()):
        entries.append(
            f"{path.relative_to(root)}\0{hashlib.sha256(path.read_bytes()).hexdigest()}"
        )
    return hashlib.sha256("\n".join(entries).encode()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--composite-root", type=Path, required=True)
    parser.add_argument("--task-ids", nargs="+", required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument(
        "--existing-only",
        action="store_true",
        help="Collect completed task outputs without starting missing frontier calls.",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summarize-existing", action="store_true")
    parser.add_argument(
        "--merge-receipt",
        action="append",
        type=Path,
        default=[],
        help="Merge one or more existing JSON receipts without rerunning frontier calls.",
    )
    args = parser.parse_args()
    if args.merge_receipt:
        receipts = [json.loads(path.read_text(encoding="utf-8")) for path in args.merge_receipt]
        result = merge_receipts(receipts)
    elif args.summarize_existing:
        result = summarize_existing(dataset_root=args.dataset_root.resolve(), work_root=args.work_root.resolve(), task_ids=args.task_ids, model=args.model)
    else:
        result = run_composite(
            dataset_root=args.dataset_root.resolve(),
            composite_root=args.composite_root.resolve(),
            task_ids=args.task_ids,
            work_root=args.work_root.resolve(),
        model=args.model,
        timeout=args.timeout,
        existing_only=args.existing_only,
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # Keep stdout bounded: frontier answers can contain large tool transcripts.
    print(
        json.dumps(
            {
                "execution": result.get("execution"),
                "tasks": [
                    {
                        "task_id": task["task_id"],
                        "status": task.get("status", "completed"),
                        "answer_present": bool(
                            task.get("answer")
                            or (task.get("arms") and task["arms"][0].get("answer"))
                        ),
                    }
                    for task in result["tasks"]
                ],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
