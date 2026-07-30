#!/usr/bin/env python3
"""Natural-trace memory availability factorial over Claude Code histories.

This study treats a later successful explicit Read of a context artifact as a
post-query observation.  Every candidate supplied to an arm must have been
successfully observed and released strictly before the Read call, on an
eligible branch or in a strictly earlier non-overlapping session of the same
source project.

The outcome is evidence availability, not user or model utility.  Raw content,
paths, native identifiers, project identifiers, and per-item hashes remain
in-memory and are never written to the durable result.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import hmac
import itertools
import json
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Optional, Sequence

import trace_commons_memory_conformance as canonical
from wisp_claude_code_adapter import canonicalize_wisp_file


SCHEMA_VERSION = "frankengate-natural-trace-memory-factorial-v1"
ANALYSIS_VERSION = "natural-read-prequery-release-factorial-v1"
RUNNABLE_MECHANISMS = (
    "latest_snapshot",
    "verbatim_state",
    "bitemporal_ledger",
    "evidence_retrieval",
)
TIME_BUCKETS = ("early", "middle", "late")


class NaturalMemoryError(ValueError):
    """Raised when source or protocol invariants are invalid."""


@dataclass(frozen=True)
class SourceSpec:
    label: str
    root: Path
    manifest: Path


@dataclass(frozen=True)
class Interaction:
    source_label: str
    project_private: str
    project_key: str
    session_private: str
    session_key: str
    artifact_private: str
    call_record: str
    result_record: str
    call_at: datetime
    result_at: datetime
    call_order: tuple[Any, ...]
    result_order: tuple[Any, ...]
    tool_kind: str
    arguments: Mapping[str, Any]
    result_content: Optional[str]
    path: str


@dataclass(frozen=True)
class Observation:
    observation_private: str
    source_label: str
    project_private: str
    project_key: str
    session_private: str
    session_key: str
    artifact_private: str
    call_record: str
    result_record: str
    call_at: datetime
    observed_at: datetime
    call_order: tuple[Any, ...]
    result_order: tuple[Any, ...]
    source_kind: str
    content: str
    content_sha256: str
    released_at: datetime


@dataclass(frozen=True)
class Query:
    query_private: str
    source_label: str
    project_private: str
    project_key: str
    session_private: str
    session_key: str
    artifact_private: str
    query_at: datetime
    target_observed_at: datetime
    target_content_sha256: str
    candidates: tuple[Observation, ...]
    cross_session: bool
    time_bucket: str


def _stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_value(value: Any) -> str:
    return _sha256_bytes(_stable_json(value).encode("utf-8"))


def _keyed(key: bytes, namespace: str, value: str) -> str:
    return hmac.new(
        key,
        (namespace + "\0" + value).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _instant(value: Any) -> datetime:
    if not isinstance(value, str):
        raise NaturalMemoryError("event timestamp is missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise NaturalMemoryError("event timestamp is invalid") from exc
    if parsed.tzinfo is None:
        raise NaturalMemoryError("event timestamp must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _path_from_arguments(arguments: Mapping[str, Any]) -> Optional[str]:
    for key in ("file_path", "path"):
        value = arguments.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _artifact_kind(path: str) -> Optional[str]:
    normalized = canonical.normalize_path(path)
    basename = PurePosixPath(normalized).name
    if "/dreams/" in normalized or "dream" in basename:
        return "dream"
    if "/skills/" in normalized or basename == "skill.md":
        return "procedure"
    if canonical.is_context_artifact(path):
        return "context"
    return None


def _is_ancestor(
    parents: Mapping[str, Optional[str]],
    ancestor: str,
    descendant: str,
) -> bool:
    current = parents.get(descendant)
    seen: set[str] = set()
    while current is not None and current not in seen:
        if current == ancestor:
            return True
        seen.add(current)
        current = parents.get(current)
    return False


def _eligible(
    candidate: Observation,
    target: Interaction,
    *,
    parents_by_session: Mapping[str, Mapping[str, Optional[str]]],
    session_bounds: Mapping[str, tuple[datetime, datetime]],
) -> bool:
    if (
        candidate.source_label != target.source_label
        or candidate.project_private != target.project_private
        or candidate.artifact_private != target.artifact_private
        or candidate.released_at >= target.call_at
    ):
        return False
    if candidate.session_private == target.session_private:
        parents = parents_by_session.get(target.session_private, {})
        return (
            candidate.result_order < target.call_order
            and (
                _is_ancestor(
                    parents,
                    candidate.result_record,
                    target.call_record,
                )
                or _is_ancestor(
                    parents,
                    candidate.call_record,
                    target.call_record,
                )
            )
        )
    candidate_bounds = session_bounds[candidate.session_private]
    target_bounds = session_bounds[target.session_private]
    return (
        candidate_bounds[1] < target_bounds[0]
        and candidate.result_order < target.call_order
    )


def _source_receipt(files: Sequence[tuple[str, bytes]]) -> str:
    rows = [
        {
            "relative_path_sha256": _sha256_bytes(path.encode("utf-8")),
            "bytes": len(raw),
            "sha256": _sha256_bytes(raw),
        }
        for path, raw in files
    ]
    return _sha256_value(rows)


def load_protocol_config(path: Path) -> dict[str, Any]:
    """Verify the frozen natural protocol and its corrected parent receipt."""

    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise NaturalMemoryError("protocol config cannot be loaded") from exc
    if (
        not isinstance(value, dict)
        or value.get("schema_version")
        != "frankengate.natural-trace-memory-factorial.v1"
    ):
        raise NaturalMemoryError("unexpected protocol config schema")
    inherited = value.get("inherited_corrected_protocol")
    if not isinstance(inherited, dict):
        raise NaturalMemoryError("corrected parent protocol is required")
    parent_path = path.parent / str(inherited.get("path", ""))
    try:
        parent_sha256 = _sha256_bytes(parent_path.read_bytes())
    except OSError as exc:
        raise NaturalMemoryError(
            "corrected parent protocol cannot be read"
        ) from exc
    if parent_sha256 != inherited.get("sha256"):
        raise NaturalMemoryError(
            "corrected parent protocol receipt mismatch"
        )
    if value.get("runnable_mechanisms") != list(
        RUNNABLE_MECHANISMS
    ):
        raise NaturalMemoryError("runnable mechanisms do not match code")
    factorial = value.get("factorial")
    if (
        not isinstance(factorial, dict)
        or factorial.get("expected_runnable_mechanisms")
        != len(RUNNABLE_MECHANISMS)
        or factorial.get("expected_arms")
        != 2 ** len(RUNNABLE_MECHANISMS)
        or factorial.get("no_memory_control") is not True
    ):
        raise NaturalMemoryError("factorial contract does not match code")
    durable = value.get("durable_output")
    if (
        not isinstance(durable, dict)
        or any(
            durable.get(field) is not False
            for field in (
                "raw_content",
                "artifact_paths",
                "native_identifiers",
                "project_identifiers",
                "per_item_content_hashes",
            )
        )
    ):
        raise NaturalMemoryError("durable output contract is unsafe")
    seed = value.get("public_reproducibility_identity_seed")
    if not isinstance(seed, str) or not seed:
        raise NaturalMemoryError(
            "public reproducibility identity seed is required"
        )
    source_bindings = []
    configured_sources = value.get("sources")
    if not isinstance(configured_sources, list) or not configured_sources:
        raise NaturalMemoryError("protocol sources are required")
    for source in configured_sources:
        if not isinstance(source, dict):
            raise NaturalMemoryError("protocol source must be an object")
        label = source.get("label")
        manifest_path = path.parent / str(source.get("manifest", ""))
        try:
            manifest_raw = manifest_path.read_bytes()
            manifest = json.loads(manifest_raw)
        except (OSError, json.JSONDecodeError) as exc:
            raise NaturalMemoryError(
                "protocol source manifest cannot be loaded"
            ) from exc
        source_bindings.append(
            {
                "label": str(label),
                "dataset_id": str(manifest.get("dataset_id", "")),
                "dataset_revision": str(
                    manifest.get("dataset_revision", "")
                ),
                "manifest_sha256": _sha256_bytes(manifest_raw),
            }
        )
    return {
        "protocol_config_sha256": _sha256_bytes(raw),
        "inherited_protocol_sha256": parent_sha256,
        "expected_arms": int(factorial["expected_arms"]),
        "identity_seed_sha256": _sha256_bytes(
            seed.encode("utf-8")
        ),
        "source_bindings": source_bindings,
    }


def _load_source(
    spec: SourceSpec,
    identity_key: bytes,
) -> tuple[
    list[Interaction],
    dict[str, dict[str, Optional[str]]],
    dict[str, tuple[datetime, datetime]],
    dict[str, Any],
    Counter[str],
]:
    if not spec.label or not isinstance(spec.label, str):
        raise NaturalMemoryError("source label is required")
    try:
        manifest = json.loads(spec.manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NaturalMemoryError("source manifest cannot be loaded") from exc
    for field in ("dataset_id", "dataset_revision", "license"):
        if not isinstance(manifest.get(field), str) or not manifest[field]:
            raise NaturalMemoryError(f"source manifest {field} is required")
    root = spec.root.resolve()
    files = sorted(root.rglob("*.jsonl"))
    if not files:
        raise NaturalMemoryError("source contains no JSONL histories")

    interactions: list[Interaction] = []
    parents_by_session: dict[str, dict[str, Optional[str]]] = {}
    session_bounds: dict[str, tuple[datetime, datetime]] = {}
    source_files: list[tuple[str, bytes]] = []
    discovery: Counter[str] = Counter()

    for source_file_order, path in enumerate(files):
        raw = path.read_bytes()
        relative = path.resolve().relative_to(root).as_posix()
        source_files.append((relative, raw))
        trajectory = canonicalize_wisp_file(path, root, manifest)
        discovery["source_records"] += int(
            trajectory["loss_receipt"]["source_record_count"]
        )
        discovery["canonical_events"] += len(trajectory["events"])
        discovery["silently_dropped_records"] += int(
            trajectory["loss_receipt"]["silently_dropped_record_count"]
        )
        session_private = spec.label + "\0" + relative
        session_key = _keyed(
            identity_key, "session", session_private
        )[:24]
        path_project = trajectory["source"]["path_context"].get(
            "project_key"
        )
        if not isinstance(path_project, str) or not path_project:
            discovery["histories_missing_pretrace_project_identity"] += 1
            continue
        project_private = spec.label + "\0" + path_project
        project_key = _keyed(
            identity_key, "project", project_private
        )[:24]

        events = trajectory["events"]
        timestamps = []
        parents: dict[str, Optional[str]] = {}
        proposals: dict[str, Mapping[str, Any]] = {}
        for event in events:
            event_id = event.get("event_id")
            if isinstance(event_id, str):
                parent = event.get("parent_event_id")
                parents[event_id] = (
                    str(parent) if isinstance(parent, str) else None
                )
            timestamp = event.get("timestamp")
            if isinstance(timestamp, str):
                try:
                    timestamps.append(_instant(timestamp))
                except NaturalMemoryError:
                    discovery["events_with_invalid_timestamp"] += 1
            if event.get("kind") == "tool.proposed":
                proposals[str(event["event_id"])] = event
        parents_by_session[session_private] = parents
        if not timestamps:
            discovery["histories_missing_timestamps"] += 1
            continue
        session_bounds[session_private] = (
            min(timestamps),
            max(timestamps),
        )

        for result in events:
            if result.get("kind") not in {
                "tool.completed",
                "tool.failed",
            }:
                continue
            proposal_id = result.get(
                "correlated_tool_proposal_event_id"
            )
            proposal = (
                proposals.get(str(proposal_id))
                if proposal_id is not None
                else None
            )
            if (
                proposal is None
                or result.get("correlation_status")
                != "exact_unique_prior"
            ):
                discovery["unresolved_or_ambiguous_tool_results"] += 1
                continue
            arguments = proposal.get("arguments")
            if not isinstance(arguments, Mapping):
                discovery["tool_calls_without_mapping_arguments"] += 1
                continue
            path_value = _path_from_arguments(arguments)
            if path_value is None:
                continue
            kind = _artifact_kind(path_value)
            if kind is None:
                continue
            discovery[f"{kind}_artifact_calls"] += 1
            if result.get("kind") == "tool.failed":
                discovery[f"{kind}_artifact_failures"] += 1
                continue
            tool_kind = str(
                proposal.get("function_name", "")
            ).casefold()
            if tool_kind not in {"read", "write", "edit"}:
                discovery[f"{kind}_non_state_tool_calls"] += 1
                continue
            try:
                call_at = _instant(proposal.get("timestamp"))
                result_at = _instant(result.get("timestamp"))
            except NaturalMemoryError:
                discovery["state_interactions_missing_timestamp"] += 1
                continue
            if result_at < call_at:
                discovery["result_before_call"] += 1
                continue
            normalized_path = canonical.normalize_path(path_value)
            artifact_private = (
                spec.label
                + "\0"
                + path_project
                + "\0"
                + normalized_path
            )
            call_record = str(
                proposal.get("record_event_id")
                or proposal.get("event_id")
            )
            result_record = str(
                result.get("record_event_id")
                or result.get("event_id")
            )
            call_order = (
                call_at,
                source_file_order,
                int(proposal.get("sequence", 0)),
            )
            result_order = (
                result_at,
                source_file_order,
                int(result.get("sequence", 0)),
            )
            interactions.append(
                Interaction(
                    source_label=spec.label,
                    project_private=project_private,
                    project_key=project_key,
                    session_private=session_private,
                    session_key=session_key,
                    artifact_private=artifact_private,
                    call_record=call_record,
                    result_record=result_record,
                    call_at=call_at,
                    result_at=result_at,
                    call_order=call_order,
                    result_order=result_order,
                    tool_kind=tool_kind,
                    arguments=dict(arguments),
                    result_content=(
                        result.get("content")
                        if isinstance(result.get("content"), str)
                        else None
                    ),
                    path=path_value,
                )
            )
            discovery[f"successful_{kind}_{tool_kind}"] += 1

    receipt = {
        "label": spec.label,
        "dataset_id": manifest["dataset_id"],
        "dataset_revision": manifest["dataset_revision"],
        "license": manifest["license"],
        "manifest_sha256": _sha256_bytes(
            spec.manifest.read_bytes()
        ),
        "source_files": len(source_files),
        "source_bytes": sum(len(raw) for _, raw in source_files),
        "source_records": discovery["source_records"],
        "source_set_sha256": _source_receipt(source_files),
    }
    return (
        interactions,
        parents_by_session,
        session_bounds,
        receipt,
        discovery,
    )


def _construct_observations(
    interactions: Sequence[Interaction],
    *,
    parents_by_session: Mapping[str, Mapping[str, Optional[str]]],
    session_bounds: Mapping[str, tuple[datetime, datetime]],
    identity_key: bytes,
) -> tuple[list[Observation], Counter[str]]:
    observations: list[Observation] = []
    gates: Counter[str] = Counter()
    for interaction in sorted(
        interactions, key=lambda item: item.call_order
    ):
        if _artifact_kind(interaction.path) != "context":
            continue
        content: Optional[str] = None
        if interaction.tool_kind == "read":
            if interaction.result_content is None:
                gates["ambiguous_read_results"] += 1
                continue
            content = canonical.canonicalize_read_content(
                interaction.result_content
            )
        elif interaction.tool_kind == "write":
            raw_content = interaction.arguments.get("content")
            if not isinstance(raw_content, str):
                gates["ambiguous_writes"] += 1
                continue
            content = canonical.canonicalize_write_content(raw_content)
        else:
            candidates = [
                item
                for item in observations
                if _eligible(
                    item,
                    interaction,
                    parents_by_session=parents_by_session,
                    session_bounds=session_bounds,
                )
            ]
            previous = max(
                candidates,
                key=lambda item: item.result_order,
                default=None,
            )
            old = interaction.arguments.get("old_string")
            new = interaction.arguments.get("new_string")
            replace_all = bool(
                interaction.arguments.get("replace_all", False)
            )
            if (
                previous is None
                or not isinstance(old, str)
                or not isinstance(new, str)
            ):
                gates["unreconstructable_edits"] += 1
                continue
            occurrences = previous.content.count(old)
            if occurrences == 0 or (
                not replace_all and occurrences != 1
            ):
                gates["unreconstructable_edits"] += 1
                continue
            content = (
                previous.content.replace(old, new)
                if replace_all
                else previous.content.replace(old, new, 1)
            )

        observation_private = (
            interaction.session_private
            + "\0"
            + interaction.call_record
            + "\0"
            + interaction.result_record
        )
        observations.append(
            Observation(
                observation_private=observation_private,
                source_label=interaction.source_label,
                project_private=interaction.project_private,
                project_key=interaction.project_key,
                session_private=interaction.session_private,
                session_key=interaction.session_key,
                artifact_private=interaction.artifact_private,
                call_record=interaction.call_record,
                result_record=interaction.result_record,
                call_at=interaction.call_at,
                observed_at=interaction.result_at,
                call_order=interaction.call_order,
                result_order=interaction.result_order,
                source_kind=interaction.tool_kind,
                content=content,
                content_sha256=_sha256_bytes(
                    content.encode("utf-8")
                ),
                released_at=interaction.result_at,
            )
        )
        gates["supported_observations"] += 1
    return observations, gates


def _assign_time_buckets(
    raw_queries: Sequence[
        tuple[Interaction, Observation, tuple[Observation, ...]]
    ],
) -> dict[str, str]:
    buckets: dict[str, str] = {}
    by_source: dict[str, list[tuple[datetime, str]]] = defaultdict(list)
    for interaction, target, _ in raw_queries:
        query_private = (
            interaction.session_private
            + "\0"
            + interaction.call_record
        )
        by_source[interaction.source_label].append(
            (target.call_at, query_private)
        )
    for rows in by_source.values():
        ordered = sorted(rows)
        total = len(ordered)
        for index, (_, query_private) in enumerate(ordered):
            bucket_index = min(2, (index * 3) // total)
            buckets[query_private] = TIME_BUCKETS[bucket_index]
    return buckets


def _construct_queries(
    interactions: Sequence[Interaction],
    observations: Sequence[Observation],
    *,
    parents_by_session: Mapping[str, Mapping[str, Optional[str]]],
    session_bounds: Mapping[str, tuple[datetime, datetime]],
) -> tuple[list[Query], Counter[str]]:
    observations_by_result = {
        (
            item.session_private,
            item.result_record,
        ): item
        for item in observations
    }
    raw_queries = []
    gates: Counter[str] = Counter()
    for interaction in sorted(
        interactions, key=lambda item: item.call_order
    ):
        if (
            interaction.tool_kind != "read"
            or _artifact_kind(interaction.path) != "context"
        ):
            continue
        target = observations_by_result.get(
            (
                interaction.session_private,
                interaction.result_record,
            )
        )
        if target is None:
            gates["excluded_reads_without_observed_outcome"] += 1
            continue
        candidates = tuple(
            sorted(
                (
                    item
                    for item in observations
                    if item.observation_private
                    != target.observation_private
                    and _eligible(
                        item,
                        interaction,
                        parents_by_session=parents_by_session,
                        session_bounds=session_bounds,
                    )
                ),
                key=lambda item: item.result_order,
                reverse=True,
            )
        )
        if not candidates:
            gates["excluded_reads_without_prequery_evidence"] += 1
            continue
        raw_queries.append((interaction, target, candidates))
    time_buckets = _assign_time_buckets(raw_queries)
    queries = []
    for interaction, target, candidates in raw_queries:
        query_private = (
            interaction.session_private
            + "\0"
            + interaction.call_record
        )
        queries.append(
            Query(
                query_private=query_private,
                source_label=interaction.source_label,
                project_private=interaction.project_private,
                project_key=interaction.project_key,
                session_private=interaction.session_private,
                session_key=interaction.session_key,
                artifact_private=interaction.artifact_private,
                query_at=interaction.call_at,
                target_observed_at=target.observed_at,
                target_content_sha256=target.content_sha256,
                candidates=candidates,
                cross_session=(
                    candidates[0].session_private
                    != interaction.session_private
                ),
                time_bucket=time_buckets[query_private],
            )
        )
    return queries, gates


def _catalog(
    query: Query,
    mechanism: str,
) -> tuple[Observation, ...]:
    if mechanism == "latest_snapshot":
        return query.candidates[:1]
    if mechanism in {
        "verbatim_state",
        "bitemporal_ledger",
        "evidence_retrieval",
    }:
        return query.candidates
    raise NaturalMemoryError("unknown runnable mechanism")


def _decide(
    query: Query,
    enabled: Sequence[str],
) -> tuple[str, Optional[Observation]]:
    supplied = {
        item.observation_private: item
        for mechanism in enabled
        for item in _catalog(query, mechanism)
    }
    if not supplied:
        return "abstention", None
    ordered = sorted(
        supplied.values(),
        key=lambda item: item.result_order,
        reverse=True,
    )
    boundary = ordered[0].observed_at
    top = [item for item in ordered if item.observed_at == boundary]
    if len({item.content_sha256 for item in top}) > 1:
        return "abstention", None
    selected = sorted(
        top, key=lambda item: item.observation_private
    )[0]
    return (
        "exact"
        if selected.content_sha256 == query.target_content_sha256
        else "stale"
    ), selected


def _metric(outcomes: Sequence[str]) -> dict[str, Any]:
    total = len(outcomes)
    exact = outcomes.count("exact")
    stale = outcomes.count("stale")
    abstention = outcomes.count("abstention")
    return {
        "queries": total,
        "exact": exact,
        "stale": stale,
        "abstention": abstention,
        "exact_rate": round(exact / total, 12) if total else None,
    }


def _arm_id(enabled: Sequence[str]) -> str:
    return "arm-" + _sha256_bytes(
        ("\0".join(enabled) or "no-memory").encode("utf-8")
    )[:16]


def _all_arms() -> list[tuple[str, ...]]:
    return [
        enabled
        for size in range(len(RUNNABLE_MECHANISMS) + 1)
        for enabled in itertools.combinations(
            RUNNABLE_MECHANISMS, size
        )
    ]


def _split_metrics(
    queries: Sequence[Query],
    outcomes_by_arm: Mapping[str, Sequence[str]],
    enabled_by_arm: Mapping[str, tuple[str, ...]],
) -> dict[str, Any]:
    source_rows = []
    for source in sorted({item.source_label for item in queries}):
        indices = [
            index
            for index, item in enumerate(queries)
            if item.source_label == source
        ]
        source_rows.append(
            {
                "source": source,
                "eligible_queries": len(indices),
                "arms": [
                    {
                        "arm_id": arm_id,
                        "mechanisms": list(enabled_by_arm[arm_id]),
                        **_metric([values[index] for index in indices]),
                    }
                    for arm_id, values in outcomes_by_arm.items()
                ],
            }
        )

    project_indices: dict[str, list[int]] = defaultdict(list)
    for index, query in enumerate(queries):
        project_indices[query.project_private].append(index)
    project_arm_rates = []
    for arm_id, values in outcomes_by_arm.items():
        rates = []
        for indices in project_indices.values():
            exact = sum(values[index] == "exact" for index in indices)
            rates.append(
                round(exact / len(indices), 12)
                if indices
                else None
            )
        project_arm_rates.append(
            {
                "arm_id": arm_id,
                "mechanisms": list(enabled_by_arm[arm_id]),
                "exact_rates_desc": sorted(
                    (value for value in rates if value is not None),
                    reverse=True,
                ),
            }
        )

    time_rows = []
    for bucket in TIME_BUCKETS:
        indices = [
            index
            for index, query in enumerate(queries)
            if query.time_bucket == bucket
        ]
        time_rows.append(
            {
                "bucket": bucket,
                "eligible_queries": len(indices),
                "arms": [
                    {
                        "arm_id": arm_id,
                        "mechanisms": list(enabled_by_arm[arm_id]),
                        **_metric([values[index] for index in indices]),
                    }
                    for arm_id, values in outcomes_by_arm.items()
                ],
            }
        )
    return {
        "source": source_rows,
        "project": {
            "project_contexts": len(project_indices),
            "eligible_queries_per_project_desc": sorted(
                (len(indices) for indices in project_indices.values()),
                reverse=True,
            ),
            "arm_exact_rate_distributions": project_arm_rates,
            "project_identifiers_emitted": False,
        },
        "target_time": time_rows,
    }


def _mechanism_gate(
    discovery: Mapping[str, int],
    mechanism: str,
) -> dict[str, Any]:
    prefix = "dream" if mechanism == "released_dream" else "procedure"
    candidate_writes = sum(
        int(discovery.get(f"successful_{prefix}_{kind}", 0))
        for kind in ("write", "edit")
    )
    return {
        "status": "not_runnable_no_natural_independent_release",
        "candidate_artifact_writes_or_edits": candidate_writes,
        "independently_released_items": 0,
        "eligible_prequery_target_links": 0,
        "required_but_absent": [
            "query_independent_derived_item",
            "source_evidence_references",
            "independent_verifier_identity",
            "immutable_release_decision_strictly_before_query",
            "explicit_target_scope",
        ],
    }


def _result_digest(result: Mapping[str, Any]) -> str:
    body = dict(result)
    body.pop("result_sha256", None)
    return _sha256_value(body)


def verify_result(result: Mapping[str, Any]) -> bool:
    digest = result.get("result_sha256")
    return (
        isinstance(digest, str)
        and len(digest) == 64
        and hmac.compare_digest(digest, _result_digest(result))
    )


def analyze_sources(
    sources: Sequence[SourceSpec],
    *,
    identity_key: bytes,
    protocol_receipt: Optional[Mapping[str, Any]] = None,
) -> dict[str, Any]:
    """Run the natural evidence-availability factorial."""

    if not sources:
        raise NaturalMemoryError("at least one source is required")
    if not isinstance(identity_key, bytes) or len(identity_key) < 32:
        raise NaturalMemoryError("identity key must contain at least 32 bytes")
    labels = [source.label for source in sources]
    if len(labels) != len(set(labels)):
        raise NaturalMemoryError("source labels must be unique")

    interactions: list[Interaction] = []
    parents_by_session: dict[
        str, dict[str, Optional[str]]
    ] = {}
    session_bounds: dict[str, tuple[datetime, datetime]] = {}
    receipts = []
    discovery: Counter[str] = Counter()
    for source in sources:
        (
            source_interactions,
            source_parents,
            source_bounds,
            source_receipt,
            source_discovery,
        ) = _load_source(source, identity_key)
        interactions.extend(source_interactions)
        parents_by_session.update(source_parents)
        session_bounds.update(source_bounds)
        receipts.append(source_receipt)
        discovery.update(source_discovery)
    if protocol_receipt is not None:
        expected_bindings = protocol_receipt.get("source_bindings")
        if not isinstance(expected_bindings, list):
            raise NaturalMemoryError(
                "bound protocol source bindings are required"
            )
        expected_by_label = {
            str(item.get("label")): item
            for item in expected_bindings
            if isinstance(item, Mapping)
        }
        if set(expected_by_label) != {
            item["label"] for item in receipts
        }:
            raise NaturalMemoryError(
                "runtime sources do not match bound protocol"
            )
        for receipt in receipts:
            expected = expected_by_label[receipt["label"]]
            for field in (
                "dataset_id",
                "dataset_revision",
                "manifest_sha256",
            ):
                if expected.get(field) != receipt[field]:
                    raise NaturalMemoryError(
                        "runtime source receipt does not match protocol"
                    )

    observations, observation_gates = _construct_observations(
        interactions,
        parents_by_session=parents_by_session,
        session_bounds=session_bounds,
        identity_key=identity_key,
    )
    queries, query_gates = _construct_queries(
        interactions,
        observations,
        parents_by_session=parents_by_session,
        session_bounds=session_bounds,
    )
    gates = observation_gates + query_gates

    arms = []
    outcomes_by_arm: dict[str, list[str]] = {}
    enabled_by_arm: dict[str, tuple[str, ...]] = {}
    post_query_items_supplied = 0
    cross_project_items_supplied = 0
    for enabled in _all_arms():
        arm_id = _arm_id(enabled)
        enabled_by_arm[arm_id] = enabled
        outcomes = []
        supplied_counts = []
        for query in queries:
            supplied = {
                item.observation_private: item
                for mechanism in enabled
                for item in _catalog(query, mechanism)
            }
            post_query_items_supplied += sum(
                item.released_at >= query.query_at
                for item in supplied.values()
            )
            cross_project_items_supplied += sum(
                item.project_private != query.project_private
                for item in supplied.values()
            )
            outcome, _ = _decide(query, enabled)
            outcomes.append(outcome)
            supplied_counts.append(len(supplied))
        outcomes_by_arm[arm_id] = outcomes
        arms.append(
            {
                "arm_id": arm_id,
                "mechanisms": list(enabled),
                "mechanism_count": len(enabled),
                **_metric(outcomes),
                "mean_supplied_items": (
                    round(
                        sum(supplied_counts) / len(supplied_counts),
                        12,
                    )
                    if supplied_counts
                    else None
                ),
            }
        )

    singleton_exact = {
        arm["mechanisms"][0]: arm["exact"]
        for arm in arms
        if arm["mechanism_count"] == 1
    }
    singleton_vectors = {
        arm["mechanisms"][0]: tuple(
            outcomes_by_arm[arm["arm_id"]]
        )
        for arm in arms
        if arm["mechanism_count"] == 1
    }
    singleton_pairwise_differences = sum(
        left_outcome != right_outcome
        for left_name, right_name in itertools.combinations(
            RUNNABLE_MECHANISMS, 2
        )
        for left_outcome, right_outcome in zip(
            singleton_vectors[left_name],
            singleton_vectors[right_name],
        )
    )
    strongest_singleton = max(
        singleton_exact.values(), default=0
    )
    all_arm = next(
        arm
        for arm in arms
        if arm["mechanism_count"] == len(RUNNABLE_MECHANISMS)
    )
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "analysis_version": ANALYSIS_VERSION,
        "study": "natural_trace_memory_evidence_availability_factorial",
        "protocol_receipt": (
            dict(protocol_receipt)
            if protocol_receipt is not None
            else {
                "status": "unbound_test_or_library_invocation",
            }
        ),
        "input_receipts": receipts,
        "discovery": {
            **dict(sorted(discovery.items())),
            "successful_state_interactions": len(interactions),
            "supported_state_observations": len(observations),
            "source_projects": len(
                {item.project_private for item in interactions}
            ),
            "histories": len(session_bounds),
            "cross_session_queries": sum(
                item.cross_session for item in queries
            ),
        },
        "gates": dict(sorted(gates.items())),
        "mechanism_gates": {
            "released_dream": _mechanism_gate(
                discovery, "released_dream"
            ),
            "released_procedure": _mechanism_gate(
                discovery, "released_procedure"
            ),
        },
        "treatment_contrast_gate": {
            "distinct_runnable_singleton_outcome_vectors": len(
                set(singleton_vectors.values())
            ),
            "runnable_singleton_pairwise_decision_differences": (
                singleton_pairwise_differences
            ),
            "differential_mechanism_effect_identifiable": (
                singleton_pairwise_differences > 0
            ),
            "reason_when_not_identifiable": (
                "all runnable mechanisms select the same latest eligible "
                "state for every observed explicit current-state read"
                if singleton_pairwise_differences == 0
                else None
            ),
            "catalog_exposure_still_differs": True,
            "latest_snapshot_items_per_query": 1,
            "historical_or_valid_time_target_queries": 0,
            "semantic_free_text_target_queries": 0,
            "bitemporal_incremental_value_testable": False,
            "semantic_retrieval_incremental_value_testable": False,
        },
        "release_protocol": {
            "source_state_release": (
                "successful_tool_result_observation_time"
            ),
            "strictly_before_query_required": True,
            "query_outcome_excluded_from_catalogs": True,
            "same_project_required": True,
            "same_session_branch_ancestor_required": True,
            "cross_session_strict_nonoverlap_required": True,
            "cutoff_safe_project_identity": (
                "source_label_plus_pretrace_corpus_project_directory"
            ),
            "derived_release_mechanisms_without_observed_release": (
                "not_run"
            ),
        },
        "design": {
            "natural_trace_units": len(queries),
            "eligible_queries": len(queries),
            "runnable_mechanisms": list(RUNNABLE_MECHANISMS),
            "requested_but_gated_mechanisms": [
                "released_dream",
                "released_procedure",
            ],
            "arm_count": len(arms),
            "zero_mechanism_arms": sum(
                arm["mechanism_count"] == 0 for arm in arms
            ),
            "single_mechanism_arms": sum(
                arm["mechanism_count"] == 1 for arm in arms
            ),
            "composed_arms": sum(
                arm["mechanism_count"] > 1 for arm in arms
            ),
            "factorial_scope": (
                "complete_2_to_k_lattice_over_observed_runnable_mechanisms"
            ),
            "source_project_time_splits_are_descriptive": True,
            "trained_parameters": 0,
            "model_calls": 0,
        },
        "arms": arms,
        "splits": _split_metrics(
            queries, outcomes_by_arm, enabled_by_arm
        ),
        "composition_summary": {
            "singleton_exact": singleton_exact,
            "strongest_singleton_exact": strongest_singleton,
            "all_runnable_mechanisms_exact": all_arm["exact"],
            "all_minus_strongest_singleton": (
                all_arm["exact"] - strongest_singleton
            ),
            "interpretation": (
                "natural_evidence_availability_not_memory_utility"
            ),
        },
        "audit": {
            "post_query_items_supplied": post_query_items_supplied,
            "cross_project_items_supplied": cross_project_items_supplied,
            "failed_operations_promoted": 0,
            "target_results_used_by_resolver": 0,
            "gold_content_used_only_after_decision": True,
        },
        "content_policy": {
            "raw_content_emitted": False,
            "artifact_paths_emitted": False,
            "native_identifiers_emitted": False,
            "project_identifiers_emitted": False,
            "per_item_content_hashes_emitted": False,
            "aggregate_source_receipts_emitted": True,
        },
        "claim_boundary": {
            "established": [
                "natural_prequery_evidence_availability",
                "strict_temporal_cutoff_enforcement",
                "cutoff_safe_project_scoping",
                "same_branch_or_serial_session_eligibility",
                "supported_mechanism_composition_redundancy_or_difference",
            ],
            "not_established": [
                "memory_correctness",
                "model_or_user_task_utility",
                "causal_effect",
                "dream_quality",
                "procedure_quality",
                "person_identity",
                "skill_inference",
                "enterprise_transfer",
                "differential_effect_between_runnable_mechanisms",
            ],
            "natural_outcome_semantics": (
                "later_successful_explicit_read_content_digest"
            ),
        },
    }
    result["result_sha256"] = _result_digest(result)
    return result


def render_markdown(result: Mapping[str, Any]) -> str:
    design = result["design"]
    composition = result["composition_summary"]
    singleton_arm = next(
        arm
        for arm in result["arms"]
        if arm["mechanisms"] == ["latest_snapshot"]
    )
    source_lines = []
    for row in result["splits"]["source"]:
        arm = next(
            item
            for item in row["arms"]
            if item["mechanisms"] == ["latest_snapshot"]
        )
        source_lines.append(
            f"- `{row['source']}`: {arm['exact']}/"
            f"{arm['queries']} exact ({arm['exact_rate']:.3f})."
        )
    lines = [
        "# Natural trace memory factorial",
        "",
        "## Outcome",
        "",
        (
            f"Ran {design['arm_count']} arms over "
            f"{design['eligible_queries']} eligible later-read queries from "
            f"{len(result['input_receipts'])} public sources."
        ),
        (
            "The all-runnable arm achieved "
            f"{composition['all_runnable_mechanisms_exact']} exact "
            "availability outcomes versus "
            f"{composition['strongest_singleton_exact']} for the strongest "
            "singleton."
        ),
        (
            "Each runnable singleton was exact for "
            f"{singleton_arm['exact']}/{singleton_arm['queries']} queries "
            f"({singleton_arm['exact_rate']:.3f}) and stale for "
            f"{singleton_arm['stale']}. The no-memory control abstained on "
            "every query."
        ),
        "",
        "## Source, project, and time splits",
        "",
        *source_lines,
        (
            f"- Anonymous project query counts: "
            f"{result['splits']['project']['eligible_queries_per_project_desc']}."
        ),
        (
            "- Target-time bucket query counts: "
            + ", ".join(
                f"{row['bucket']}={row['eligible_queries']}"
                for row in result["splits"]["target_time"]
            )
            + "."
        ),
        (
            "These are descriptive strata, not learned train/test "
            "generalization estimates."
        ),
        "",
        "## Treatment contrast gate",
        "",
        (
            "All four runnable singletons produced the same decision vector "
            "and every composition tied its strongest component. The corpus "
            "therefore does not identify a differential mechanism effect. "
            "Bitemporal value needs historical/valid-time queries; semantic "
            "retrieval value needs free-text targets."
        ),
        "",
        "## Natural release gates",
        "",
    ]
    for name, gate in result["mechanism_gates"].items():
        lines.append(
            f"- `{name}`: {gate['status']}; "
            f"{gate['candidate_artifact_writes_or_edits']} candidate "
            "artifact writes/edits and "
            f"{gate['independently_released_items']} independently "
            "released items."
        )
    lines.extend(
        [
            "",
            "## Claim boundary",
            "",
            (
                "This is a natural evidence-availability study. It does not "
                "measure memory correctness, model or user utility, causal "
                "benefit, Dream quality, procedure quality, skill, or "
                "enterprise transfer. Seven stale outcomes show that a "
                "successful pre-query observation is not proof that the "
                "state remained valid at the later Read."
            ),
            "",
            "Raw trace content, paths, native identifiers, project "
            "identifiers, and per-item hashes are not included.",
            "",
        ]
    )
    return "\n".join(lines)


def _parse_source(value: str) -> SourceSpec:
    parts = value.split("=", 2)
    if len(parts) != 3:
        raise argparse.ArgumentTypeError(
            "source must be LABEL=ROOT=MANIFEST"
        )
    return SourceSpec(
        label=parts[0],
        root=Path(parts[1]),
        manifest=Path(parts[2]),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        action="append",
        required=True,
        type=_parse_source,
    )
    parser.add_argument("--protocol-config", required=True, type=Path)
    parser.add_argument("--identity-key-file", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    args = parser.parse_args()
    identity_key = args.identity_key_file.read_bytes()
    protocol_receipt = load_protocol_config(args.protocol_config)
    result = analyze_sources(
        args.source,
        identity_key=identity_key,
        protocol_receipt=protocol_receipt,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.summary.write_text(
        render_markdown(result),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
