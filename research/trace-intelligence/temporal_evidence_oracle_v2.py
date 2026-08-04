#!/usr/bin/env python3
"""Cutoff-safe bitemporal state oracle for corrected memory experiments.

The oracle reconstructs only what an online observer could have known at the
query's ``known_at`` cutoff.  ``valid_at`` is evaluated independently, so a
late-recorded observation can answer a historical question without being
available to an earlier online query.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Optional, Sequence, Tuple


class TemporalOracleError(ValueError):
    """Raised when evidence cannot satisfy the frozen oracle contract."""


def instant(value: str) -> datetime:
    """Parse one timezone-aware ISO-8601 instant and normalize it to UTC."""

    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise TemporalOracleError("timestamps must be timezone-aware")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class TemporalEvidenceEvent:
    event_id: str
    event_type: str
    succeeded: bool
    authority_subject: str
    project_context: str
    artifact_context: str
    content_sha256: str
    valid_at: datetime
    known_at: datetime
    parent_event_ids: Tuple[str, ...] = ()


@dataclass(frozen=True)
class TemporalQuery:
    authority_subject: str
    project_context: str
    artifact_context: str
    valid_at: datetime
    known_at: datetime
    parent_event_ids: Tuple[str, ...]


@dataclass(frozen=True)
class TemporalRevision:
    revision_id: str
    content_sha256: str
    valid_from: datetime
    valid_from_lower_bound: Optional[datetime]
    valid_from_precision: str
    valid_to: Optional[datetime]
    valid_to_lower_bound: Optional[datetime]
    valid_to_precision: str
    confirmed_through: datetime
    known_at: datetime
    source_event_ids: Tuple[str, ...]


@dataclass(frozen=True)
class IntervalCensoredGap:
    lower_exclusive: datetime
    upper_inclusive: datetime
    discovered_at: datetime
    from_content_sha256: str
    to_content_sha256: str
    source_event_id: str


@dataclass(frozen=True)
class EqualPrecedenceConflict:
    valid_at: datetime
    lineage_depth: int
    content_sha256s: Tuple[str, ...]
    source_event_ids: Tuple[str, ...]


@dataclass(frozen=True)
class OracleResolution:
    status: str
    reason: str
    selected_revision: Optional[TemporalRevision]
    revisions: Tuple[TemporalRevision, ...] = ()
    interval_gaps: Tuple[IntervalCensoredGap, ...] = ()
    conflicts: Tuple[EqualPrecedenceConflict, ...] = ()


class TemporalEvidenceOracle:
    """Resolve temporal state using exact scope and cutoff-safe evidence."""

    def __init__(self, events: Sequence[TemporalEvidenceEvent]) -> None:
        self._events = tuple(events)
        self._by_id = {item.event_id: item for item in self._events}
        if len(self._by_id) != len(self._events):
            raise TemporalOracleError("event ids must be unique")
        for item in self._events:
            missing = set(item.parent_event_ids).difference(self._by_id)
            if missing:
                raise TemporalOracleError(
                    "event references unknown parent: " + sorted(missing)[0]
                )

    def _ancestor_ids(self, frontier: Sequence[str]) -> set:
        pending = list(frontier)
        ancestors = set()
        while pending:
            event_id = pending.pop()
            if event_id in ancestors:
                continue
            item = self._by_id.get(event_id)
            if item is None:
                raise TemporalOracleError(
                    "query references unknown parent: " + event_id
                )
            ancestors.add(event_id)
            pending.extend(item.parent_event_ids)
        return ancestors

    def _depth(self, event_id: str, active: Optional[set] = None) -> int:
        active = set() if active is None else active
        if event_id in active:
            raise TemporalOracleError("event lineage contains a cycle")
        item = self._by_id[event_id]
        if not item.parent_event_ids:
            return 0
        active.add(event_id)
        result = 1 + max(
            self._depth(parent, active) for parent in item.parent_event_ids
        )
        active.remove(event_id)
        return result

    def _eligible_events(
        self, query: TemporalQuery
    ) -> Tuple[TemporalEvidenceEvent, ...]:
        ancestors = self._ancestor_ids(query.parent_event_ids)
        return tuple(
            sorted(
                (
                    item
                    for item in self._events
                    if item.event_id in ancestors
                    and item.known_at <= query.known_at
                    and item.succeeded
                    and item.authority_subject == query.authority_subject
                    and item.project_context == query.project_context
                    and item.artifact_context == query.artifact_context
                ),
                key=lambda item: (
                    item.valid_at,
                    self._depth(item.event_id),
                    item.event_id,
                ),
            )
        )

    def _active_conflicts(
        self,
        events: Sequence[TemporalEvidenceEvent],
        valid_at: datetime,
    ) -> Tuple[EqualPrecedenceConflict, ...]:
        groups = {}
        for item in events:
            if item.valid_at > valid_at:
                continue
            key = (item.valid_at, self._depth(item.event_id))
            groups.setdefault(key, []).append(item)

        conflicts = []
        for (boundary, depth), items in groups.items():
            contents = {item.content_sha256 for item in items}
            if len(contents) <= 1:
                continue
            source_ids = {item.event_id for item in items}
            resolved = False
            for candidate in events:
                candidate_order = (
                    candidate.valid_at,
                    self._depth(candidate.event_id),
                )
                if (
                    candidate.valid_at > valid_at
                    or candidate_order <= (boundary, depth)
                ):
                    continue
                if source_ids.issubset(
                    self._ancestor_ids((candidate.event_id,))
                ):
                    resolved = True
                    break
            if not resolved:
                conflicts.append(
                    EqualPrecedenceConflict(
                        valid_at=boundary,
                        lineage_depth=depth,
                        content_sha256s=tuple(sorted(contents)),
                        source_event_ids=tuple(sorted(source_ids)),
                    )
                )
        return tuple(
            sorted(
                conflicts,
                key=lambda item: (
                    item.valid_at,
                    item.lineage_depth,
                    item.source_event_ids,
                ),
            )
        )

    def _timeline(
        self, events: Sequence[TemporalEvidenceEvent]
    ) -> Tuple[
        Tuple[TemporalRevision, ...], Tuple[IntervalCensoredGap, ...]
    ]:
        revisions = []
        gaps = []
        for item in events:
            if item.event_type not in {"write", "read"}:
                raise TemporalOracleError(
                    "event type must be write or read"
                )
            if item.event_type == "read" and revisions:
                current = revisions[-1]
                if current.content_sha256 == item.content_sha256:
                    revisions[-1] = replace(
                        current,
                        confirmed_through=max(
                            current.confirmed_through, item.valid_at
                        ),
                        source_event_ids=current.source_event_ids
                        + (item.event_id,),
                    )
                    continue
                if item.valid_at <= current.confirmed_through:
                    raise TemporalOracleError(
                        "changed read must follow the prior confirmation"
                    )
                revisions[-1] = replace(
                    current,
                    valid_to=item.valid_at,
                    valid_to_lower_bound=current.confirmed_through,
                    valid_to_precision="interval_censored",
                )
                gaps.append(
                    IntervalCensoredGap(
                        lower_exclusive=current.confirmed_through,
                        upper_inclusive=item.valid_at,
                        discovered_at=item.known_at,
                        from_content_sha256=current.content_sha256,
                        to_content_sha256=item.content_sha256,
                        source_event_id=item.event_id,
                    )
                )
                revisions.append(
                    TemporalRevision(
                        revision_id="revision:" + item.event_id,
                        content_sha256=item.content_sha256,
                        valid_from=item.valid_at,
                        valid_from_lower_bound=current.confirmed_through,
                        valid_from_precision="interval_censored",
                        valid_to=None,
                        valid_to_lower_bound=None,
                        valid_to_precision="open",
                        confirmed_through=item.valid_at,
                        known_at=item.known_at,
                        source_event_ids=(item.event_id,),
                    )
                )
                continue
            if item.event_type == "read":
                revisions.append(
                    TemporalRevision(
                        revision_id="revision:" + item.event_id,
                        content_sha256=item.content_sha256,
                        valid_from=item.valid_at,
                        valid_from_lower_bound=item.valid_at,
                        valid_from_precision="exact",
                        valid_to=None,
                        valid_to_lower_bound=None,
                        valid_to_precision="open",
                        confirmed_through=item.valid_at,
                        known_at=item.known_at,
                        source_event_ids=(item.event_id,),
                    )
                )
                continue
            if revisions:
                revisions[-1] = replace(
                    revisions[-1],
                    valid_to=item.valid_at,
                    valid_to_lower_bound=item.valid_at,
                    valid_to_precision="exact",
                )
            revisions.append(
                TemporalRevision(
                    revision_id="revision:" + item.event_id,
                    content_sha256=item.content_sha256,
                    valid_from=item.valid_at,
                    valid_from_lower_bound=item.valid_at,
                    valid_from_precision="exact",
                    valid_to=None,
                    valid_to_lower_bound=None,
                    valid_to_precision="open",
                    confirmed_through=item.valid_at,
                    known_at=item.known_at,
                    source_event_ids=(item.event_id,),
                )
            )
        return tuple(revisions), tuple(gaps)

    def resolve(self, query: TemporalQuery) -> OracleResolution:
        eligible = self._eligible_events(query)
        conflicts = self._active_conflicts(eligible, query.valid_at)
        if conflicts:
            first_boundary = min(item.valid_at for item in conflicts)
            revisions, gaps = self._timeline(
                tuple(
                    item
                    for item in eligible
                    if item.valid_at < first_boundary
                )
            )
            return OracleResolution(
                status="conflict",
                reason="incompatible_overlap",
                selected_revision=None,
                revisions=revisions,
                interval_gaps=gaps,
                conflicts=conflicts,
            )
        revisions, gaps = self._timeline(eligible)
        if any(
            gap.lower_exclusive < query.valid_at < gap.upper_inclusive
            for gap in gaps
        ):
            return OracleResolution(
                status="insufficient",
                reason="interval_censored_gap",
                selected_revision=None,
                revisions=revisions,
                interval_gaps=gaps,
                conflicts=conflicts,
            )
        candidates = [
            item
            for item in revisions
            if item.valid_from <= query.valid_at
            and (item.valid_to is None or query.valid_at < item.valid_to)
        ]
        if not candidates:
            return OracleResolution(
                status="insufficient",
                reason="no_eligible_evidence",
                selected_revision=None,
                revisions=revisions,
                interval_gaps=gaps,
                conflicts=conflicts,
            )
        revision = candidates[-1]
        resolved = (
            query.valid_at <= revision.confirmed_through
            or revision.valid_to_precision == "exact"
        )
        return OracleResolution(
            status="resolved" if resolved else "last_observed_only",
            reason=(
                "unique_supported_state"
                if resolved
                else "last_observation_with_open_gap"
            ),
            selected_revision=revision,
            revisions=revisions,
            interval_gaps=gaps,
            conflicts=conflicts,
        )
