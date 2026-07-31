#!/usr/bin/env python3
"""Fail-closed scope gate for cross-user enterprise trace questions.

This module is a deterministic research oracle, not a replacement for
PostgreSQL RLS.  It models the checks that must happen *before* similarity,
clustering, skill-gap inference, or collaboration recommendations are run:
current authorization epoch, tenant/team scope, classification, purpose,
explicit cross-user consent, a minimum cohort, and reviewed human outcome
labels.  A denied request exposes no candidate rows or aggregates.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Iterable, Mapping


SCHEMA_VERSION = "frankengate-enterprise-outcome-gate-v1"


@dataclass(frozen=True)
class TraceRow:
    trace_id: str
    tenant_id: str
    owner_subject_id: str
    audience: str
    team_id: str | None
    classification: int
    allowed_purposes: frozenset[str]
    authorization_epoch: int
    visibility_state: str = "active"
    cross_user_consent_scope: str | None = None
    human_outcome_label: str | None = None


@dataclass(frozen=True)
class ScopeRequest:
    tenant_id: str
    subject_id: str
    team_ids: frozenset[str]
    authorization_epoch: int
    classification_ceiling: int
    purpose: str
    analysis: str
    cross_user_consent: bool = False
    consent_scope: str | None = None
    minimum_cohort: int = 3
    require_human_outcomes: bool = False


@dataclass(frozen=True)
class GateDecision:
    decision: str
    reason: str
    candidate_count: int
    distinct_subject_count: int
    labeled_candidate_count: int
    candidate_digests: tuple[str, ...] = ()


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _authorized(row: TraceRow, request: ScopeRequest) -> bool:
    """Mirror the RLS predicate; this is deliberately called first."""

    if row.tenant_id != request.tenant_id:
        return False
    if row.visibility_state != "active":
        return False
    if row.authorization_epoch != request.authorization_epoch:
        return False
    if row.classification > request.classification_ceiling:
        return False
    if request.purpose not in row.allowed_purposes:
        return False
    if row.audience == "private":
        return row.owner_subject_id == request.subject_id
    if row.audience == "team":
        return row.team_id is not None and row.team_id in request.team_ids
    return False


def evaluate(rows: Iterable[TraceRow], request: ScopeRequest) -> GateDecision:
    """Return an abstaining decision unless the complete scope is authorized.

    The function never returns row content.  Candidate digests are included
    only on an allow decision so a caller can bind a later query to this exact
    authorization decision without making the gate a data channel.
    """

    if request.minimum_cohort < 1:
        return GateDecision("abstain", "invalid_minimum_cohort", 0, 0, 0)
    if request.analysis not in {
        "similar_work",
        "skill_gap",
        "collaboration",
        "friction_recovery",
    }:
        return GateDecision("abstain", "unknown_analysis", 0, 0, 0)

    # This is the only point at which rows enter the analysis.  All downstream
    # counts are derived from this filtered set, preventing post-ranking RLS.
    candidates = [row for row in rows if _authorized(row, request)]
    subjects = {row.owner_subject_id for row in candidates}
    labeled = [row for row in candidates if row.human_outcome_label]

    cross_user = len(subjects) > 1 or request.analysis in {
        "skill_gap",
        "collaboration",
    }
    if cross_user:
        if not request.cross_user_consent:
            return GateDecision(
                "abstain", "cross_user_consent_required", 0, 0, 0
            )
        if not request.consent_scope:
            return GateDecision("abstain", "consent_scope_required", 0, 0, 0)
        if any(
            row.cross_user_consent_scope != request.consent_scope
            for row in candidates
        ):
            return GateDecision("abstain", "row_consent_scope_mismatch", 0, 0, 0)
        if len(subjects) < request.minimum_cohort:
            return GateDecision(
                "abstain", "minimum_cohort_not_met", 0, 0, 0
            )

    if request.require_human_outcomes and len(labeled) != len(candidates):
        return GateDecision(
            "abstain", "human_outcome_labels_required", 0, 0, 0
        )

    return GateDecision(
        "allow",
        "scope_and_outcome_gate_passed",
        len(candidates),
        len(subjects),
        len(labeled),
        tuple(sorted(_digest(row.trace_id) for row in candidates)),
    )


def conformance_cases() -> Mapping[str, GateDecision]:
    """Small deterministic fixture used by the receipt runner and unit tests."""

    rows = [
        TraceRow(
            "alice-1", "tenant-a", "alice", "team", "platform", 1,
            frozenset({"quality-improvement"}), 7,
            cross_user_consent_scope="team-platform-v1",
            human_outcome_label="recovered",
        ),
        TraceRow(
            "bob-1", "tenant-a", "bob", "team", "platform", 1,
            frozenset({"quality-improvement"}), 7,
            cross_user_consent_scope="team-platform-v1",
            human_outcome_label="recovered",
        ),
        TraceRow(
            "carol-1", "tenant-a", "carol", "team", "platform", 1,
            frozenset({"quality-improvement"}), 7,
            cross_user_consent_scope="team-platform-v1",
            human_outcome_label="blocked",
        ),
        TraceRow(
            "restricted-1", "tenant-a", "dana", "team", "platform", 3,
            frozenset({"quality-improvement"}), 7,
            cross_user_consent_scope="team-platform-v1",
            human_outcome_label="recovered",
        ),
        TraceRow(
            "stale-1", "tenant-a", "erin", "team", "platform", 1,
            frozenset({"quality-improvement"}), 6,
            cross_user_consent_scope="team-platform-v1",
            human_outcome_label="recovered",
        ),
        TraceRow(
            "unlabeled-1", "tenant-a", "frank", "team", "platform", 1,
            frozenset({"quality-improvement"}), 7,
            cross_user_consent_scope="team-platform-v1",
        ),
        TraceRow(
            "other-tenant-1", "tenant-b", "zoe", "team", "platform", 1,
            frozenset({"quality-improvement"}), 7,
            cross_user_consent_scope="team-platform-v1",
            human_outcome_label="recovered",
        ),
    ]
    base = dict(
        tenant_id="tenant-a",
        subject_id="alice",
        team_ids=frozenset({"platform"}),
        authorization_epoch=7,
        classification_ceiling=2,
        purpose="quality-improvement",
        analysis="skill_gap",
        minimum_cohort=3,
    )
    cases = {
        "missing_consent": ScopeRequest(**base),
        "wrong_consent_scope": ScopeRequest(
            **base, cross_user_consent=True, consent_scope="wrong"
        ),
        "cohort_without_labels": ScopeRequest(
            **base,
            cross_user_consent=True,
            consent_scope="team-platform-v1",
            require_human_outcomes=True,
        ),
        "authorized_labeled_cohort": ScopeRequest(
            **base,
            cross_user_consent=True,
            consent_scope="team-platform-v1",
            require_human_outcomes=True,
        ),
    }
    return {
        "missing_consent": evaluate(rows, cases["missing_consent"]),
        "wrong_consent_scope": evaluate(rows, cases["wrong_consent_scope"]),
        "cohort_without_labels": evaluate(
            rows,
            cases["cohort_without_labels"],
        ),
        "authorized_labeled_cohort": evaluate(
            rows[:3], cases["authorized_labeled_cohort"]
        ),
    }
