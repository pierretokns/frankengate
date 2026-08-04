"""Faithful preflight for trace-to-skill mechanisms.

This deliberately refuses to call a mechanism an intervention study when the
pinned implementation cannot produce a candidate from the pinned traces and
evaluate it on an independent task split.  It records executable source and
test evidence, while keeping content-bearing traces outside the repository.
"""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


HERMES_SELF_EVOLUTION_REVISION = "0a929e3aa20e15cf04dc7c28492a7d41a5139125"
GEPA_REVISION = "8b0ce6cd99a234f6b74daf37558a2ac0ce18f975"
REASONING_BANK_REVISION = "ed80611788292ea739f1effd31f16c53823b8a0d"
TRACE2SKILL_REVISION = "3d0b52a140f002a512930252b613c49048f7d5ac"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_revision(root: Path) -> str | None:
    try:
        return subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def run_tests(root: Path, timeout: int = 300) -> dict[str, Any]:
    candidate = Path("/private/tmp/hermes-py313/bin/python")
    executable = str(candidate) if candidate.is_file() else "python3"
    try:
        completed = subprocess.run(
            [executable, "-m", "pytest", "tests/", "-q", "--tb=no"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        lines = (completed.stdout + "\n" + completed.stderr).strip().splitlines()
        return {
            "status": "pass" if completed.returncode == 0 else "fail",
            "returncode": completed.returncode,
            "tail": lines[-4:],
        }
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "returncode": None, "tail": []}
    except OSError as exc:
        return {"status": "unavailable", "returncode": None, "tail": [str(exc)]}


def source_contract(root: Path) -> dict[str, Any]:
    evolve = root / "evolution/skills/evolve_skill.py"
    constraints = root / "evolution/core/constraints.py"
    evolve_text = evolve.read_text(encoding="utf-8")
    constraints_text = constraints.read_text(encoding="utf-8")
    ast.parse(evolve_text)
    ast.parse(constraints_text)
    # These are source-level facts, not inferred behavior.
    return {
        "evolve_sha256": sha256(evolve),
        "constraints_sha256": sha256(constraints),
        "uses_dspy_gepa": "dspy.GEPA(" in evolve_text,
        "uses_fitness_metric": "skill_fitness_metric" in evolve_text,
        "extracts_module_skill_text": "optimized_module.skill_text" in evolve_text,
        "validates_body_without_frontmatter": "validate_all(skill[\"body\"], \"skill\")" in evolve_text,
        "validator_requires_frontmatter": "has_frontmatter" in constraints_text and "skill_structure" in constraints_text,
        "holdout_evaluation_present": "holdout" in evolve_text and "baseline_scores" in evolve_text,
        "independent_trace_loader_present": "build_dataset_from_external" in evolve_text,
        "direct_live_skill_write_present": "write_text(evolved_full)" in evolve_text,
    }


def build_result(
    *,
    hermes_root: Path | None,
    gepa_root: Path | None,
    reasoning_bank_root: Path | None,
    trace2skill_root: Path | None,
) -> dict[str, Any]:
    mechanisms: dict[str, dict[str, Any]] = {}
    if hermes_root and hermes_root.is_dir():
        contract = source_contract(hermes_root)
        mechanisms["hermes_self_evolution"] = {
            "status": "typed_null_no_faithful_intervention",
            "pin": {"revision": HERMES_SELF_EVOLUTION_REVISION, "observed": git_revision(hermes_root)},
            "source_contract": contract,
            "tests": run_tests(hermes_root),
            "reason": (
                "The pinned runner exposes GEPA and holdout plumbing, but the reviewed source "
                "optimizes a DSPy module while extracting optimized_module.skill_text; the "
                "production validator is called on body-only text despite requiring frontmatter. "
                "No candidate was released or independently replayed from a natural trace in this run."
            ),
        }
    else:
        mechanisms["hermes_self_evolution"] = {"status": "unavailable_pinned_source"}

    for name, root, revision in (
        ("gepa_gskill", gepa_root, GEPA_REVISION),
        ("reasoning_bank", reasoning_bank_root, REASONING_BANK_REVISION),
        ("trace2skill", trace2skill_root, TRACE2SKILL_REVISION),
    ):
        if root and root.is_dir():
            mechanisms[name] = {
                "status": "source_available_no_faithful_natural_intervention",
                "pin": {"revision": revision, "observed": git_revision(root)},
                "reason": (
                    "Source is pinned, but this checkout/run has no independent natural-trace "
                    "candidate-generation plus held-out outcome harness for this mechanism."
                ),
            }
        else:
            mechanisms[name] = {"status": "unavailable_pinned_source"}

    return {
        "schema_version": "frankengate.skill-learning-faithful-preflight.v1",
        "experiment_date": "2026-07-30",
        "experiment_class": "faithful source-and-executable-preflight",
        "dataset": {
            "natural_trace_manifest": "configs/datasets/wisp-claude-code-sessions.json",
            "trace_content_committed": False,
            "independent_outcome_split_executed": False,
        },
        "mechanisms": mechanisms,
        "claim_boundary": [
            "A typed null is not evidence that a mechanism cannot work.",
            "Passing upstream unit tests does not establish skill benefit.",
            "No SKILL.md or MEMORY.md was activated or written by this preflight.",
            "The existing Trace2Skill Stage-0 result remains a separate one-task execution-safety smoke test.",
        ],
    }


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    result = build_result(
        hermes_root=Path("/private/tmp/hermes-self-evolution-pin-research"),
        gepa_root=Path("/private/tmp/gepa-v0.1.4-research"),
        reasoning_bank_root=None,
        trace2skill_root=Path("/private/tmp/trace2skill-3d0b52a-research"),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
