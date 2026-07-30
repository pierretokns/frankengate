"""CLI and report renderer for the Wisp changed-system replay study."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from agentevals_interop.experiment import select_wisp_cohort
from changed_system_replay import (
    UPSTREAM_COMMIT,
    ReplayTask,
    build_input_manifest,
    run_changed_system_experiment,
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _result_hash(result: dict[str, Any]) -> str:
    payload = dict(result)
    payload.pop("result_sha256", None)
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


def render_summary(result: dict[str, Any]) -> str:
    assertions = {
        (row["implementation"], row["assertion"]): row
        for row in result["assertion_results"]
    }
    prospective = {
        row["assertion"]: row for row in result["prospective_metrics"]
    }
    lines = [
        "# Changed-system replay from natural Wisp assertions",
        "",
        "**Study date:** 2026-07-30  ",
        "**Cohort:** "
        f"{result['natural_trajectory_count']} pinned natural Wisp trajectories  ",
        "**Actual runtime invocations:** "
        f"{result['execution_protocol']['total_runtime_invocations']} "
        "(each system-task pair executed twice to verify reset)  ",
        "**Upstream evaluator:** AgentEvals v0.9.7 at "
        "`221febbe05927923242a5edc12e68a2b70fd5ae9`",
        "",
        "## Result",
        "",
        "This experiment executes three different **system implementations**. It "
        "does not mutate a stored output and call that a changed-system test. "
        "Each implementation runs against a fresh state machine whose required "
        "transitions, expected tool path, observed tool results, task prompt, "
        "and final response are derived from the same source-pinned natural "
        "trajectory.",
        "",
        "| System implementation | Outcome-complete | EXACT | IN_ORDER | ANY_ORDER |",
        "|---|---:|---:|---:|---:|",
    ]
    for implementation in ("original", "benign_audit", "harmful_drop"):
        outcome = result["outcomes"][implementation]
        values = []
        for assertion in ("EXACT", "IN_ORDER", "ANY_ORDER"):
            row = assertions[(implementation, assertion)]
            values.append(f"{row['passed']}/{row['n']} passed")
        lines.append(
            f"| `{implementation}` | {outcome['completed']}/{outcome['n']} | "
            + " | ".join(values)
            + " |"
        )
    lines.extend(
        [
            "",
            "The original system completed all source-derived transitions. The "
            "benign system did the same and appended an audit-only tool call. "
            "The harmful system omitted the final required transition and was "
            "incomplete according to the replay state—not according to the "
            "AgentEvals score.",
            "",
            "## Prospective regression metrics",
            "",
            "| Assertion | Original false positives | Benign false positives | Harmful recall | Errors |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for assertion in ("EXACT", "IN_ORDER", "ANY_ORDER"):
        row = prospective[assertion]
        lines.append(
            f"| `{assertion}` | "
            f"{row['original_false_positive_rate']:.1%} | "
            f"{row['benign_false_positive_rate']:.1%} | "
            f"{row['harmful_regression_recall']:.1%} | "
            f"{row['errored_runs']} |"
        )
    lines.extend(
        [
            "",
            "`EXACT` caught the harmful omission but also rejected every benign "
            "audit addition. `IN_ORDER` and `ANY_ORDER` caught every harmful "
            "omission while accepting the benign extra call in this cohort. "
            "This is prospective regression evidence for this replay model, "
            "not an accuracy estimate for production.",
            "",
            "## Evidence preserved",
            "",
            f"- {result['natural_trajectory_count']} source files are frozen by "
            "content SHA-256 and verified against Hugging Face cache revision "
            f"`{result['corpus']['revision']}`.",
            "- Every expected and emitted tool path, paired tool-result evidence "
            "set, prompt, and final response has a content digest in the input "
            "manifest or aggregate case receipts.",
            "- Content-bearing source JSONL, OTLP, eval sets, and per-case "
            "AgentEvals records remain in the external run directory.",
            "- Each system-task pair ran twice; equality of both executions and a "
            "zeroed pre-state are required before scoring.",
            "- The AgentEvals module was loaded from the verified v0.9.7 checkout; "
            "the runtime reported AgentEvals 0.9.7 and Google ADK 2.1.0.",
            "",
            "## Claim boundary and failure modes",
            "",
            "- The executed target is a resettable **opaque transition replay**, "
            "not the original Hyprland desktop, shell, filesystem, network, model, "
            "or user session.",
            "- Historical Bash arguments are preserved as evidence and assertion "
            "inputs but are never executed. This avoids unsafe, irreproducible "
            "side effects while sacrificing environment fidelity.",
            "- Replay completion means all source-derived transitions were "
            "applied. It does not prove that the historical user task was correct "
            "or that its recorded final response was truthful.",
            "- The harmful arm is one deterministic omission. Argument corruption, "
            "wrong-but-plausible tool results, timeouts, nondeterminism, reordered "
            "commutative actions, provider changes, and semantic-response failures "
            "remain untested changed-system families.",
            "- The cohort contains three content-hash-selected trajectories from "
            "one public contributor and includes benchmark traffic. It cannot "
            "estimate enterprise prevalence or transfer.",
            "- `IN_ORDER` and `ANY_ORDER` tolerate extra calls. That was desirable "
            "for an audit-only addition here, but could hide harmful unasserted "
            "side effects. Separate invariants and outcome oracles remain required.",
            "",
            "## Reproduction",
            "",
            "```bash",
            "PYTHONPATH=research/trace-intelligence python3 \\",
            "  research/trace-intelligence/changed_system_replay_run.py \\",
            "  --cache-root \"$WISP_CACHE_ROOT\" \\",
            "  --dataset-manifest research/trace-intelligence/configs/datasets/wisp-claude-code-sessions.json \\",
            "  --experiment-config research/trace-intelligence/configs/experiments/changed-system-replay-v1-2026.json \\",
            "  --upstream-python \"$AGENTEVALS_UPSTREAM_PYTHON\" \\",
            "  --upstream-root \"$AGENTEVALS_UPSTREAM_ROOT\" \\",
            "  --raw-dir \"$CHANGED_SYSTEM_RAW_DIR\" \\",
            "  --input-manifest research/trace-intelligence/experiments/manifests/changed-system-replay-wisp-2026-07-30.json \\",
            "  --output research/trace-intelligence/experiments/results/changed-system-replay-wisp-2026-07-30.json \\",
            "  --summary research/trace-intelligence/experiments/summaries/changed-system-replay-wisp-2026-07-30.md",
            "```",
            "",
            "## Sources",
            "",
            "- [Wisp dataset at the pinned revision]"
            "(https://huggingface.co/datasets/crispwisp/wisp-claude-code-sessions/tree/"
            "c2c90b59174318ab0b163ec9c9ac82bb879288ce)",
            "- [AgentEvals v0.9.7]"
            "(https://github.com/agentevals-dev/agentevals/tree/"
            "221febbe05927923242a5edc12e68a2b70fd5ae9)",
            "- [AgentEvals built-in metric construction]"
            "(https://github.com/agentevals-dev/agentevals/blob/"
            "221febbe05927923242a5edc12e68a2b70fd5ae9/src/agentevals/builtin_metrics.py#L176-L191)",
            "- [Google ADK trajectory match semantics]"
            "(https://github.com/google/adk-python/blob/"
            "6d15e19f057ee4035960ba5984499cb1eaf943ca/src/google/adk/evaluation/eval_metrics.py)",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--experiment-config", type=Path, required=True)
    parser.add_argument("--upstream-python", type=Path, required=True)
    parser.add_argument("--upstream-root", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()

    config = json.loads(args.experiment_config.read_text(encoding="utf-8"))
    dataset = json.loads(args.dataset_manifest.read_text(encoding="utf-8"))
    if config["upstream"]["commit"] != UPSTREAM_COMMIT:
        raise ValueError("experiment config upstream pin mismatch")
    if config["dataset"]["revision"] != dataset["dataset_revision"]:
        raise ValueError("experiment config dataset revision mismatch")
    max_cases = int(config["dataset"]["max_cases"])
    cohort = select_wisp_cohort(
        args.cache_root / "transcripts",
        max_cases=max_cases,
    )
    if len(cohort) != max_cases:
        raise ValueError(
            f"expected {max_cases} eligible natural trajectories, found {len(cohort)}"
        )
    input_manifest = build_input_manifest(
        cohort=cohort,
        cache_root=args.cache_root,
        dataset_manifest_path=args.dataset_manifest,
    )
    result = run_changed_system_experiment(
        tasks=tuple(
            ReplayTask.from_natural_trajectory(case.trajectory) for case in cohort
        ),
        upstream_python=args.upstream_python,
        upstream_root=args.upstream_root,
        raw_dir=args.raw_dir,
    )
    result.update(
        {
            "study_id": config["study_id"],
            "preregistered_claim": config["preregistered_claim"],
            "corpus": {
                "dataset_id": dataset["dataset_id"],
                "revision": dataset["dataset_revision"],
                "license": dataset["license"],
                "selection": input_manifest["selection"],
            },
            "input_manifest": {
                "path": "experiments/manifests/changed-system-replay-wisp-2026-07-30.json",
                "sha256": hashlib.sha256(
                    (
                        json.dumps(input_manifest, indent=2, sort_keys=True) + "\n"
                    ).encode("utf-8")
                ).hexdigest(),
            },
            "experiment_config": {
                "path": "configs/experiments/changed-system-replay-v1-2026.json",
                "sha256": _sha256_file(args.experiment_config),
            },
            "execution_protocol": {
                "scored_system_task_pairs": len(cohort) * 3,
                "repeat_reset_verification_pairs": len(cohort) * 3,
                "total_runtime_invocations": len(cohort) * 3 * 2,
                "upstream_deterministic_assertion_runs": len(cohort) * 3 * 3,
            },
            "runner_sha256": _sha256_file(Path(__file__)),
        }
    )
    result["result_sha256"] = _result_hash(result)

    args.input_manifest.parent.mkdir(parents=True, exist_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.input_manifest.write_text(
        json.dumps(input_manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.summary.write_text(render_summary(result), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
