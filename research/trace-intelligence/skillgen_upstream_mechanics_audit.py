#!/usr/bin/env python3
"""Bounded, no-network audit of the upstream SkillGen mechanics.

This is deliberately not a benchmark.  It imports the pinned upstream source,
checks that the Python tree compiles, verifies its on-disk skill contract, and
exercises the paired before/after accounting with deterministic trajectories.
No provider, LLM, benchmark, or internet call is made.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(cmd: list[str], *, cwd: Path) -> dict:
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    return {
        "command": cmd,
        "returncode": proc.returncode,
        "stdout_sha256": hashlib.sha256(proc.stdout.encode()).hexdigest(),
        "stderr_sha256": hashlib.sha256(proc.stderr.encode()).hexdigest(),
        "stdout_bytes": len(proc.stdout.encode()),
        "stderr_bytes": len(proc.stderr.encode()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    upstream = args.upstream.resolve()
    sys.path.insert(0, str(upstream))

    source_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=upstream, text=True
    ).strip()
    py_compile = run(
        [sys.executable, "-m", "compileall", "-q", str(upstream)], cwd=upstream
    )

    # Importing the modules also catches missing absolute imports that compileall
    # cannot see.  No model/client is constructed by these imports.
    import models  # type: ignore
    import skill_store  # type: ignore
    import router  # type: ignore
    import effectiveness  # type: ignore
    from models import CandidateSkill, SkillItem, SkillStatus, TaskInstance, TaskType, Trajectory

    import_results = {}
    for name in ("models", "skill_store", "router", "effectiveness"):
        module = sys.modules[name]
        import_results[name] = {"file": str(Path(module.__file__).resolve()),
                                "sha256": sha256(Path(module.__file__).resolve())}

    # Skill persistence contract: candidate promotion, JSON round-trip, and
    # executable helper emission.  The helper is harmless and deterministic.
    candidate = CandidateSkill(
        candidate_id="candidate-audit",
        analysis_id="analysis-audit",
        body="## When to use\nUse for deterministic arithmetic.\n",
        contextual_abstract="deterministic arithmetic",
        scripts=["def add_one(x):\n    return int(x) + 1"],
    )
    with tempfile.TemporaryDirectory(prefix="skillgen-audit-") as tmp:
        skill = skill_store.finalize_skill(candidate, tmp, dataset_id="ds-audit", task_name="arithmetic")
        loaded = skill_store.load_skill(tmp, skill.skill_id)
        helper_path = Path(tmp) / f"{skill.skill_id}_helpers.py"
        persistence = {
            "candidate_promoted": skill.status == SkillStatus.ACTIVE,
            "round_trip_id_equal": loaded.skill_id == skill.skill_id,
            "round_trip_body_equal": loaded.body == skill.body,
            "round_trip_scripts_equal": loaded.scripts == skill.scripts,
            "helper_emitted": helper_path.exists(),
            "helper_sha256": sha256(helper_path) if helper_path.exists() else None,
        }

    # Paired effectiveness accounting: replace the trajectory collector with a
    # deterministic fixture.  This validates the upstream gate and its repair /
    # regression / net-gain buckets without pretending to measure model quality.
    target = [TaskInstance("t1", "repair me"), TaskInstance("t2", "still fail")]
    boundary = [TaskInstance("b1", "preserve me"), TaskInstance("b2", "preserve me too")]
    all_instances = target + boundary
    baseline = {
        "t1": Trajectory("bt1", "t1", {}, [], "bad", success=False),
        "t2": Trajectory("bt2", "t2", {}, [], "bad", success=False),
        "b1": Trajectory("bb1", "b1", {}, [], "good", success=True),
        "b2": Trajectory("bb2", "b2", {}, [], "good", success=True),
    }

    original_collect = effectiveness.collect_trajectories

    def fake_collect(instances, task_type, *, skill=None, config=None, progress_desc=None):
        out = []
        for inst in instances:
            base = baseline[inst.instance_id]
            succeeded = bool(base.success)
            # The hypothetical skill repairs t1 but regresses b2.  Expected net
            # gain is zero, so the strict positive gate must reject it.
            if skill is not None and inst.instance_id == "t1":
                succeeded = True
            if skill is not None and inst.instance_id == "b2":
                succeeded = False
            out.append(Trajectory(
                f"st-{inst.instance_id}", inst.instance_id, {}, [],
                "good" if succeeded else "bad", success=succeeded,
            ))
        return out

    try:
        effectiveness.collect_trajectories = fake_collect
        eff, _ = effectiveness.verify_effectiveness(
            SkillItem("skill-audit", "body", "abstract"),
            target,
            boundary,
            TaskType.BINARY,
            baseline_cache=baseline,
            router_model=None,
            min_net_gain_abs=1,
        )
    finally:
        effectiveness.collect_trajectories = original_collect

    paired = {
        "paired_n": eff.paired_n,
        "repair_count": eff.repair_count,
        "regression_count": eff.regression_count,
        "net_gain": eff.net_gain,
        "passed": eff.passed,
        "expected": {"paired_n": 4, "repair_count": 1, "regression_count": 1,
                     "net_gain": 0, "passed": False},
    }
    paired["matches_expected"] = all(paired[k] == paired["expected"][k] for k in paired["expected"])

    # Router safety contract: upstream documents fail-closed behavior.  Force
    # the LLM call to fail and verify that the public function bypasses skill use.
    old_chat_json = router.llm.chat_json
    try:
        def raising_chat_json(*args, **kwargs):
            raise RuntimeError("offline audit")
        router.llm.chat_json = raising_chat_json
        apply, reason = router.should_apply_skill("anything", SkillItem("s", "body", "abstract"), model="offline")
    finally:
        router.llm.chat_json = old_chat_json
    router_contract = {"apply": apply, "reason": reason, "fails_closed": (apply is False and reason.startswith("router_error:"))}

    payload = {
        "schema_version": 1,
        "upstream": {"repo": "yccm/SkillGen", "source_commit": source_commit,
                     "source_root": str(upstream),
                     "files": {name: result["sha256"] for name, result in import_results.items()}},
        "commands": {"compileall": py_compile},
        "imports": import_results,
        "persistence_contract": persistence,
        "paired_effectiveness_accounting": paired,
        "router_fail_closed_contract": router_contract,
        "network_or_model_calls": False,
        "limitations": [
            "No benchmark task execution or LLM generation was performed.",
            "The paired result is a deterministic accounting fixture, not a skill efficacy result.",
            "Upstream has no bundled unit-test suite in the checked-out root; compile/import checks are the bounded reproduction.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "source_commit": source_commit,
        "compile_returncode": py_compile["returncode"],
        "persistence": persistence,
        "paired": paired,
        "router": router_contract,
    }, indent=2, sort_keys=True))
    return 0 if py_compile["returncode"] == 0 and persistence["round_trip_id_equal"] and paired["matches_expected"] and router_contract["fails_closed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
