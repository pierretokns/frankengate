"""Run the aggregate-only upstream AgentEvals interoperability study."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .experiment import MUTATION_ARMS, run_upstream_experiment, select_wisp_cohort


WISP_DATASET = {
    "dataset_id": "crispwisp/wisp-claude-code-sessions",
    "revision": "c2c90b59174318ab0b163ec9c9ac82bb879288ce",
    "license": "MIT",
    "source_format": "Claude Code JSONL",
}


def render_summary(result: dict[str, Any]) -> str:
    deterministic = {
        (row["arm"], row["assertion"]): row
        for row in result["deterministic_assertions"]
    }
    semantic = {row["arm"]: row for row in result["semantic_assertions"]}
    lines = [
        "# Upstream AgentEvals natural-trace interoperability",
        "",
        "**Study date:** 2026-07-30  ",
        "**Execution:** AgentEvals v0.9.7 at "
        "`221febbe05927923242a5edc12e68a2b70fd5ae9`  ",
        "**Natural cohort:** "
        f"{result['natural_trajectory_count']} complete multi-tool Wisp histories  ",
        "**Claim boundary:** stored-trace assertions only; no changed system was executed",
        "",
        "## Deterministic tool-trajectory assertions",
        "",
        "| Mutation | EXACT | IN_ORDER | ANY_ORDER |",
        "|---|---:|---:|---:|",
    ]
    for arm in result["mutation_arms"]:
        cells = []
        for assertion in ("EXACT", "IN_ORDER", "ANY_ORDER"):
            row = deterministic[(arm, assertion)]
            cells.append(
                f"{row['mean_score']:.3f} ({row['passed']}/{row['n']} passed)"
            )
        lines.append(f"| `{arm}` | {' | '.join(cells)} |")
    if semantic:
        lines.extend(
            [
                "",
                "## Upstream semantic response assertion",
                "",
                "AgentEvals `final_response_match_v2` was executed with its pinned "
                "ADK judge path and a pinned, loopback-only Qwen3.5-9B model. "
                "This is a model-judge result, not deterministic ground truth.",
                "",
                "| Mutation | Mean score | Passed | Failed | Errors |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        lines.extend(
            [
                "",
                "The semantic judge caught all 3/3 response reversals and accepted "
                "all 3/3 benign wrappers, but it also rejected 1/3 unmodified "
                "baselines. That non-monotonic false negative is direct evidence "
                "against using this judge alone as a release gate.",
            ]
        )
        for arm in (
            "baseline",
            "benign_response_wrapper",
            "harmful_response_reversal",
        ):
            if arm not in semantic:
                continue
            row = semantic[arm]
            score = "n/a" if row["mean_score"] is None else f"{row['mean_score']:.3f}"
            lines.append(
                f"| `{arm}` | {score} | {row['passed']} | "
                f"{row['failed']} | {row['errored']} |"
            )
    lines.extend(
        [
            "",
            "## What this mechanism contributes",
            "",
            "- `EXACT` detects any tool-name/argument/order divergence.",
            "- `IN_ORDER` tests an expected ordered subsequence, so it can tolerate "
            "additional calls but not a reversal or a missing expected call.",
            "- `ANY_ORDER` isolates membership/argument equality from ordering; the "
            "reversal arm demonstrates its incremental contribution.",
            "- `final_response_match_v2` tests response-level semantic equivalence "
            "separately from tool-path equivalence.",
            "",
            "## Limits",
            "",
            "- These evaluations score already-recorded traces. They do not rerun an "
            "agent, tool, environment, side effect, or changed Frankengate build.",
            "- A passing stored-trajectory assertion is therefore retrospective "
            "compatibility evidence, not a changed-system regression result.",
            "- Call-ID remapping is intentionally benign and demonstrates that the "
            "tool evaluator compares names and arguments, not trace correlation IDs.",
            "- Sequence reversal is a structural sensitivity probe; it is not labeled "
            "benign or harmful without task-specific commutativity evidence.",
            "- The semantic arm uses one local judge model and one deterministic "
            "template-level benign/harmful mutation pair. Human labels and multiple "
            "judge families are required before estimating semantic accuracy.",
            "- Raw prompts, responses, tool arguments, and per-case scores remain in "
            "the external run directory. This repository contains aggregates only.",
            "",
            "## Reproduction",
            "",
            "```bash",
            "PYTHONPATH=research/trace-intelligence \\",
            "python -m agentevals_interop.run \\",
            "  --corpus-root \"$WISP_CORPUS_ROOT\" \\",
            "  --upstream-python \"$AGENTEVALS_UPSTREAM_PYTHON\" \\",
            "  --upstream-root \"$AGENTEVALS_UPSTREAM_ROOT\" \\",
            "  --raw-dir \"$AGENTEVALS_RAW_DIR\" \\",
            "  --judge-base-url http://127.0.0.1:18082/v1 \\",
            "  --output experiments/results/agentevals-upstream-wisp-2026-07-30.json \\",
            "  --summary experiments/summaries/agentevals-upstream-wisp-2026-07-30.md",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument("--upstream-python", type=Path, required=True)
    parser.add_argument("--upstream-root", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--judge-base-url", required=True)
    parser.add_argument("--judge-model", default="openai/default_model")
    parser.add_argument("--max-cases", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()

    cohort = select_wisp_cohort(args.corpus_root, max_cases=args.max_cases)
    result = run_upstream_experiment(
        trajectories=tuple(case.trajectory for case in cohort),
        upstream_python=args.upstream_python,
        upstream_root=args.upstream_root,
        raw_dir=args.raw_dir,
        arms=MUTATION_ARMS,
        include_semantic=True,
        judge_model=args.judge_model,
        judge_base_url=args.judge_base_url,
        judge_api_key="loopback-no-secret",
    )
    result["study_id"] = "agentevals-upstream-wisp-2026-07-30"
    result["corpus"] = {
        **WISP_DATASET,
        "selection": (
            f"first {len(cohort)} by source-content hash among complete single-turn histories "
            "with at least two paired tool calls and a final response"
        ),
    }
    result["independent_contribution"] = {
        "exact": "detects tool name, argument, count, and order divergence",
        "in_order": "requires expected calls in sequence while allowing extra calls",
        "any_order": "removes order sensitivity while retaining membership and argument checks",
        "semantic": (
            "detects response-level reversal ignored by every tool matcher, "
            "but produced one false negative on three unmodified baselines"
        ),
        "composition": (
            "tool-path and response-semantic assertions are complementary; "
            "neither establishes changed-system behavior"
        ),
    }
    result["semantic_evaluator"]["model_manifest"] = (
        "configs/models/qwen3.5-9b-optiq-4bit-mlx-runtime-v2.json"
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.summary.write_text(render_summary(result), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
