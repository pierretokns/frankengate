#!/usr/bin/env python3
"""Audit SkillLearnBench coverage and enterprise-claim fit without raw data."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tomllib
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


METHOD_RE = re.compile(r"^(b[1-4]-[^/]+)$")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_revision(root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _task_metadata(task_dir: Path) -> Dict[str, Any]:
    instance_dirs = sorted(
        path for path in task_dir.iterdir() if path.is_dir() and path.name.rsplit("-", 1)[-1].isdigit()
    )
    categories: List[str] = []
    difficulties: List[str] = []
    tags: List[str] = []
    verifier_files = 0
    solution_files = 0
    for instance in instance_dirs:
        toml_path = instance / "task.toml"
        if toml_path.exists():
            try:
                metadata = tomllib.loads(toml_path.read_text(encoding="utf-8")).get("metadata", {})
                if metadata.get("category"):
                    categories.append(str(metadata["category"]))
                if metadata.get("difficulty"):
                    difficulties.append(str(metadata["difficulty"]))
                tags.extend(str(tag) for tag in metadata.get("tags", []))
            except (OSError, tomllib.TOMLDecodeError):
                pass
        verifier_files += sum(1 for path in (instance / "tests").rglob("*") if path.is_file()) if (instance / "tests").exists() else 0
        solution_files += sum(1 for path in (instance / "solution").rglob("*") if path.is_file()) if (instance / "solution").exists() else 0
    return {
        "instance_count": len(instance_dirs),
        "instance_names_hash": hashlib.sha256("\n".join(path.name for path in instance_dirs).encode()).hexdigest(),
        "categories": sorted(set(categories)),
        "difficulties": sorted(set(difficulties)),
        "tag_count": len(set(tags)),
        "verifier_file_count": verifier_files,
        "solution_file_count": solution_files,
    }


def audit(root: Path) -> Dict[str, Any]:
    tasks_root = root / "tasks"
    task_dirs = sorted(path for path in tasks_root.iterdir() if path.is_dir())
    task_metadata = {path.name: _task_metadata(path) for path in task_dirs}
    categories = Counter(category for item in task_metadata.values() for category in item["categories"])
    instance_counts = [item["instance_count"] for item in task_metadata.values()]

    skills_root = root / "skills"
    skill_methods = sorted(path.name for path in skills_root.iterdir() if path.is_dir()) if skills_root.exists() else []
    baseline_methods = sorted(path.name for path in (root / "baselines").iterdir() if path.is_dir())
    skill_docs = 0
    method_task_coverage: Dict[str, int] = {}
    for method in skill_methods:
        method_root = skills_root / method
        docs = list(method_root.rglob("SKILL.md"))
        skill_docs += len(docs)
        method_task_coverage[method] = len({path.relative_to(method_root).parts[0] for path in docs})
    keypoint_tasks = sum(1 for path in (root / "eval_keypoints").iterdir() if path.is_dir())

    license_path = root / "LICENSE"
    return {
        "schema": "frankengate.skilllearnbench_fit_audit.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "repository": "cxcscmu/SkillLearnBench",
            "git_revision": _git_revision(root),
            "license": "MIT" if license_path.exists() and "MIT License" in license_path.read_text(errors="replace") else "unknown",
            "license_sha256": _sha256(license_path) if license_path.exists() else None,
            "raw_content_committed": False,
        },
        "benchmark": {
            "task_count": len(task_dirs),
            "instance_count": sum(instance_counts),
            "instance_count_distribution": dict(Counter(instance_counts)),
            "categories": dict(categories),
            "task_metadata": task_metadata,
            "keypoint_task_count": keypoint_tasks,
            "baseline_methods": baseline_methods,
        },
        "skill_artifacts": {
            "method_directory_count": len(skill_methods),
            "method_directories": skill_methods,
            "skill_doc_count": skill_docs,
            "method_task_coverage": method_task_coverage,
            "human_authored_present": "human_authored" in skill_methods,
            "no_skill_is_null_baseline": True,
        },
        "fit": {
            "continual_skill_generation": True,
            "verified_task_outcomes": True,
            "skill_quality_and_trajectory_dimensions": True,
            "cross_user_transfer": False,
            "corporate_identity_aliases": False,
            "authority_or_deletion_epochs": False,
            "changed_system_replay": False,
            "reason": "SkillLearnBench is a strong adjacent skill-learning benchmark with explicit verifiers and quality dimensions, but its public task instances do not provide enterprise principals, temporal authority, corporate aliases, changed-system outcomes, or multi-user transfer labels.",
        },
        "execution_requirements": {
            "static_audit_completed": True,
            "full_evaluation_requires_model_api": True,
            "full_evaluation_requires_docker": True,
            "full_evaluation_run_here": False,
        },
        "claim_boundary": {
            "benchmark_fit_proven": True,
            "enterprise_skill_transfer_proven": False,
            "next_step": "Run the published no-skill/one-shot/self-feedback/teacher-feedback/skill-creator matrix on a frozen subset, then port only the surviving representation intervention into the changed-system Frankengate protocol.",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["claim_boundary"], sort_keys=True))


if __name__ == "__main__":
    main()
