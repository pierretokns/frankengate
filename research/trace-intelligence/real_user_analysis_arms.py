#!/usr/bin/env python3
"""Run content-minimized analysis arms over native Claude Code sessions.

The raw corpus is intentionally read only in temporary storage.  This program
does not serialize prompts, reasoning, tool arguments/results, paths, native
IDs, exact timestamps, or per-session rows.  Its output is limited to
aggregate counts over controlled structural features.

The stages mirror the Frankengate experiment ladder:

* S0: metadata and ingestion quality;
* S1: deterministic friction signals;
* S2: exact/structured and controlled-vocabulary FTS-ready features;
* S4: temporal error/retry episode candidates;
* S6: eval, memory, and procedure proposal candidates.

All "recovery" measurements are structural specificity proxies.  They are not
labels of task success, correctness, causality, user skill, or productivity.
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import datetime as dt
import json
import math
from pathlib import Path
from typing import Any, Iterable


MAX_RECOVERY_GAP_RECORDS = 24
HIGH_SPECIFICITY_GAP_RECORDS = 8
REVIEW_FRACTION = 0.20
MIN_REVIEW_BUDGET = 10
MAX_REVIEW_BUDGET = 25


TOOL_FAMILIES = {
    "Bash": "shell",
    "Edit": "file_mutation",
    "Write": "file_mutation",
    "Read": "file_read",
    "WebFetch": "external_retrieval",
    "WebSearch": "external_retrieval",
    "ToolSearch": "tool_discovery",
    "TaskCreate": "task_coordination",
    "TaskUpdate": "task_coordination",
    "TaskOutput": "task_coordination",
    "Workflow": "delegation",
    "Skill": "skill_invocation",
    "AskUserQuestion": "human_interaction",
    "StructuredOutput": "structured_output",
}


def tool_family(name: Any) -> str:
    """Map a native tool name to a controlled, non-content vocabulary."""
    if not isinstance(name, str):
        return "other"
    return TOOL_FAMILIES.get(name, "other")


def classify_file(relative_path: Path) -> str:
    """Classify a file without serializing its path."""
    parts = relative_path.parts
    text = relative_path.as_posix()
    if "/subagents/workflows/" in f"/{text}":
        return "nested_subagent"
    if len(parts) == 2 and parts[0] == "-home-me":
        return "main_user"
    if len(parts) == 2 and parts[0] == "-home-me-ht-hyprland-bench":
        return "benchmark_development"
    if parts and parts[0].startswith(
        "-home-me-ht-hyprland-bench-results-"
    ):
        return "benchmark_task"
    return "other"


def iter_blocks(record: dict[str, Any]) -> Iterable[dict[str, Any]]:
    message = record.get("message")
    if not isinstance(message, dict):
        return
    content = message.get("content")
    if not isinstance(content, list):
        return
    for block in content:
        if isinstance(block, dict):
            yield block


def parse_timestamp(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def result_is_error(block: dict[str, Any]) -> bool:
    return block.get("is_error") is True or block.get("isError") is True


@dataclasses.dataclass(frozen=True)
class ToolCall:
    order: int
    family: str


@dataclasses.dataclass(frozen=True)
class ToolResult:
    order: int
    call_reference: str | None
    is_error: bool


@dataclasses.dataclass(frozen=True)
class RecoveryEpisode:
    tier: str
    error_family: str
    recovery_family: str
    gap_records: int


@dataclasses.dataclass
class SessionEvidence:
    stratum: str
    valid_records: int = 0
    invalid_records: int = 0
    record_type_counts: collections.Counter[str] = dataclasses.field(
        default_factory=collections.Counter
    )
    calls: dict[str, ToolCall] = dataclasses.field(default_factory=dict)
    call_order: list[ToolCall] = dataclasses.field(default_factory=list)
    results: list[ToolResult] = dataclasses.field(default_factory=list)
    native_nodes: set[str] = dataclasses.field(default_factory=set)
    parent_references: set[str] = dataclasses.field(default_factory=set)
    parent_child_counts: collections.Counter[str] = dataclasses.field(
        default_factory=collections.Counter
    )
    api_error_records: int = 0
    timestamps: list[dt.datetime] = dataclasses.field(default_factory=list)
    recoveries: list[RecoveryEpisode] = dataclasses.field(default_factory=list)
    ambiguous_parallel_successes: int = 0

    @property
    def explicit_errors(self) -> int:
        return sum(result.is_error for result in self.results)

    @property
    def linked_results(self) -> int:
        return sum(
            result.call_reference in self.calls
            for result in self.results
            if result.call_reference
        )

    @property
    def unlinked_results(self) -> int:
        return len(self.results) - self.linked_results

    @property
    def orphan_calls(self) -> int:
        referenced = {
            result.call_reference
            for result in self.results
            if result.call_reference
        }
        return sum(call_reference not in referenced for call_reference in self.calls)

    @property
    def branch_points(self) -> int:
        return sum(count > 1 for count in self.parent_child_counts.values())

    @property
    def dangling_parents(self) -> int:
        return len(self.parent_references - self.native_nodes)

    @property
    def repeated_family_runs(self) -> int:
        if not self.call_order:
            return 0
        runs = 0
        previous = self.call_order[0].family
        run_length = 1
        for call in self.call_order[1:]:
            if call.family == previous:
                run_length += 1
            else:
                if run_length >= 3:
                    runs += 1
                previous = call.family
                run_length = 1
        if run_length >= 3:
            runs += 1
        return runs

    @property
    def controlled_terms(self) -> set[str]:
        terms = {f"stratum_{self.stratum}"}
        terms.update(f"tool_{call.family}" for call in self.call_order)
        if self.explicit_errors:
            terms.add("signal_explicit_error")
        if self.recoveries:
            terms.add("signal_recovery_candidate")
        if self.repeated_family_runs:
            terms.add("signal_repeated_family")
        if self.branch_points:
            terms.add("topology_branch")
        if self.dangling_parents:
            terms.add("quality_dangling_parent")
        if self.invalid_records:
            terms.add("quality_malformed_record")
        return terms


def read_session(path: Path, root: Path) -> SessionEvidence:
    evidence = SessionEvidence(stratum=classify_file(path.relative_to(root)))
    record_order = 0
    with path.open("rb") as stream:
        for raw_line in stream:
            try:
                record = json.loads(raw_line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                evidence.invalid_records += 1
                continue
            if not isinstance(record, dict):
                evidence.invalid_records += 1
                continue

            record_order += 1
            evidence.valid_records += 1
            evidence.record_type_counts[
                str(record.get("type", "missing"))
            ] += 1
            timestamp = parse_timestamp(record.get("timestamp"))
            if timestamp is not None:
                evidence.timestamps.append(timestamp)
            if record.get("isApiErrorMessage") is True:
                evidence.api_error_records += 1

            native_node = record.get("uuid")
            if isinstance(native_node, str) and native_node:
                evidence.native_nodes.add(native_node)
            parent = record.get("parentUuid")
            if isinstance(parent, str) and parent:
                evidence.parent_references.add(parent)
                evidence.parent_child_counts[parent] += 1

            block_offset = 0
            for block in iter_blocks(record):
                block_offset += 1
                block_order = record_order * 100 + block_offset
                block_type = block.get("type")
                if block_type == "tool_use":
                    native_call = block.get("id")
                    call = ToolCall(
                        order=block_order,
                        family=tool_family(block.get("name")),
                    )
                    evidence.call_order.append(call)
                    if isinstance(native_call, str) and native_call:
                        evidence.calls[native_call] = call
                elif block_type == "tool_result":
                    native_reference = block.get("tool_use_id")
                    evidence.results.append(
                        ToolResult(
                            order=block_order,
                            call_reference=(
                                native_reference
                                if isinstance(native_reference, str)
                                and native_reference
                                else None
                            ),
                            is_error=result_is_error(block),
                        )
                    )

    evidence.recoveries, evidence.ambiguous_parallel_successes = (
        reconstruct_recoveries(evidence)
    )
    return evidence


def reconstruct_recoveries(
    evidence: SessionEvidence,
) -> tuple[list[RecoveryEpisode], int]:
    """Greedily build one-to-one structural recovery candidates.

    A candidate requires an explicit error result followed by a non-error result
    whose own tool call was proposed after the error.  This excludes parallel
    calls that happened to finish later.  Same-family and short-gap chains have
    higher specificity, but none are correctness or task-success labels.
    """
    recoveries: list[RecoveryEpisode] = []
    consumed_successes: set[int] = set()
    ambiguous_parallel = 0

    for error_index, error_result in enumerate(evidence.results):
        if not error_result.is_error:
            continue
        error_call = (
            evidence.calls.get(error_result.call_reference)
            if error_result.call_reference
            else None
        )
        candidates: list[tuple[int, ToolResult, ToolCall]] = []
        for success_index in range(error_index + 1, len(evidence.results)):
            if success_index in consumed_successes:
                continue
            success_result = evidence.results[success_index]
            if success_result.is_error or not success_result.call_reference:
                continue
            success_call = evidence.calls.get(success_result.call_reference)
            if success_call is None:
                continue
            result_gap = (success_result.order // 100) - (
                error_result.order // 100
            )
            if result_gap > MAX_RECOVERY_GAP_RECORDS:
                break
            if success_call.order <= error_result.order:
                ambiguous_parallel += 1
                continue
            candidates.append((success_index, success_result, success_call))

        if not candidates:
            continue

        same_family: list[tuple[int, ToolResult, ToolCall]] = []
        if error_call is not None:
            same_family = [
                candidate
                for candidate in candidates
                if candidate[2].family == error_call.family
            ]
        chosen = same_family[0] if same_family else candidates[0]
        success_index, success_result, success_call = chosen
        gap = (success_result.order // 100) - (error_result.order // 100)
        if error_call is not None and success_call.family == error_call.family:
            tier = (
                "high"
                if gap <= HIGH_SPECIFICITY_GAP_RECORDS
                else "medium"
            )
            error_family = error_call.family
        else:
            tier = "low"
            error_family = error_call.family if error_call else "unknown"
        recoveries.append(
            RecoveryEpisode(
                tier=tier,
                error_family=error_family,
                recovery_family=success_call.family,
                gap_records=gap,
            )
        )
        consumed_successes.add(success_index)

    return recoveries, ambiguous_parallel


def review_budget(session_count: int) -> int:
    if session_count <= 0:
        return 0
    return min(
        session_count,
        MAX_REVIEW_BUDGET,
        max(MIN_REVIEW_BUDGET, math.ceil(session_count * REVIEW_FRACTION)),
    )


def ranked_selection(
    sessions: list[SessionEvidence],
    score,
    budget: int,
    require_positive: bool = True,
    eligible: set[int] | None = None,
) -> set[int]:
    ranking = sorted(
        (
            (score(session), index)
            for index, session in enumerate(sessions)
            if eligible is None or index in eligible
        ),
        key=lambda item: (-item[0], item[1]),
    )
    return {
        index
        for value, index in ranking[:budget]
        if value > 0 or not require_positive
    }


def overlap(left: set[int], right: set[int]) -> dict[str, int | float]:
    union = left | right
    intersection = left & right
    return {
        "intersection": len(intersection),
        "union": len(union),
        "jaccard": round(len(intersection) / len(union), 4) if union else 1.0,
    }


def by_stratum(
    sessions: list[SessionEvidence], selected: set[int]
) -> dict[str, int]:
    counts = collections.Counter(
        session.stratum
        for index, session in enumerate(sessions)
        if index in selected
    )
    return dict(sorted(counts.items()))


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return round(numerator / denominator, 4)


def analyze_corpus(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    paths = sorted(root.rglob("*.jsonl"))
    sessions = [read_session(path, root) for path in paths]
    budget = review_budget(len(sessions))

    stratum_counts = collections.Counter(session.stratum for session in sessions)
    timestamps = [
        timestamp for session in sessions for timestamp in session.timestamps
    ]
    observed_span_days = (
        (max(timestamps) - min(timestamps)).days if timestamps else None
    )

    s1_candidates = {
        index
        for index, session in enumerate(sessions)
        if (
            session.explicit_errors
            or session.api_error_records
            or session.repeated_family_runs
            or session.branch_points
            or session.invalid_records
            or session.dangling_parents
            or session.orphan_calls
            or session.unlinked_results
        )
    }
    s1_review = ranked_selection(
        sessions,
        lambda session: (
            5 * session.explicit_errors
            + 4 * session.api_error_records
            + 3 * session.repeated_family_runs
            + 2 * session.branch_points
            + 2 * session.invalid_records
            + session.dangling_parents
            + session.orphan_calls
            + session.unlinked_results
        ),
        budget,
        eligible=s1_candidates,
    )

    s2_candidates = {
        index
        for index, session in enumerate(sessions)
        if len(session.controlled_terms) > 1
    }
    s2_review = ranked_selection(
        sessions,
        lambda session: (
            len(session.controlled_terms)
            + 4 * session.explicit_errors
            + 3 * len(session.recoveries)
            + 2 * session.repeated_family_runs
            + session.branch_points
        ),
        budget,
        eligible=s2_candidates,
    )

    s4_candidates = {
        index
        for index, session in enumerate(sessions)
        if session.recoveries
    }
    s4_review = ranked_selection(
        sessions,
        lambda session: (
            5
            * sum(episode.tier == "high" for episode in session.recoveries)
            + 3
            * sum(episode.tier == "medium" for episode in session.recoveries)
            + sum(episode.tier == "low" for episode in session.recoveries)
        ),
        budget,
        eligible=s4_candidates,
    )

    recovery_motifs: collections.Counter[
        tuple[str, str, str]
    ] = collections.Counter()
    recovery_motif_sessions: dict[
        tuple[str, str, str], set[int]
    ] = collections.defaultdict(set)
    for index, session in enumerate(sessions):
        for episode in session.recoveries:
            motif = (
                episode.tier,
                episode.error_family,
                episode.recovery_family,
            )
            recovery_motifs[motif] += 1
            recovery_motif_sessions[motif].add(index)

    repeated_motifs = {
        motif
        for motif, supporting_sessions in recovery_motif_sessions.items()
        if len(supporting_sessions) >= 2
    }
    memory_supporting_sessions = set().union(
        *(recovery_motif_sessions[motif] for motif in repeated_motifs)
    ) if repeated_motifs else set()
    procedure_episodes = sum(
        recovery_motifs[motif]
        for motif in repeated_motifs
        if motif[0] in {"high", "medium"}
        and motif[1] == motif[2]
    )
    eval_supporting_sessions = {
        index
        for index, session in enumerate(sessions)
        if session.explicit_errors
    }
    s6_candidates = (
        eval_supporting_sessions | memory_supporting_sessions | s4_candidates
    )
    s6_review = ranked_selection(
        sessions,
        lambda session: (
            6
            * sum(episode.tier == "high" for episode in session.recoveries)
            + 4
            * sum(episode.tier == "medium" for episode in session.recoveries)
            + 2 * session.explicit_errors
            + session.repeated_family_runs
        ),
        budget,
        eligible=s6_candidates,
    )

    all_recoveries = [
        episode for session in sessions for episode in session.recoveries
    ]
    tier_counts = collections.Counter(
        episode.tier for episode in all_recoveries
    )
    explicit_errors = sum(session.explicit_errors for session in sessions)
    linked_error_results = sum(
        result.is_error
        and result.call_reference is not None
        and result.call_reference in session.calls
        for session in sessions
        for result in session.results
    )
    total_calls = sum(len(session.calls) for session in sessions)
    total_results = sum(len(session.results) for session in sessions)

    controlled_vocabulary = set().union(
        *(session.controlled_terms for session in sessions)
    ) if sessions else set()
    token_counts = [len(session.controlled_terms) for session in sessions]

    result = {
        "schema_version": "content-minimized-real-user-arms-v1",
        "source": {
            "dataset": manifest.get("dataset_id"),
            "revision": manifest.get("dataset_revision"),
            "license": manifest.get("license"),
            "raw_corpus_committed": False,
        },
        "privacy_contract": {
            "serialized_granularity": "aggregate_counts_only",
            "content_fields_read_for_analysis": False,
            "prohibited_output": [
                "prompts",
                "reasoning",
                "tool_arguments",
                "tool_results",
                "filesystem_paths",
                "native_or_synthetic_session_or_event_identifiers",
                "exact_timestamps",
                "per-session_rows",
            ],
            "identity_scope": "one_intentionally_public_contributor",
        },
        "claim_boundaries": {
            "supported": [
                "ingestion_and_schema_quality",
                "deterministic_candidate_selection",
                "controlled_structural_retrieval",
                "proposal_only_error_retry_episode_reconstruction",
                "bounded_human_review_queue_design",
            ],
            "not_identifiable": [
                "task_success_or_correctness",
                "causal_recovery",
                "user_skill_or_productivity",
                "best_prompt_model_memory_or_procedure",
                "cross_user_similarity_or_collaboration_value",
                "enterprise_population_effects",
            ],
            "required_next_evidence": [
                "independent_task_outcomes",
                "environment_access_and_tool_availability_labels",
                "human_review_labels",
                "multi_user_consent_and_governance",
                "prospective_randomized_or_stepped_wedge_interventions",
            ],
        },
        "review_policy": {
            "fraction": REVIEW_FRACTION,
            "minimum": MIN_REVIEW_BUDGET,
            "maximum": MAX_REVIEW_BUDGET,
            "selected_session_budget": budget,
            "ranking_tie_break": "stable_source_order_not_serialized",
        },
        "S0_metadata": {
            "sessions": len(sessions),
            "sessions_by_stratum": dict(sorted(stratum_counts.items())),
            "valid_records": sum(
                session.valid_records for session in sessions
            ),
            "malformed_records": sum(
                session.invalid_records for session in sessions
            ),
            "observed_span_days": observed_span_days,
            "tool_calls": total_calls,
            "tool_results": total_results,
            "linked_result_share": _ratio(
                sum(session.linked_results for session in sessions),
                total_results,
            ),
            "orphan_tool_calls": sum(
                session.orphan_calls for session in sessions
            ),
            "unlinked_tool_results": sum(
                session.unlinked_results for session in sessions
            ),
            "branch_points": sum(
                session.branch_points for session in sessions
            ),
            "dangling_parent_references": sum(
                session.dangling_parents for session in sessions
            ),
        },
        "S1_deterministic_signals": {
            "candidate_sessions": len(s1_candidates),
            "candidate_sessions_by_stratum": by_stratum(
                sessions, s1_candidates
            ),
            "review_selected_sessions": len(s1_review),
            "review_selected_by_stratum": by_stratum(sessions, s1_review),
            "signal_events": {
                "explicit_tool_errors": explicit_errors,
                "api_error_records": sum(
                    session.api_error_records for session in sessions
                ),
                "repeated_tool_family_runs_length_at_least_three": sum(
                    session.repeated_family_runs for session in sessions
                ),
                "sessions_with_branch_points": sum(
                    bool(session.branch_points) for session in sessions
                ),
                "sessions_with_malformed_records": sum(
                    bool(session.invalid_records) for session in sessions
                ),
                "sessions_with_dangling_parents": sum(
                    bool(session.dangling_parents) for session in sessions
                ),
            },
            "interpretation": (
                "selection signals for review, not failure or skill labels"
            ),
        },
        "S2_exact_structured_fts_ready": {
            "candidate_sessions": len(s2_candidates),
            "candidate_sessions_by_stratum": by_stratum(
                sessions, s2_candidates
            ),
            "review_selected_sessions": len(s2_review),
            "review_selected_by_stratum": by_stratum(sessions, s2_review),
            "structured_feature_rows": len(sessions),
            "controlled_vocabulary_terms": len(controlled_vocabulary),
            "mean_terms_per_session": (
                round(sum(token_counts) / len(token_counts), 4)
                if token_counts
                else 0.0
            ),
            "query_candidate_counts": {
                "explicit_error": sum(
                    bool(session.explicit_errors) for session in sessions
                ),
                "recovery_candidate": sum(
                    bool(session.recoveries) for session in sessions
                ),
                "branch_and_error": sum(
                    bool(session.branch_points and session.explicit_errors)
                    for session in sessions
                ),
                "subagent_and_error": sum(
                    session.stratum == "nested_subagent"
                    and bool(session.explicit_errors)
                    for session in sessions
                ),
                "repeated_family_and_error": sum(
                    bool(
                        session.repeated_family_runs
                        and session.explicit_errors
                    )
                    for session in sessions
                ),
            },
            "fts_boundary": (
                "only controlled structural terms; no transcript text"
            ),
        },
        "S4_temporal_episode_candidates": {
            "candidate_sessions": len(s4_candidates),
            "candidate_sessions_by_stratum": by_stratum(
                sessions, s4_candidates
            ),
            "review_selected_sessions": len(s4_review),
            "review_selected_by_stratum": by_stratum(sessions, s4_review),
            "candidate_episodes": len(all_recoveries),
            "candidate_tiers": {
                "high": tier_counts["high"],
                "medium": tier_counts["medium"],
                "low": tier_counts["low"],
            },
            "precision_proxies": {
                "linked_error_evidence_share": _ratio(
                    linked_error_results, explicit_errors
                ),
                "error_to_candidate_episode_share": _ratio(
                    len(all_recoveries), explicit_errors
                ),
                "high_specificity_share": _ratio(
                    tier_counts["high"], len(all_recoveries)
                ),
                "same_family_share": _ratio(
                    tier_counts["high"] + tier_counts["medium"],
                    len(all_recoveries),
                ),
            },
            "ambiguous_parallel_successes_excluded": sum(
                session.ambiguous_parallel_successes
                for session in sessions
            ),
            "definition": {
                "high": (
                    "linked explicit error followed by a newly proposed, "
                    "linked non-error result in the same tool family within "
                    f"{HIGH_SPECIFICITY_GAP_RECORDS} records"
                ),
                "medium": (
                    "same as high but within "
                    f"{MAX_RECOVERY_GAP_RECORDS} records"
                ),
                "low": (
                    "linked explicit error followed by a newly proposed, "
                    "linked non-error result in another tool family within "
                    f"{MAX_RECOVERY_GAP_RECORDS} records"
                ),
            },
            "interpretation": (
                "structural specificity proxies, not measured precision or "
                "causal recovery"
            ),
        },
        "S6_proposal_records": {
            "candidate_sessions": len(s6_candidates),
            "candidate_sessions_by_stratum": by_stratum(
                sessions, s6_candidates
            ),
            "review_selected_sessions": len(s6_review),
            "review_selected_by_stratum": by_stratum(sessions, s6_review),
            "candidate_records": {
                "eval_review": explicit_errors,
                "memory_review_motifs": len(repeated_motifs),
                "memory_review_supporting_episodes": sum(
                    recovery_motifs[motif] for motif in repeated_motifs
                ),
                "procedure_review_episodes": procedure_episodes,
                "skill_gap_recommendations": 0,
                "cross_user_collaboration_recommendations": 0,
                "automatic_memory_or_skill_writes": 0,
            },
            "release_boundary": (
                "records are review proposals; promotion requires scoped "
                "evidence, independent outcomes, provenance, and approval"
            ),
            "abstentions": {
                "skill_gap": "no validated capability taxonomy or outcomes",
                "cross_user_collaboration": (
                    "single contributor and no reciprocal enterprise consent"
                ),
                "automatic_memory_write": (
                    "structural recurrence is insufficient for a durable fact "
                    "or procedure"
                ),
            },
        },
        "arm_overlap": {
            "eligible": {
                "S1_vs_S2": overlap(s1_candidates, s2_candidates),
                "S1_vs_S4": overlap(s1_candidates, s4_candidates),
                "S4_vs_S6": overlap(s4_candidates, s6_candidates),
                "all_four_intersection": len(
                    s1_candidates
                    & s2_candidates
                    & s4_candidates
                    & s6_candidates
                ),
            },
            "review_budget": {
                "S1_vs_S2": overlap(s1_review, s2_review),
                "S1_vs_S4": overlap(s1_review, s4_review),
                "S2_vs_S6": overlap(s2_review, s6_review),
                "all_four_intersection": len(
                    s1_review & s2_review & s4_review & s6_review
                ),
            },
        },
        "observed_failure_modes": {
            "malformed_records": sum(
                session.invalid_records for session in sessions
            ),
            "orphan_tool_calls": sum(
                session.orphan_calls for session in sessions
            ),
            "unlinked_tool_results": sum(
                session.unlinked_results for session in sessions
            ),
            "dangling_parent_references": sum(
                session.dangling_parents for session in sessions
            ),
            "parallel_successes_not_valid_retries": sum(
                session.ambiguous_parallel_successes
                for session in sessions
            ),
            "outcome_labels_available": 0,
            "environment_state_snapshots_available": 0,
            "authorization_and_classification_labels_available": 0,
            "stable_multi_user_organizational_relationships_available": 0,
        },
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus_root", type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    result = analyze_corpus(args.corpus_root.resolve(), manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
