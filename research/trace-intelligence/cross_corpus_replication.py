#!/usr/bin/env python3
"""Replicate structural trace findings across aggregate-only pilot outputs.

This program never opens a transcript corpus. Its only inputs are the
content-minimized JSON results produced by the Wisp and share-codex pilots.
It standardizes denominators, reports Wilson score intervals, and explicitly
withholds cross-corpus deltas when event construction is not equivalent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


Z_95 = 1.959963984540054


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def wilson_interval(
    successes: int, total: int, z: float = Z_95
) -> tuple[float, float]:
    if not isinstance(successes, int) or not isinstance(total, int):
        raise TypeError("successes and total must be integers")
    if total <= 0 or successes < 0 or successes > total:
        raise ValueError("require 0 <= successes <= total and total > 0")
    proportion = successes / total
    denominator = 1 + (z * z / total)
    center = (proportion + z * z / (2 * total)) / denominator
    radius = (
        z
        * math.sqrt(
            proportion * (1 - proportion) / total
            + z * z / (4 * total * total)
        )
        / denominator
    )
    lower = 0.0 if successes == 0 else max(0.0, center - radius)
    upper = 1.0 if successes == total else min(1.0, center + radius)
    return lower, upper


def proportion(
    successes: int,
    total: int,
    numerator_unit: str,
    denominator_unit: str,
) -> dict[str, Any]:
    lower, upper = wilson_interval(successes, total)
    return {
        "successes": successes,
        "total": total,
        "numerator_unit": numerator_unit,
        "denominator_unit": denominator_unit,
        "observed_share": round(successes / total, 6),
        "wilson_95": {
            "lower": round(lower, 6),
            "upper": round(upper, 6),
        },
    }


def require_content_minimized(
    aggregate: dict[str, Any], corpus: str
) -> None:
    privacy = aggregate.get("privacy")
    if privacy is None:
        privacy = aggregate.get("privacy_contract")
    if not isinstance(privacy, dict):
        raise ValueError(f"{corpus} aggregate has no privacy contract")
    if privacy.get("raw_data_committed") is True:
        raise ValueError(f"{corpus} aggregate admits committed raw data")
    if privacy.get("content_emitted") is True:
        raise ValueError(f"{corpus} aggregate emits transcript content")
    if privacy.get("content_fields_read_for_analysis") is True:
        raise ValueError(f"{corpus} aggregate used transcript content")


def comparable_pair(
    wisp: dict[str, Any],
    share_codex: dict[str, Any],
    comparability: str,
    caveat: str,
) -> dict[str, Any]:
    result = {
        "comparability": comparability,
        "wisp": wisp,
        "share_codex_sparse": share_codex,
        "caveat": caveat,
    }
    if comparability in {"aligned", "limited"}:
        result["observed_difference_share_codex_minus_wisp"] = round(
            share_codex["observed_share"] - wisp["observed_share"], 6
        )
    return result


def compare_aggregates(
    wisp: dict[str, Any],
    share_codex: dict[str, Any],
    input_integrity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    require_content_minimized(wisp, "wisp")
    require_content_minimized(share_codex, "share-codex")

    wisp_s0 = wisp["S0_metadata"]
    wisp_s2 = wisp["S2_exact_structured_fts_ready"]
    wisp_s4 = wisp["S4_temporal_episode_candidates"]
    share_coverage = share_codex["coverage"]
    share_lifecycle = share_codex["lifecycle"]

    wisp_sessions = int(wisp_s0["sessions"])
    share_sessions = int(share_coverage["sessions"])
    wisp_results = int(wisp_s0["tool_results"])
    share_results = int(share_lifecycle["tool_results"])
    wisp_calls = int(wisp_s0["tool_calls"])
    share_calls = int(share_lifecycle["tool_proposals"])
    wisp_errors = int(
        wisp["S1_deterministic_signals"]["signal_events"][
            "explicit_tool_errors"
        ]
    )
    share_errors = int(share_lifecycle["explicit_error_results"])
    wisp_error_sessions = int(
        wisp_s2["query_candidate_counts"]["explicit_error"]
    )
    share_error_sessions = int(
        share_lifecycle["sessions_with_explicit_error"]
    )
    wisp_candidates = int(wisp_s4["candidate_episodes"])
    share_candidates = int(
        share_lifecycle["error_results_with_later_success"]
    )
    wisp_candidate_sessions = int(wisp_s4["candidate_sessions"])
    share_candidate_sessions = int(
        share_lifecycle["sessions_with_error_then_later_success"]
    )
    wisp_same_family = int(
        wisp_s4["candidate_tiers"]["high"]
        + wisp_s4["candidate_tiers"]["medium"]
    )
    share_same_tool = int(
        share_lifecycle["error_results_with_later_same_tool_success"]
    )

    if wisp_errors > wisp_results or share_errors > share_results:
        raise ValueError("explicit errors exceed tool results")
    if (
        wisp_candidates > wisp_errors
        or share_candidates > share_errors
    ):
        raise ValueError("candidate episodes exceed explicit errors")
    if (
        wisp_same_family > wisp_candidates
        or share_same_tool > share_candidates
    ):
        raise ValueError("same-tool candidates exceed all candidates")

    metrics = {
        "matched_tool_result_share": comparable_pair(
            proportion(
                wisp_results - int(wisp_s0["unlinked_tool_results"]),
                wisp_results,
                "linked tool results",
                "tool results",
            ),
            proportion(
                int(share_lifecycle["matched_tool_results"]),
                share_results,
                "linked tool results",
                "tool results",
            ),
            "aligned",
            (
                "Both adapters use explicit call identifiers. This measures "
                "parser linkage completeness, not task quality."
            ),
        ),
        "proposal_resolution_share": comparable_pair(
            proportion(
                wisp_results,
                wisp_calls,
                "tool proposals with an observed result",
                "tool proposals",
            ),
            proportion(
                share_results,
                share_calls,
                "tool proposals with an observed result",
                "tool proposals",
            ),
            "limited",
            (
                "Both count unresolved proposals, but Wisp is a complete "
                "file snapshot while share-codex is a clustered sparse row "
                "sample; termination and export semantics may differ."
            ),
        ),
        "explicit_error_result_share": comparable_pair(
            proportion(
                wisp_errors,
                wisp_results,
                "typed explicit-error tool results",
                "tool results",
            ),
            proportion(
                share_errors,
                share_results,
                "typed explicit-error tool results",
                "tool results",
            ),
            "limited",
            (
                "Both use exporter-provided error booleans, but native Claude "
                "and normalized Codex/Claude exporters need not label the "
                "same operational failures."
            ),
        ),
        "error_bearing_session_share": comparable_pair(
            proportion(
                wisp_error_sessions,
                wisp_sessions,
                "files/sessions with an explicit error",
                "analyzed files/sessions",
            ),
            proportion(
                share_error_sessions,
                share_sessions,
                "sessions with an explicit error",
                "sampled sessions",
            ),
            "limited",
            (
                "Wisp's unit includes main, benchmark, and nested-subagent "
                "JSONL files; share-codex rows are exported sessions."
            ),
        ),
        "error_to_later_success_candidate_share": comparable_pair(
            proportion(
                wisp_candidates,
                wisp_errors,
                "greedily matched candidate episodes",
                "explicit-error results",
            ),
            proportion(
                share_candidates,
                share_errors,
                "error results with any later non-error result",
                "explicit-error results",
            ),
            "not_aligned",
            (
                "Wisp uses a one-to-one newly proposed result within 24 "
                "records; share-codex uses any later success with no record "
                "window and may reuse one success for multiple errors. No "
                "cross-corpus difference is computed."
            ),
        ),
        "same_tool_or_family_candidate_share": comparable_pair(
            proportion(
                wisp_same_family,
                wisp_candidates,
                "same-family candidates within 24 records",
                "candidate episodes",
            ),
            proportion(
                share_same_tool,
                share_candidates,
                "same-exact-tool-name later-success candidates",
                "later-success candidates",
            ),
            "not_aligned",
            (
                "Wisp compares normalized tool families in a bounded greedy "
                "match. share-codex compares exact generic tool names over an "
                "unbounded suffix. No cross-corpus difference is computed."
            ),
        ),
    }

    return {
        "schema_version": "cross-corpus-structural-replication-v1",
        "inputs": {
            "wisp": {
                "dataset": wisp["source"]["dataset"],
                "revision": wisp["source"]["revision"],
                "aggregate_schema": wisp["schema_version"],
                "integrity": (
                    input_integrity.get("wisp")
                    if input_integrity is not None
                    else None
                ),
            },
            "share_codex_sparse": {
                "dataset": share_codex["source"]["dataset_id"],
                "revision": share_codex["source"]["dataset_revision"],
                "aggregate_schema": share_codex["schema_version"],
                "integrity": (
                    input_integrity.get("share_codex_sparse")
                    if input_integrity is not None
                    else None
                ),
            },
        },
        "uncertainty_contract": {
            "method": "two-sided 95% Wilson score intervals",
            "z": Z_95,
            "interpretation": (
                "Intervals describe denominator uncertainty under a binomial "
                "heuristic. Events are clustered within sessions, Wisp is a "
                "complete released snapshot, and share-codex uses a "
                "non-probability clustered sample. The intervals are not "
                "population confidence intervals and must not be used for "
                "employee or enterprise inference."
            ),
            "cross_corpus_tests": "none",
        },
        "metrics": metrics,
        "session_concentration": {
            "wisp": {
                "sessions": wisp_sessions,
                "error_bearing_sessions": wisp_error_sessions,
                "errors_per_error_bearing_session": round(
                    wisp_errors / wisp_error_sessions, 6
                ),
                "candidate_bearing_sessions": wisp_candidate_sessions,
                "candidates_per_candidate_bearing_session": round(
                    wisp_candidates / wisp_candidate_sessions, 6
                ),
            },
            "share_codex_sparse": {
                "sessions": share_sessions,
                "error_bearing_sessions": share_error_sessions,
                "errors_per_error_bearing_session": round(
                    share_errors / share_error_sessions, 6
                ),
                "candidate_bearing_sessions": share_candidate_sessions,
                "candidates_per_candidate_bearing_session": round(
                    share_candidates / share_candidate_sessions, 6
                ),
            },
            "comparability": "descriptive_only",
            "caveat": (
                "The session/file units and candidate constructors differ. "
                "These concentration summaries are workload diagnostics, "
                "not behavioral comparisons."
            ),
        },
        "schema_and_selection_differences": [
            {
                "dimension": "sampling",
                "wisp": "complete pinned 104-file released snapshot",
                "share_codex_sparse": (
                    "128 rows in eight clustered position strata from a "
                    "4333-row population"
                ),
                "implication": (
                    "share-codex rates cannot be extrapolated to its corpus"
                ),
            },
            {
                "dimension": "analysis unit",
                "wisp": (
                    "main-user, benchmark-development, benchmark-task, and "
                    "nested-subagent JSONL files"
                ),
                "share_codex_sparse": "exported conversation session rows",
                "implication": "session prevalence has limited comparability",
            },
            {
                "dimension": "harness composition",
                "wisp": "native Claude Code plus nested workflow journals",
                "share_codex_sparse": "121 Codex and 7 Claude sampled sessions",
                "implication": (
                    "observed differences mix schema, harness, workload, and "
                    "selection effects"
                ),
            },
            {
                "dimension": "tool lifecycle",
                "wisp": "native tool-use/result content blocks",
                "share_codex_sparse": (
                    "OpenAI-style function calls and normalized tool rows"
                ),
                "implication": (
                    "identifier linkage replicates; error semantics need a "
                    "conformance study"
                ),
            },
            {
                "dimension": "candidate recovery",
                "wisp": (
                    "greedy one-to-one, newly proposed result, 24-record "
                    "window, normalized tool family"
                ),
                "share_codex_sparse": (
                    "any later non-error result, reusable match, no record "
                    "window, exact tool name"
                ),
                "implication": (
                    "recovery and same-tool rates are not replicated "
                    "estimands"
                ),
            },
            {
                "dimension": "outcomes",
                "wisp": "no independent task outcome",
                "share_codex_sparse": "no independent task outcome",
                "implication": (
                    "neither candidate definition measures successful or "
                    "causal recovery"
                ),
            },
        ],
        "replication_decision": {
            "replicated": [
                (
                    "explicit tool-call/result identifiers support complete "
                    "observed result linkage in both adapters"
                ),
                (
                    "typed explicit errors select a small, concentrated "
                    "session review set in both corpora"
                ),
                (
                    "error-to-later-success structures exist in both corpora "
                    "as proposal-only evidence"
                ),
            ],
            "not_replicated_or_not_testable": [
                (
                    "a common recovery rate, because constructors are not "
                    "aligned"
                ),
                (
                    "task success, correctness, skill, productivity, or "
                    "causal improvement"
                ),
                (
                    "cross-user or enterprise collaboration benefit, because "
                    "each source represents an unrelated public contributor"
                ),
            ],
            "required_next_step": (
                "Run one canonical bounded episode constructor over both "
                "native adapters, then validate it against independent task "
                "outcomes and human labels before comparing rates."
            ),
        },
        "claim_boundary": {
            "permitted": [
                "cross-adapter lifecycle linkage replication",
                "descriptive error and review-queue prevalence",
                "schema and selection sensitivity",
                "proposal-only candidate presence",
            ],
            "refused": [
                "individual or cross-user skill inference",
                "productivity or competence ranking",
                "enterprise population prevalence",
                "causal recovery",
                "collaboration recommendations",
                "automatic memory, skill, or eval promotion",
            ],
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wisp", required=True, type=Path)
    parser.add_argument("--share-codex", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    wisp = json.loads(args.wisp.read_text(encoding="utf-8"))
    share_codex = json.loads(args.share_codex.read_text(encoding="utf-8"))
    integrity = {
        "wisp": {"sha256": file_digest(args.wisp)},
        "share_codex_sparse": {"sha256": file_digest(args.share_codex)},
    }
    result = compare_aggregates(wisp, share_codex, integrity)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
