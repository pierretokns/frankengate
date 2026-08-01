#!/usr/bin/env python3
"""Freeze a comparable SkillLearnBench method matrix before execution."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, List


METHODS = (
    "none",
    "human_authored",
    "b1-one-shot-claude-sonnet-4-6",
    "b2-self-feedback-claude-sonnet-4-6",
    "b3-teacher-feedback-claude-sonnet-4-6",
    "b4-skill-creator-claude-sonnet-4-6",
)


def _hash_lines(values: Iterable[str]) -> str:
    return hashlib.sha256("\n".join(sorted(values)).encode("utf-8")).hexdigest()


def _tree_hash(root: Path) -> str:
    entries: List[str] = []
    if not root.exists():
        return _hash_lines(entries)
    for path in sorted(path for path in root.rglob("*") if path.is_file()):
        relative = str(path.relative_to(root))
        entries.append(f"{relative}\0{hashlib.sha256(path.read_bytes()).hexdigest()}")
    return _hash_lines(entries)


def build_matrix(root: Path) -> dict[str, Any]:
    task_root = root / "tasks"
    tasks = sorted(path.name for path in task_root.iterdir() if path.is_dir())
    if not tasks:
        raise ValueError("SkillLearnBench task root is empty")
    task_hash = _hash_lines(tasks)
    skills_root = root / "skills"
    rows = []
    missing: dict[str, list[str]] = {}
    for method in METHODS:
        method_root = skills_root / method
        if method == "none":
            rows.append(
                {
                    "method": method,
                    "task_count": len(tasks),
                    "task_set_sha256": task_hash,
                    "artifact_tree_sha256": None,
                    "artifact_task_count": 0,
                    "null_baseline": True,
                }
            )
            continue
        present = sorted(path.name for path in method_root.iterdir() if path.is_dir()) if method_root.exists() else []
        missing[method] = sorted(set(tasks) - set(present))
        rows.append(
            {
                "method": method,
                "task_count": len(tasks),
                "task_set_sha256": task_hash,
                "artifact_tree_sha256": _tree_hash(method_root),
                "artifact_task_count": len(set(present) & set(tasks)),
                "null_baseline": False,
            }
        )
    complete = not any(missing.values())
    return {
        "schema": "frankengate.skilllearnbench_method_matrix.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {"repository": "cxcscmu/SkillLearnBench", "raw_content_committed": False},
        "design": {
            "method_count": len(METHODS),
            "methods": list(METHODS),
            "task_count": len(tasks),
            "task_set_sha256": task_hash,
            "same_task_set_across_methods": all(row["task_set_sha256"] == task_hash for row in rows),
            "same_solving_model": "claude-sonnet-4-6" in " ".join(METHODS),
            "task_disjoint_confirmation_required": True,
        },
        "methods": rows,
        "missing_task_directories": missing,
        "execution_requirements": {
            "requires_docker": True,
            "requires_anthropic_api": True,
            "requires_openai_judge_api_for_metrics": True,
            "preflight_only": True,
        },
        "claim_boundary": {
            "matrix_ready": complete,
            "outcome_measured": False,
            "enterprise_transfer_proven": False,
            "reason": "This freezes a same-task method comparison; it does not execute agents or establish skill utility.",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_matrix(args.root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["claim_boundary"], sort_keys=True))


if __name__ == "__main__":
    main()
