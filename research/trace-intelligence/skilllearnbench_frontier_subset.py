#!/usr/bin/env python3
"""Run a small Codex-subscription SkillLearnBench portability probe.

This intentionally runs outside the benchmark's Docker/OPENAI_API_KEY runner.
It is a bounded host-harness adaptation used to test whether the published
skills change verifier outcomes before investing in the full benchmark stack.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any


EXPECTED = {
    "q1": {
        "eid_06cddbb3",
        "eid_1e9356f5",
        "eid_24dbff62",
        "eid_2d72674d",
        "eid_4350bf70",
        "eid_7ab41e2c",
        "eid_99835861",
        "eid_c3f3eff2",
    },
    "q3": {
        "https://www.convosuggest.com/demo",
        "https://www.pitchperfectai.com/demo",
        "https://www.salesmateai.com/demo",
    },
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_events(stdout: str) -> tuple[dict[str, Any], int]:
    usage: dict[str, Any] = {}
    message_count = 0
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
            usage = event["usage"]
        item = event.get("item")
        if isinstance(item, dict) and item.get("type") == "agent_message":
            message_count += 1
    return usage, message_count


def _validate_answer(answer_path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "answer_exists": answer_path.exists(),
        "json_object": False,
        "required_questions_present": False,
        "token_fields_numeric": False,
        "q1_missing": None,
        "q3_missing": None,
        "exact_metrics": {},
        "passed": False,
    }
    if not answer_path.exists():
        return result
    try:
        actual = json.loads(answer_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return result
    result["json_object"] = isinstance(actual, dict)
    if not isinstance(actual, dict):
        return result
    result["required_questions_present"] = all(key in actual for key in EXPECTED)
    if not result["required_questions_present"]:
        return result
    token_ok = True
    for key in EXPECTED:
        item = actual.get(key)
        if not isinstance(item, dict) or not isinstance(item.get("answer"), list):
            token_ok = False
            continue
        value = item.get("tokens")
        if isinstance(value, bool):
            token_ok = False
        else:
            try:
                float(value)
            except (TypeError, ValueError):
                token_ok = False
    result["token_fields_numeric"] = token_ok
    result["q1_missing"] = len(EXPECTED["q1"] - set(actual["q1"]["answer"]))
    result["q3_missing"] = len(EXPECTED["q3"] - set(actual["q3"]["answer"]))
    exact_metrics: dict[str, dict[str, float | int]] = {}
    for key, expected in EXPECTED.items():
        answers = actual[key]["answer"]
        observed = set(answers)
        exact_metrics[key] = {
            "answer_count": len(answers),
            "expected_count": len(expected),
            "extra_count": len(observed - expected),
            "precision": len(observed & expected) / len(answers) if answers else 0.0,
            "recall": len(observed & expected) / len(expected),
        }
    result["exact_metrics"] = exact_metrics
    result["passed"] = bool(
        result["json_object"]
        and result["required_questions_present"]
        and result["token_fields_numeric"]
        and result["q1_missing"] == 0
        and result["q3_missing"] == 0
    )
    return result


def _arm_prompt(instruction: str, arm: str, arm_root: Path, skill_root: Path | None) -> str:
    skill_clause = (
        "Do not read or use any skill files; this is the null baseline."
        if skill_root is None
        else (
            f"Before solving, read every SKILL.md under {skill_root} and follow the "
            "procedures that apply. Do not read verifier files or gold-answer files."
        )
    )
    return f"""You are running a bounded SkillLearnBench portability probe for arm {arm!r}.
{skill_clause}

The original task instruction is below. Its container paths are mapped as follows:
- /root/DATA -> {arm_root / 'DATA'}
- /root/question.txt -> {arm_root / 'question.txt'}
- /root/answer.json -> {arm_root / 'answer.json'}
Use only those mapped paths and write the required answer JSON before finishing.
Do not inspect tests, verifier code, or any source path outside the mapped data and
the explicitly permitted skill directory. Do not merely explain the answer; create
the JSON file.

Original instruction:
{instruction}
"""


def resolve_skill_root(skill_base: Path, arm: str, task_id: str) -> Path:
    """Resolve the benchmark's family-level skill directory for a task."""
    return skill_base / arm / Path(task_id).parent


def run_arm(
    *,
    task_root: Path,
    arm: str,
    work_root: Path,
    skill_root: Path | None,
    model: str,
    timeout: int,
) -> dict[str, Any]:
    source_environment = task_root / "environment"
    arm_root = work_root / arm.replace("/", "_")
    existing_events = arm_root / "codex-events.jsonl"
    existing_answer = arm_root / "answer.json"
    if existing_events.exists() and existing_answer.exists():
        usage, message_count = _parse_events(existing_events.read_text(encoding="utf-8"))
        return {
            "arm": arm,
            "model": model,
            "returncode": 0,
            "elapsed_seconds": None,
            "usage": usage,
            "agent_message_count": message_count,
            "stdout_sha256": _sha256(existing_events),
            "stderr_sha256": None,
            "answer": _validate_answer(existing_answer),
            "raw_content_retained_outside_repo": True,
            "reused_existing_run": True,
        }
    if arm_root.exists():
        shutil.rmtree(arm_root)
    arm_root.mkdir(parents=True)
    shutil.copytree(source_environment / "DATA", arm_root / "DATA")
    shutil.copy2(source_environment / "question.txt", arm_root / "question.txt")
    instruction = (task_root / "instruction.md").read_text(encoding="utf-8")
    prompt = _arm_prompt(instruction, arm, arm_root, skill_root)
    output_path = arm_root / "codex-events.jsonl"
    started = time.monotonic()
    completed = subprocess.run(
        [
            "codex",
            "exec",
            "--dangerously-bypass-approvals-and-sandbox",
            "--skip-git-repo-check",
            "--json",
            "--ephemeral",
            "--model",
            model,
            "--",
            prompt,
        ],
        cwd=arm_root,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    output_path.write_text(completed.stdout, encoding="utf-8")
    usage, message_count = _parse_events(completed.stdout)
    answer = _validate_answer(arm_root / "answer.json")
    return {
        "arm": arm,
        "model": model,
        "returncode": completed.returncode,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "usage": usage,
        "agent_message_count": message_count,
        "stdout_sha256": _sha256(output_path),
        "stderr_sha256": hashlib.sha256(completed.stderr.encode()).hexdigest(),
        "answer": answer,
        "raw_content_retained_outside_repo": True,
    }


def run(
    *,
    dataset_root: Path,
    task_id: str,
    arms: list[str],
    work_root: Path,
    model: str,
    timeout: int,
) -> dict[str, Any]:
    task_root = dataset_root / "tasks" / task_id
    if not task_root.is_dir():
        raise ValueError(f"task not found: {task_root}")
    skill_base = dataset_root / "skills"
    arm_results = []
    for arm in arms:
        # SkillLearnBench stores skills under the task *family* directory
        # (for example ``enterprise-information-search``), not under the
        # concrete task directory (``enterprise-information-search-1``).
        # Include the whole family so the portability probe can read every
        # skill artifact applicable to the task family.
        skill_root = None if arm == "none" else resolve_skill_root(skill_base, arm, task_id)
        if skill_root is not None and not skill_root.exists():
            raise ValueError(f"skill path not found for {arm}: {skill_root}")
        arm_results.append(
            run_arm(
                task_root=task_root,
                arm=arm,
                work_root=work_root,
                skill_root=skill_root,
                model=model,
                timeout=timeout,
            )
        )
    return {
        "schema": "frankengate-skilllearnbench-frontier-subset-v1",
        "source": {
            "dataset": "cxcscmu/SkillLearnBench",
            "dataset_revision": subprocess.check_output(
                ["git", "-C", str(dataset_root), "rev-parse", "HEAD"], text=True
            ).strip(),
            "task_id": task_id,
            "raw_content_committed": False,
        },
        "harness": {
            "provider": "Codex subscription",
            "model": model,
            "docker_runner": False,
            "adaptation": "host-path portability probe; not the benchmark's Docker runner",
        },
        "arms": arm_results,
        "claim_boundary": {
            "verifier_outcome_measured": True,
            "skill_learning_causal_effect_proven": False,
            "enterprise_transfer_proven": False,
            "reason": "One public task instance and a host-harness adaptation; use only as feasibility and directional evidence.",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-root", type=Path, required=True)
    parser.add_argument("--task-id", default="enterprise-information-search/enterprise-information-search-1")
    parser.add_argument("--arms", nargs="+", default=["none", "human_authored"])
    parser.add_argument("--work-root", type=Path, required=True)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(
        dataset_root=args.dataset_root.resolve(),
        task_id=args.task_id,
        arms=args.arms,
        work_root=args.work_root.resolve(),
        model=args.model,
        timeout=args.timeout,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({arm["arm"]: arm["answer"] for arm in result["arms"]}, sort_keys=True))


if __name__ == "__main__":
    main()
