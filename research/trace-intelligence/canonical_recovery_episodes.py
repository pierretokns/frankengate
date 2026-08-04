#!/usr/bin/env python3
"""Construct comparable, bounded failure-to-recovery trace episodes.

The constructor intentionally uses a very small vocabulary shared by both
Claude Code JSONL and share-codex exports:

* ``tool.proposed``
* ``tool.result.error``
* ``tool.result.success``

An episode is a structural review candidate, not evidence that a task was
correctly completed.  It requires:

1. an exporter-typed error result linked to one unique prior proposal;
2. a successful result linked to one unique prior proposal;
3. the successful call's proposal to occur *after* the error result;
4. the two calls to have the same controlled tool family;
5. the success result to fall inside one fixed lifecycle-event window; and
6. greedy, chronological, one-to-one assignment of successes to errors.

The CLI reads raw public data only from caller-supplied temporary locations.
It emits aggregate counts and controlled-vocabulary families; it never emits
transcript content, paths, native tool names, call/session/row identifiers, or
per-session records.
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import json
from pathlib import Path
from typing import Any, Iterable, Sequence


SCHEMA_VERSION = "canonical-bounded-recovery-episode-v1"
DEFAULT_MAX_LIFECYCLE_DISTANCE = 12
EXPECTED_SHARE_CODEX_REVISION_HEADER = "x-revision"

EVENT_PROPOSED = "tool.proposed"
EVENT_ERROR = "tool.result.error"
EVENT_SUCCESS = "tool.result.success"
EVENT_KINDS = frozenset({EVENT_PROPOSED, EVENT_ERROR, EVENT_SUCCESS})

# Only explicitly mapped names are eligible for same-family recovery matching.
# Collapsing every custom tool into one "other" family would create false
# cross-tool recovery pairs and would not be comparable across harnesses.
_TOOL_FAMILY_BY_CASEFOLD_NAME = {
    "apply_patch": "file_change",
    "edit": "file_change",
    "multiedit": "file_change",
    "notebookedit": "file_change",
    "write": "file_change",
    "read": "file_read",
    "glob": "file_search",
    "grep": "file_search",
    "bash": "shell",
    "exec_command": "shell",
    "shell": "shell",
    "shell_command": "shell",
    "write_stdin": "shell_session",
    "webfetch": "external_retrieval",
    "websearch": "external_retrieval",
    "web_search_call": "external_retrieval",
    "toolsearch": "tool_discovery",
    "taskcreate": "coordination",
    "taskupdate": "coordination",
    "taskoutput": "coordination",
    "update_plan": "coordination",
    "workflow": "delegation",
    "agent": "delegation",
    "skill": "skill_invocation",
    "askuserquestion": "human_interaction",
    "structuredoutput": "structured_output",
    "view_image": "media",
}


class EpisodeConstructionError(ValueError):
    """Raised when lifecycle input violates a constructor invariant."""


@dataclasses.dataclass(frozen=True)
class LifecycleEvent:
    """Content-free lifecycle event used by the common constructor.

    ``call_key`` is an ephemeral native correlation key.  It is permitted in
    memory but must never be serialized by :func:`aggregate_corpus`.
    """

    order: int
    kind: str
    call_key: str | None
    tool_family: str | None


@dataclasses.dataclass(frozen=True)
class RecoveryEpisode:
    """Internal evidence tuple; native keys are deliberately not included."""

    error_order: int
    recovery_proposal_order: int
    recovery_result_order: int
    tool_family: str

    @property
    def lifecycle_distance(self) -> int:
        return self.recovery_result_order - self.error_order


@dataclasses.dataclass(frozen=True)
class SessionConstruction:
    """Internal per-session result, reduced before CLI serialization."""

    lifecycle_events: int
    proposals: int
    error_results: int
    success_results: int
    linked_error_results: int
    linked_success_results: int
    eligible_error_results: int
    matched_episodes: tuple[RecoveryEpisode, ...]
    excluded_in_flight_candidate_pairs: int
    excluded_out_of_window_candidate_pairs: int
    excluded_unmapped_error_results: int
    excluded_unlinked_error_results: int
    unmatched_eligible_error_results: int


def tool_family(native_name: Any) -> str | None:
    """Map a native tool name into the shared controlled vocabulary."""
    if not isinstance(native_name, str) or not native_name:
        return None
    return _TOOL_FAMILY_BY_CASEFOLD_NAME.get(native_name.casefold())


def _tool_name_from_share_codex_call(call: dict[str, Any]) -> Any:
    function = call.get("function")
    if not isinstance(function, dict):
        return None
    return function.get("name")


def lifecycle_from_wisp_records(
    records: Iterable[dict[str, Any]],
) -> list[LifecycleEvent]:
    """Project Wisp/Claude Code records without reading content values."""
    events: list[LifecycleEvent] = []
    for record in records:
        message = record.get("message")
        if not isinstance(message, dict):
            continue
        blocks = message.get("content")
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "tool_use":
                call_key = block.get("id")
                events.append(
                    LifecycleEvent(
                        order=len(events),
                        kind=EVENT_PROPOSED,
                        call_key=(
                            call_key
                            if isinstance(call_key, str) and call_key
                            else None
                        ),
                        tool_family=tool_family(block.get("name")),
                    )
                )
            elif block_type == "tool_result":
                call_key = block.get("tool_use_id")
                is_error = (
                    block.get("is_error") is True
                    or block.get("isError") is True
                )
                events.append(
                    LifecycleEvent(
                        order=len(events),
                        kind=EVENT_ERROR if is_error else EVENT_SUCCESS,
                        call_key=(
                            call_key
                            if isinstance(call_key, str) and call_key
                            else None
                        ),
                        tool_family=None,
                    )
                )
    return events


def lifecycle_from_wisp_file(path: Path) -> list[LifecycleEvent]:
    """Read one Wisp JSONL file, skipping malformed/non-object records."""
    records: list[dict[str, Any]] = []
    with path.open("rb") as stream:
        for raw_line in stream:
            try:
                record = json.loads(raw_line)
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if isinstance(record, dict):
                records.append(record)
    return lifecycle_from_wisp_records(records)


def lifecycle_from_share_codex_row(
    row: dict[str, Any],
) -> list[LifecycleEvent]:
    """Project one share-codex session without reading transcript content."""
    messages = row.get("messages")
    if not isinstance(messages, list):
        return []
    events: list[LifecycleEvent] = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        calls = message.get("tool_calls")
        if isinstance(calls, list):
            for call in calls:
                if not isinstance(call, dict):
                    continue
                call_key = call.get("id")
                events.append(
                    LifecycleEvent(
                        order=len(events),
                        kind=EVENT_PROPOSED,
                        call_key=(
                            call_key
                            if isinstance(call_key, str) and call_key
                            else None
                        ),
                        tool_family=tool_family(
                            _tool_name_from_share_codex_call(call)
                        ),
                    )
                )
        if message.get("role") != "tool":
            continue
        call_key = message.get("tool_call_id")
        metadata = message.get("metadata")
        is_error = (
            isinstance(metadata, dict)
            and metadata.get("is_error") is True
        )
        events.append(
            LifecycleEvent(
                order=len(events),
                kind=EVENT_ERROR if is_error else EVENT_SUCCESS,
                call_key=(
                    call_key
                    if isinstance(call_key, str) and call_key
                    else None
                ),
                tool_family=None,
            )
        )
    return events


def _validate_events(
    events: Sequence[LifecycleEvent],
) -> tuple[LifecycleEvent, ...]:
    normalized = tuple(events)
    for expected_order, event in enumerate(normalized):
        if event.order != expected_order:
            raise EpisodeConstructionError(
                "lifecycle order must be dense, deterministic, and zero-based"
            )
        if event.kind not in EVENT_KINDS:
            raise EpisodeConstructionError(
                f"unsupported lifecycle event kind: {event.kind!r}"
            )
        if event.kind != EVENT_PROPOSED and event.tool_family is not None:
            raise EpisodeConstructionError(
                "result events inherit family only through linked proposals"
            )
    return normalized


def construct_recovery_episodes(
    events: Sequence[LifecycleEvent],
    *,
    max_lifecycle_distance: int = DEFAULT_MAX_LIFECYCLE_DISTANCE,
) -> SessionConstruction:
    """Build deterministic, greedy, one-to-one structural episodes."""
    if (
        not isinstance(max_lifecycle_distance, int)
        or max_lifecycle_distance <= 0
    ):
        raise EpisodeConstructionError(
            "max_lifecycle_distance must be a positive integer"
        )
    ordered = _validate_events(events)

    proposals_by_key: dict[str, list[LifecycleEvent]] = collections.defaultdict(
        list
    )
    result_counts_by_key: collections.Counter[str] = collections.Counter()
    for event in ordered:
        if event.kind == EVENT_PROPOSED and event.call_key is not None:
            proposals_by_key[event.call_key].append(event)
        elif event.kind in {EVENT_ERROR, EVENT_SUCCESS}:
            if event.call_key is not None:
                result_counts_by_key[event.call_key] += 1

    def linked_proposal(result: LifecycleEvent) -> LifecycleEvent | None:
        if result.call_key is None:
            return None
        proposals = proposals_by_key.get(result.call_key, [])
        # Unique proposal and unique result make correlation deterministic.
        if len(proposals) != 1 or result_counts_by_key[result.call_key] != 1:
            return None
        proposal = proposals[0]
        return proposal if proposal.order < result.order else None

    errors: list[tuple[LifecycleEvent, LifecycleEvent | None]] = []
    successes: list[tuple[LifecycleEvent, LifecycleEvent | None]] = []
    for event in ordered:
        if event.kind == EVENT_ERROR:
            errors.append((event, linked_proposal(event)))
        elif event.kind == EVENT_SUCCESS:
            successes.append((event, linked_proposal(event)))

    consumed_success_orders: set[int] = set()
    episodes: list[RecoveryEpisode] = []
    excluded_in_flight_pairs = 0
    excluded_out_of_window_pairs = 0
    excluded_unmapped_errors = 0
    excluded_unlinked_errors = 0
    eligible_errors = 0

    for error_result, error_proposal in errors:
        if error_proposal is None:
            excluded_unlinked_errors += 1
            continue
        if error_proposal.tool_family is None:
            excluded_unmapped_errors += 1
            continue
        eligible_errors += 1

        candidates: list[tuple[LifecycleEvent, LifecycleEvent]] = []
        for success_result, success_proposal in successes:
            if success_result.order in consumed_success_orders:
                continue
            if success_result.order <= error_result.order:
                continue
            if success_proposal is None:
                continue
            if success_proposal.tool_family != error_proposal.tool_family:
                continue
            if success_proposal.order <= error_result.order:
                if (
                    success_result.order - error_result.order
                    <= max_lifecycle_distance
                ):
                    excluded_in_flight_pairs += 1
                continue
            distance = success_result.order - error_result.order
            if distance > max_lifecycle_distance:
                excluded_out_of_window_pairs += 1
                continue
            candidates.append((success_result, success_proposal))

        if not candidates:
            continue
        # Stable earliest-success assignment implements chronological greedy
        # one-to-one matching without ranking on content.
        success_result, success_proposal = min(
            candidates,
            key=lambda pair: (pair[0].order, pair[1].order),
        )
        consumed_success_orders.add(success_result.order)
        episodes.append(
            RecoveryEpisode(
                error_order=error_result.order,
                recovery_proposal_order=success_proposal.order,
                recovery_result_order=success_result.order,
                tool_family=error_proposal.tool_family,
            )
        )

    return SessionConstruction(
        lifecycle_events=len(ordered),
        proposals=sum(event.kind == EVENT_PROPOSED for event in ordered),
        error_results=len(errors),
        success_results=len(successes),
        linked_error_results=sum(
            proposal is not None for _, proposal in errors
        ),
        linked_success_results=sum(
            proposal is not None for _, proposal in successes
        ),
        eligible_error_results=eligible_errors,
        matched_episodes=tuple(episodes),
        excluded_in_flight_candidate_pairs=excluded_in_flight_pairs,
        excluded_out_of_window_candidate_pairs=excluded_out_of_window_pairs,
        excluded_unmapped_error_results=excluded_unmapped_errors,
        excluded_unlinked_error_results=excluded_unlinked_errors,
        unmatched_eligible_error_results=eligible_errors - len(episodes),
    )


def _aggregate_sessions(
    sessions: Iterable[SessionConstruction],
) -> dict[str, Any]:
    totals: collections.Counter[str] = collections.Counter()
    family_counts: collections.Counter[str] = collections.Counter()
    session_count = 0
    sessions_with_error = 0
    sessions_with_episode = 0
    distances: list[int] = []
    for session in sessions:
        session_count += 1
        if session.error_results:
            sessions_with_error += 1
        if session.matched_episodes:
            sessions_with_episode += 1
        for field in (
            "lifecycle_events",
            "proposals",
            "error_results",
            "success_results",
            "linked_error_results",
            "linked_success_results",
            "eligible_error_results",
            "excluded_in_flight_candidate_pairs",
            "excluded_out_of_window_candidate_pairs",
            "excluded_unmapped_error_results",
            "excluded_unlinked_error_results",
            "unmatched_eligible_error_results",
        ):
            totals[field] += int(getattr(session, field))
        totals["matched_episodes"] += len(session.matched_episodes)
        for episode in session.matched_episodes:
            family_counts[episode.tool_family] += 1
            distances.append(episode.lifecycle_distance)

    eligible = totals["eligible_error_results"]
    matched = totals["matched_episodes"]
    return {
        "units": {
            "sessions": session_count,
            "sessions_with_explicit_error": sessions_with_error,
            "sessions_with_matched_episode": sessions_with_episode,
        },
        "lifecycle": {
            key: totals[key]
            for key in (
                "lifecycle_events",
                "proposals",
                "error_results",
                "success_results",
                "linked_error_results",
                "linked_success_results",
            )
        },
        "constructor": {
            key: totals[key]
            for key in (
                "eligible_error_results",
                "matched_episodes",
                "unmatched_eligible_error_results",
                "excluded_in_flight_candidate_pairs",
                "excluded_out_of_window_candidate_pairs",
                "excluded_unmapped_error_results",
                "excluded_unlinked_error_results",
            )
        },
        "matched_episode_share_of_eligible_errors": (
            round(matched / eligible, 6) if eligible else None
        ),
        "matched_episode_family_counts": dict(sorted(family_counts.items())),
        "lifecycle_distance": {
            "minimum": min(distances) if distances else None,
            "maximum": max(distances) if distances else None,
            "mean": (
                round(sum(distances) / len(distances), 6)
                if distances
                else None
            ),
        },
    }


def aggregate_wisp(
    root: Path,
    *,
    max_lifecycle_distance: int,
) -> dict[str, Any]:
    paths = sorted(path for path in root.rglob("*.jsonl") if path.is_file())
    if not paths:
        raise EpisodeConstructionError(
            "Wisp root contains no JSONL files; refusing an empty run"
        )
    sessions = (
        construct_recovery_episodes(
            lifecycle_from_wisp_file(path),
            max_lifecycle_distance=max_lifecycle_distance,
        )
        for path in paths
    )
    result = _aggregate_sessions(sessions)
    result["source_files"] = len(paths)
    return result


def _read_revision_header(path: Path) -> str | None:
    for line in path.read_text(encoding="utf-8").splitlines():
        name, separator, value = line.partition(":")
        if (
            separator
            and name.strip().lower()
            == EXPECTED_SHARE_CODEX_REVISION_HEADER
        ):
            return value.strip()
    return None


def aggregate_share_codex(
    sample_dir: Path,
    *,
    expected_revision: str,
    max_lifecycle_distance: int,
    expected_requests: Sequence[dict[str, Any]] | None = None,
    expected_population_rows: int | None = None,
) -> dict[str, Any]:
    payload_paths = sorted(sample_dir.glob("share-codex.rows-*.json"))
    if not payload_paths:
        raise EpisodeConstructionError(
            "share-codex sample contains no responses; refusing an empty run"
        )
    requests_by_offset = (
        {
            int(request["offset"]): int(request["length"])
            for request in expected_requests
        }
        if expected_requests is not None
        else None
    )
    observed_offsets: set[int] = set()
    sessions: list[SessionConstruction] = []
    for payload_path in payload_paths:
        try:
            offset = int(
                payload_path.stem.removeprefix("share-codex.rows-")
            )
        except ValueError as error:
            raise EpisodeConstructionError(
                "share-codex response filename has a non-integer offset"
            ) from error
        if requests_by_offset is not None and offset not in requests_by_offset:
            raise EpisodeConstructionError(
                "share-codex response is outside the pinned sample design"
            )
        if offset in observed_offsets:
            raise EpisodeConstructionError(
                "duplicate share-codex response offset"
            )
        observed_offsets.add(offset)
        header_path = payload_path.with_suffix(".headers")
        if not header_path.is_file():
            raise EpisodeConstructionError(
                "share-codex response is missing its revision header file"
            )
        revision = _read_revision_header(header_path)
        if revision != expected_revision:
            raise EpisodeConstructionError(
                "share-codex response revision does not match manifest"
            )
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        if payload.get("partial") is not False:
            raise EpisodeConstructionError(
                "partial share-codex response is not admissible"
            )
        rows = payload.get("rows")
        if not isinstance(rows, list):
            raise EpisodeConstructionError(
                "share-codex response rows must be a list"
            )
        if (
            expected_population_rows is not None
            and payload.get("num_rows_total") != expected_population_rows
        ):
            raise EpisodeConstructionError(
                "share-codex population row count changed"
            )
        if requests_by_offset is not None:
            expected_length = requests_by_offset[offset]
            if len(rows) != expected_length:
                raise EpisodeConstructionError(
                    "share-codex response length differs from sample design"
                )
            observed_indices = [
                wrapper.get("row_idx")
                if isinstance(wrapper, dict)
                else None
                for wrapper in rows
            ]
            if observed_indices != list(
                range(offset, offset + expected_length)
            ):
                raise EpisodeConstructionError(
                    "share-codex row indices differ from sample design"
                )
        for wrapper in rows:
            if not isinstance(wrapper, dict):
                raise EpisodeConstructionError(
                    "share-codex row wrapper must be an object"
                )
            row = wrapper.get("row")
            if not isinstance(row, dict):
                raise EpisodeConstructionError(
                    "share-codex row must be an object"
                )
            sessions.append(
                construct_recovery_episodes(
                    lifecycle_from_share_codex_row(row),
                    max_lifecycle_distance=max_lifecycle_distance,
                )
            )
    if (
        requests_by_offset is not None
        and observed_offsets != set(requests_by_offset)
    ):
        raise EpisodeConstructionError(
            "share-codex sample is incomplete for the pinned design"
        )
    result = _aggregate_sessions(sessions)
    result["source_response_files"] = len(payload_paths)
    return result


def run_comparison(
    *,
    wisp_root: Path,
    share_codex_sample_dir: Path,
    wisp_manifest: dict[str, Any],
    share_codex_manifest: dict[str, Any],
    max_lifecycle_distance: int = DEFAULT_MAX_LIFECYCLE_DISTANCE,
) -> dict[str, Any]:
    """Run both corpus adapters and emit an aggregate-only comparison."""
    wisp = aggregate_wisp(
        wisp_root,
        max_lifecycle_distance=max_lifecycle_distance,
    )
    share_codex = aggregate_share_codex(
        share_codex_sample_dir,
        expected_revision=share_codex_manifest["dataset_revision"],
        max_lifecycle_distance=max_lifecycle_distance,
        expected_requests=share_codex_manifest["sample_design"]["requests"],
        expected_population_rows=share_codex_manifest["population_rows"],
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "constructor_contract": {
            "event_vocabulary": sorted(EVENT_KINDS),
            "max_lifecycle_distance": max_lifecycle_distance,
            "requires_exporter_typed_error": True,
            "requires_unique_prior_proposal_and_unique_result": True,
            "requires_recovery_proposal_after_error": True,
            "requires_same_controlled_tool_family": True,
            "matching": "chronological_greedy_one_to_one",
            "interpretation": (
                "structural review candidate; not correctness, task success, "
                "causal recovery, user skill, or productivity"
            ),
        },
        "sources": {
            "wisp": {
                "dataset_id": wisp_manifest["dataset_id"],
                "dataset_revision": wisp_manifest["dataset_revision"],
                "sampling": "released corpus snapshot",
            },
            "share_codex_sparse": {
                "dataset_id": share_codex_manifest["dataset_id"],
                "dataset_revision": share_codex_manifest["dataset_revision"],
                "sampling": share_codex_manifest["sample_design"]["name"],
            },
        },
        "privacy": {
            "raw_data_committed": False,
            "transcript_content_emitted": False,
            "native_identifiers_emitted": False,
            "native_tool_names_emitted": False,
            "per_session_records_emitted": False,
            "controlled_vocabulary_aggregates_only": True,
        },
        "corpora": {
            "wisp": wisp,
            "share_codex_sparse": share_codex,
        },
        "comparability": {
            "aligned": [
                "lifecycle event vocabulary",
                "explicit error requirement",
                "unique call-result linkage",
                "post-error recovery proposal requirement",
                "controlled tool-family equality",
                "lifecycle-event distance",
                "greedy one-to-one matching",
            ],
            "not_aligned": [
                "corpus sampling frame",
                "harness exporter error semantics",
                "task mix and user population",
                "task correctness and outcome labels",
            ],
            "permitted_claim": (
                "constructor portability and structural candidate prevalence "
                "within each analyzed sample"
            ),
            "prohibited_claim": (
                "behavioral difference, productivity, skill, or causal "
                "improvement between corpora"
            ),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wisp-root", type=Path, required=True)
    parser.add_argument("--share-codex-sample-dir", type=Path, required=True)
    parser.add_argument("--wisp-manifest", type=Path, required=True)
    parser.add_argument("--share-codex-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--max-lifecycle-distance",
        type=int,
        default=DEFAULT_MAX_LIFECYCLE_DISTANCE,
    )
    args = parser.parse_args()

    wisp_manifest = json.loads(
        args.wisp_manifest.read_text(encoding="utf-8")
    )
    share_codex_manifest = json.loads(
        args.share_codex_manifest.read_text(encoding="utf-8")
    )
    result = run_comparison(
        wisp_root=args.wisp_root,
        share_codex_sample_dir=args.share_codex_sample_dir,
        wisp_manifest=wisp_manifest,
        share_codex_manifest=share_codex_manifest,
        max_lifecycle_distance=args.max_lifecycle_distance,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "schema_version": result["schema_version"],
                "wisp_sessions": result["corpora"]["wisp"]["units"][
                    "sessions"
                ],
                "wisp_episodes": result["corpora"]["wisp"]["constructor"][
                    "matched_episodes"
                ],
                "share_codex_sessions": result["corpora"][
                    "share_codex_sparse"
                ]["units"]["sessions"],
                "share_codex_episodes": result["corpora"][
                    "share_codex_sparse"
                ]["constructor"]["matched_episodes"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
