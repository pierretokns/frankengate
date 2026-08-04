"""Aggregate content-bearing Trace2Skill runs into a safe Stage-0 receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Sequence

from governed_tool_sandbox import is_network_denial


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def verifier_passes(payload: dict) -> bool:
    summary = payload.get("summary", {})
    return (
        summary.get("total_instances") == 1
        and summary.get("fully_correct_instances") == 1
    )


def summarize_arm(
    label: str,
    root: Path,
    post_recalculation_eval: Path | None = None,
) -> dict:
    root = root.resolve(strict=True)
    result_path = root / "results.json"
    eval_path = root / "eval.json"
    runner = load_json(result_path)
    evaluation = load_json(eval_path)
    audit_paths = sorted((root / "audit").glob("*.jsonl"))
    if not audit_paths:
        raise ValueError(f"no tool audit found for arm {label}")

    tool_calls = []
    for path in audit_paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                tool_calls.append(json.loads(line))

    post_payload = (
        load_json(post_recalculation_eval.resolve(strict=True))
        if post_recalculation_eval
        else evaluation
    )
    before = verifier_passes(evaluation)
    after = verifier_passes(post_payload)
    network_denials = sum(
        bool(row.get("network_denied"))
        or is_network_denial(
            str(row.get("stdout", "")) + "\n" + str(row.get("stderr", ""))
        )
        for row in tool_calls
    )
    result_rows = runner.get("results", [])
    turns = sum(
        int(test_case.get("turns", 0))
        for result in result_rows
        for test_case in result.get("test_cases", [])
    )
    return {
        "label": label,
        "runner_reported_success": runner.get("successful_instances") == 1,
        "verifier_pass_before_formula_recalculation": before,
        "verifier_pass_after_formula_recalculation": after,
        "formula_recalculation_changed_verdict": before != after,
        "turns": turns,
        "tool_calls": len(tool_calls),
        "nonzero_tool_exits": sum(
            (row.get("exit_code") or 0) != 0 for row in tool_calls
        ),
        "tool_timeouts": sum(bool(row.get("timed_out")) for row in tool_calls),
        "sandbox_violations": sum(
            bool(row.get("sandbox_violation")) for row in tool_calls
        ),
        "network_attempts_denied": network_denials,
        "content_bearing_input_hashes": {
            "runner_result_sha256": sha256_file(result_path),
            "pre_recalculation_eval_sha256": sha256_file(eval_path),
            "post_recalculation_eval_sha256": (
                sha256_file(post_recalculation_eval)
                if post_recalculation_eval
                else sha256_file(eval_path)
            ),
            "tool_audit_sha256": [
                sha256_file(path) for path in audit_paths
            ],
        },
    }


def parse_arm(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("arm must be LABEL=/absolute/run/root")
    label, raw_path = value.split("=", 1)
    if not label or not raw_path:
        raise argparse.ArgumentTypeError("arm must be LABEL=/absolute/run/root")
    return label, Path(raw_path)


def parse_recalculated(value: str) -> tuple[str, Path]:
    return parse_arm(value)


def build_receipt(
    arms: Sequence[tuple[str, Path]],
    recalculated: dict[str, Path],
) -> dict:
    summaries = [
        summarize_arm(label, root, recalculated.get(label))
        for label, root in arms
    ]
    return {
        "schema_version": "frankengate-trace2skill-stage0-v1",
        "experiment_date": "2026-07-30",
        "experiment_class": "execution-safety and verifier-validity smoke test",
        "dataset": {
            "id": "Qwen-Applications/Trace2Skill:spreadsheetbench_verified_400",
            "revision": "3d0b52a140f002a512930252b613c49048f7d5ac",
            "manifest_sha256": "bcecaa89a005bd4e3bbe98da150a86e8062c27f262e575d5e47bd9861b3525e7",
            "task_id": "54513",
        },
        "model": {
            "id": "mlx-community/Qwen3.5-9B-OptiQ-4bit",
            "snapshot": "319aed167e31e0bf81ddba0c23f8d218a15be612",
            "temperature": 0,
            "seed": 20260730,
        },
        "arms": summaries,
        "findings": {
            "sandbox_boundary_executed_real_model_tool_calls": True,
            "all_recorded_tool_calls_had_network_denied_by_policy": True,
            "formula_recalculation_is_required_before_workbook_verification": any(
                arm["formula_recalculation_changed_verdict"] for arm in summaries
            ),
            "skill_benefit_established": False,
            "spreadsheet_domain_priority": "cross-domain control only",
            "primary_enterprise_domain": "NL2SQL",
        },
        "claim_boundary": [
            "one task cannot estimate skill utility",
            "runner success means an output exists, not that the verifier passes",
            "pre-recalculation data-only comparison can falsely reject formula outputs",
            "the smoke test establishes execution-boundary mechanics, not enterprise transfer",
        ],
        "raw_traces_or_workbooks_committed": False,
    }


def render_summary(receipt: dict) -> str:
    arm_lines = []
    for arm in receipt["arms"]:
        arm_lines.append(
            "| {label} | {before} | {after} | {calls} | {violations} | {network} |".format(
                label=arm["label"],
                before="pass" if arm["verifier_pass_before_formula_recalculation"] else "fail",
                after="pass" if arm["verifier_pass_after_formula_recalculation"] else "fail",
                calls=arm["tool_calls"],
                violations=arm["sandbox_violations"],
                network=arm["network_attempts_denied"],
            )
        )
    return """# Trace2Skill governed Stage-0 smoke test

This is a one-task execution-safety and verifier-validity result, not a skill
quality estimate. SpreadsheetBench remains a cross-domain control; NL2SQL is the
primary enterprise replay domain.

| Arm | Pre-recalculation verifier | Post-recalculation verifier | Tool calls | Sandbox violations | Network attempts denied |
| --- | --- | --- | ---: | ---: | ---: |
{arms}

Both arms passed after correct formula handling. The human-skill arm wrote a
formula whose cached value was absent, so the upstream data-only comparison
initially rejected it. LibreOffice recalculation changed that verdict from fail
to pass. A production experiment must therefore pin and run a calculation
engine before workbook comparison.

The sandbox executed real model tool calls with task-only writes, declared-root
reads, stripped API credentials, and network denial. No sandbox escape or
timeout was observed. Content-bearing commands, outputs, workbooks, and logs
remain outside Git; only aggregate counts and hashes are committed.

No skill benefit can be inferred from one task where both arms pass. The useful
result is the execution boundary and the discovery of a verifier failure mode.
""".format(arms="\n".join(arm_lines))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--arm", action="append", required=True, type=parse_arm)
    parser.add_argument(
        "--post-recalculation-eval",
        action="append",
        default=[],
        type=parse_recalculated,
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    args = parser.parse_args(argv)

    recalculated = dict(args.post_recalculation_eval)
    receipt = build_receipt(args.arm, recalculated)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    args.summary.write_text(render_summary(receipt), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
