#!/usr/bin/env python3
"""Replay a SkillLearnBench task after a deterministic product rename.

This is a public changed-data proxy, not an enterprise or causal cohort. The
mutation changes the target product's user-facing name in the prompt and
artifacts while preserving the published answer IDs and verifier.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from skilllearnbench_frontier_subset import load_expected, run_arm


def _replace_tree(root: Path, old: str, new: str) -> None:
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        path.write_text(text.replace(old, new), encoding="utf-8")


def prepare_changed_task(
    *, dataset_root: Path, task_id: str, changed_root: Path, old_name: str, new_name: str
) -> Path:
    source = dataset_root / "tasks" / task_id
    target = changed_root / "tasks" / task_id
    if not source.is_dir():
        raise ValueError(f"task not found: {source}")
    if target.exists():
        shutil.rmtree(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, target)
    _replace_tree(target / "environment", old_name, new_name)
    old_file = target / "environment" / "DATA" / "products" / f"{old_name}.json"
    new_file = target / "environment" / "DATA" / "products" / f"{new_name}.json"
    if old_file.exists():
        old_file.rename(new_file)
    return target


def run_changed_data(
    *,
    dataset_root: Path,
    task_id: str,
    changed_root: Path,
    work_root: Path,
    arms: list[tuple[str, Path | None]],
    model: str,
    timeout: int,
    old_name: str,
    new_name: str,
) -> dict[str, Any]:
    task_root = prepare_changed_task(
        dataset_root=dataset_root,
        task_id=task_id,
        changed_root=changed_root,
        old_name=old_name,
        new_name=new_name,
    )
    expected = load_expected(task_root)
    results: list[dict[str, Any]] = []
    for arm, skill_root in arms:
        results.append(
            run_arm(
                task_root=task_root,
                arm=arm,
                work_root=work_root,
                skill_root=skill_root,
                model=model,
                timeout=timeout,
                expected=expected,
            )
        )
    changed_hash = hashlib.sha256(
        json.dumps(
            {
                "task_id": task_id,
                "old_name": old_name,
                "new_name": new_name,
                "data_hash": _tree_hash(task_root / "environment" / "DATA"),
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    return {
        "schema": "frankengate-skilllearnbench-changed-data-frontier-v1",
        "source": {
            "dataset": "cxcscmu/SkillLearnBench",
            "task_id": task_id,
            "old_name": old_name,
            "new_name": new_name,
            "changed_fixture_sha256": changed_hash,
            "raw_content_committed": False,
        },
        "harness": {
            "provider": "Codex subscription",
            "model": model,
            "docker_runner": False,
            "adaptation": "host-path portability probe; not the benchmark Docker runner",
        },
        "arms": results,
        "claim_boundary": {
            "verifier_outcomes_measured": True,
            "changed_data_proxy_only": True,
            "enterprise_transfer_proven": False,
            "causal_skill_effect_proven": False,
            "reason": "Public deterministic product rename; no user identity, independent outcome, or authorized enterprise cohort.",
        },
    }


def _tree_hash(root: Path) -> str:
    entries = []
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        entries.append(f"{path.relative_to(root)}\0{hashlib.sha256(path.read_bytes()).hexdigest()}")
    return hashlib.sha256("\n".join(entries).encode()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--changed-root", type=Path, required=True)
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--human-skill-root", type=Path, required=True)
    parser.add_argument("--composite-skill-root", type=Path, required=True)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--old-name", default="ContentForce")
    parser.add_argument("--new-name", default="ContentHub")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_changed_data(
        dataset_root=args.dataset_root.resolve(),
        task_id=args.task_id,
        changed_root=args.changed_root.resolve(),
        work_root=args.work_root.resolve(),
        arms=[
            ("none", None),
            ("human_authored", args.human_skill_root.resolve()),
            ("composite-human-plus-b1", args.composite_skill_root.resolve()),
        ],
        model=args.model,
        timeout=args.timeout,
        old_name=args.old_name,
        new_name=args.new_name,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({r["arm"]: r["answer"] for r in result["arms"]}, sort_keys=True))


if __name__ == "__main__":
    main()
