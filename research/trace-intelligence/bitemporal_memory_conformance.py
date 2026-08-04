#!/usr/bin/env python3
"""Deterministic conformance arm for governed bitemporal memory releases.

This is a relational state-machine oracle, not a memory extractor and not a
database/RLS benchmark.  It isolates the mechanics that can be tested without a
model: evidence-scope intersection, contextual contradiction, valid/system-time
queries, copy-on-write release, failed-job isolation, rollback, deletion
closure, and influence-lineage exclusion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


SCHEMA_VERSION = "bitemporal-memory-conformance-result-v1"
ENGINE_VERSION = "governed-bitemporal-release-oracle-v1"
SOURCE_PINS = {
    "anthropic_dreams": {
        "source": "https://platform.claude.com/docs/en/managed-agents/dreams",
        "revision": "dreaming-2026-04-21",
        "mechanism": "asynchronous copy-on-write memory-store output",
    },
    "graphiti": {
        "source": "https://github.com/getzep/graphiti",
        "revision": "v0.29.3@021d3a57d511f21b10adaf7fa923bd5c1fce5e9d",
        "mechanism": "episode provenance and temporal fact invalidation",
    },
    "langmem": {
        "source": "https://github.com/langchain-ai/langmem",
        "revision": "56d85939d80bb731bd5e237567148d817d7bfd16",
        "mechanism": "typed create/update/delete memory candidates",
    },
    "mempalace": {
        "source": "https://github.com/MemPalace/mempalace",
        "revision": "v3.6.0@8ab251c452c43f2b07a76a28f2433e258307f571",
        "mechanism": "verbatim evidence and valid-time provenance",
    },
}


class ConformanceError(ValueError):
    """Raised when a governed memory invariant is violated."""


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ConformanceError("timestamps must be timezone-aware")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class Envelope:
    tenant_id: str
    owner_subject_id: str
    audience: str
    team_id: Optional[str]
    classification: int
    purposes: Tuple[str, ...]
    authorization_epoch: int
    policy_revision: str

    def __post_init__(self) -> None:
        if self.audience not in {"private", "team"}:
            raise ConformanceError("audience must be private or team")
        if (self.audience == "private") != (self.team_id is None):
            raise ConformanceError("private scope cannot have a team; team scope requires one")
        if not self.purposes:
            raise ConformanceError("authority envelope needs at least one purpose")
        if self.authorization_epoch <= 0:
            raise ConformanceError("authorization epoch must be positive")


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    fact_key: str
    context: Tuple[Tuple[str, str], ...]
    value: str
    valid_from: datetime
    observed_at: datetime
    envelope: Envelope
    deleted_at: Optional[datetime] = None


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    fact_key: str
    context: Tuple[Tuple[str, str], ...]
    value: str
    valid_from: datetime
    evidence_ids: Tuple[str, ...]
    parent_candidate_ids: Tuple[str, ...]
    envelope: Envelope
    lifecycle: str
    derivation_revision: str


@dataclass(frozen=True)
class ReleaseEntry:
    candidate_id: str
    fact_key: str
    context: Tuple[Tuple[str, str], ...]
    value: str
    valid_from: datetime
    valid_to: Optional[datetime]
    evidence_ids: Tuple[str, ...]
    envelope: Envelope


@dataclass(frozen=True)
class Release:
    release_id: str
    parent_release_id: Optional[str]
    created_at: datetime
    kind: str
    entries: Tuple[ReleaseEntry, ...]
    invalidated_at: Optional[datetime] = None


@dataclass(frozen=True)
class QueryAuthority:
    tenant_id: str
    subject_id: str
    teams: Tuple[str, ...]
    classification_ceiling: int
    purpose: str
    authorization_epoch: int


def intersect_envelopes(envelopes: Sequence[Envelope]) -> Envelope:
    if not envelopes:
        raise ConformanceError("candidate needs evidence")
    tenants = {item.tenant_id for item in envelopes}
    owners = {item.owner_subject_id for item in envelopes}
    if len(tenants) != 1 or len(owners) != 1:
        raise ConformanceError("cross-tenant or cross-owner facts require a different product")
    purposes = set(envelopes[0].purposes)
    for item in envelopes[1:]:
        purposes.intersection_update(item.purposes)
    if not purposes:
        raise ConformanceError("evidence has no common authorized purpose")

    private = [item for item in envelopes if item.audience == "private"]
    if private:
        audience = "private"
        team_id = None
    else:
        teams = {item.team_id for item in envelopes}
        if len(teams) != 1:
            raise ConformanceError("team evidence has no common visibility scope")
        audience = "team"
        team_id = next(iter(teams))
    return Envelope(
        tenant_id=envelopes[0].tenant_id,
        owner_subject_id=envelopes[0].owner_subject_id,
        audience=audience,
        team_id=team_id,
        classification=max(item.classification for item in envelopes),
        purposes=tuple(sorted(purposes)),
        authorization_epoch=max(item.authorization_epoch for item in envelopes),
        policy_revision=digest(sorted(item.policy_revision for item in envelopes))[:16],
    )


class MemoryLedger:
    def __init__(self) -> None:
        self.evidence: Dict[str, Evidence] = {}
        self.candidates: Dict[str, Candidate] = {}
        self.releases: Dict[str, Release] = {}
        self.exports: Dict[str, str] = {}
        self.current_epochs: Dict[Tuple[str, str], int] = {}

    def add_evidence(self, evidence: Evidence) -> None:
        if evidence.evidence_id in self.evidence:
            raise ConformanceError("duplicate evidence id")
        self.evidence[evidence.evidence_id] = evidence
        self.current_epochs[
            (evidence.envelope.tenant_id, evidence.envelope.owner_subject_id)
        ] = max(
            evidence.envelope.authorization_epoch,
            self.current_epochs.get(
                (
                    evidence.envelope.tenant_id,
                    evidence.envelope.owner_subject_id,
                ),
                0,
            ),
        )

    def propose(
        self,
        *,
        fact_key: str,
        context: Mapping[str, str],
        value: str,
        valid_from: datetime,
        evidence_ids: Sequence[str],
        parent_candidate_ids: Sequence[str] = (),
        derivation_revision: str = "synthetic-extractor-v1",
    ) -> Candidate:
        if not evidence_ids:
            raise ConformanceError("candidate requires evidence ids")
        evidence_rows = []
        for evidence_id in evidence_ids:
            row = self.evidence.get(evidence_id)
            if row is None or row.deleted_at is not None:
                raise ConformanceError("candidate evidence is missing or deleted")
            evidence_rows.append(row)
        for parent_id in parent_candidate_ids:
            if parent_id not in self.candidates:
                raise ConformanceError("parent candidate is missing")
        normalized_context = tuple(sorted((str(key), str(item)) for key, item in context.items()))
        payload = {
            "fact_key": fact_key,
            "context": normalized_context,
            "value": value,
            "valid_from": valid_from.isoformat(),
            "evidence_ids": sorted(evidence_ids),
            "parent_candidate_ids": sorted(parent_candidate_ids),
            "derivation_revision": derivation_revision,
        }
        candidate = Candidate(
            candidate_id="cand-" + digest(payload)[:24],
            fact_key=fact_key,
            context=normalized_context,
            value=value,
            valid_from=valid_from,
            evidence_ids=tuple(sorted(evidence_ids)),
            parent_candidate_ids=tuple(sorted(parent_candidate_ids)),
            envelope=intersect_envelopes([row.envelope for row in evidence_rows]),
            lifecycle="proposal",
            derivation_revision=derivation_revision,
        )
        self.candidates[candidate.candidate_id] = candidate
        return candidate

    def review(self, candidate_id: str) -> Candidate:
        candidate = self.candidates[candidate_id]
        reviewed = replace(candidate, lifecycle="reviewed")
        self.candidates[candidate_id] = reviewed
        return reviewed

    def _latest_release(self, at: Optional[datetime] = None) -> Optional[Release]:
        eligible = [
            release
            for release in self.releases.values()
            if at is None or release.created_at <= at
        ]
        return max(eligible, key=lambda item: (item.created_at, item.release_id)) if eligible else None

    def _make_release(
        self,
        *,
        parent_release_id: Optional[str],
        created_at: datetime,
        kind: str,
        entries: Iterable[ReleaseEntry],
    ) -> Release:
        ordered = tuple(
            sorted(
                entries,
                key=lambda item: (
                    item.fact_key,
                    item.context,
                    item.valid_from,
                    item.candidate_id,
                ),
            )
        )
        payload = {
            "parent_release_id": parent_release_id,
            "created_at": created_at.isoformat(),
            "kind": kind,
            "entries": [
                {
                    "candidate_id": item.candidate_id,
                    "fact_key": item.fact_key,
                    "context": item.context,
                    "value": item.value,
                    "valid_from": item.valid_from.isoformat(),
                    "valid_to": item.valid_to.isoformat() if item.valid_to else None,
                    "evidence_ids": item.evidence_ids,
                }
                for item in ordered
            ],
        }
        release = Release(
            release_id="rel-" + digest(payload)[:24],
            parent_release_id=parent_release_id,
            created_at=created_at,
            kind=kind,
            entries=ordered,
        )
        self.releases[release.release_id] = release
        return release

    def promote(
        self,
        candidate_id: str,
        *,
        dream_job_status: str,
        created_at: datetime,
    ) -> Release:
        if dream_job_status != "completed":
            raise ConformanceError("partial, failed, or canceled dream cannot promote")
        candidate = self.candidates[candidate_id]
        if candidate.lifecycle != "reviewed":
            raise ConformanceError("only reviewed candidates can promote")
        for evidence_id in candidate.evidence_ids:
            if self.evidence[evidence_id].deleted_at is not None:
                raise ConformanceError("deleted evidence cannot promote")

        parent = self._latest_release()
        entries = list(parent.entries) if parent else []
        identity = (candidate.fact_key, candidate.context)
        same_identity = [
            item for item in entries if (item.fact_key, item.context) == identity
        ]
        if any(
            item.value == candidate.value
            and item.valid_from == candidate.valid_from
            and item.valid_to is None
            for item in same_identity
        ):
            raise ConformanceError("exact duplicate candidate must be deduplicated")

        updated = []
        for item in entries:
            if (
                (item.fact_key, item.context) == identity
                and item.value != candidate.value
                and item.valid_from < candidate.valid_from
                and (item.valid_to is None or candidate.valid_from < item.valid_to)
            ):
                updated.append(replace(item, valid_to=candidate.valid_from))
            else:
                updated.append(item)
        updated.append(
            ReleaseEntry(
                candidate_id=candidate.candidate_id,
                fact_key=candidate.fact_key,
                context=candidate.context,
                value=candidate.value,
                valid_from=candidate.valid_from,
                valid_to=None,
                evidence_ids=candidate.evidence_ids,
                envelope=candidate.envelope,
            )
        )
        release = self._make_release(
            parent_release_id=parent.release_id if parent else None,
            created_at=created_at,
            kind="promotion",
            entries=updated,
        )
        self.candidates[candidate_id] = replace(candidate, lifecycle="released")
        return release

    def _authorized(self, envelope: Envelope, authority: QueryAuthority) -> bool:
        current_epoch = self.current_epochs.get(
            (authority.tenant_id, authority.subject_id)
        )
        if current_epoch != authority.authorization_epoch:
            return False
        if envelope.tenant_id != authority.tenant_id:
            return False
        if envelope.classification > authority.classification_ceiling:
            return False
        if authority.purpose not in envelope.purposes:
            return False
        if envelope.audience == "private":
            return envelope.owner_subject_id == authority.subject_id
        return envelope.team_id in authority.teams

    def query(
        self,
        *,
        fact_key: str,
        context: Mapping[str, str],
        valid_at: datetime,
        system_at: datetime,
        authority: QueryAuthority,
    ) -> List[ReleaseEntry]:
        release = self._latest_release(system_at)
        if release is None:
            return []
        normalized_context = tuple(sorted((str(key), str(value)) for key, value in context.items()))
        result = []
        for entry in release.entries:
            if entry.fact_key != fact_key or entry.context != normalized_context:
                continue
            if not (entry.valid_from <= valid_at and (entry.valid_to is None or valid_at < entry.valid_to)):
                continue
            if any(self.evidence[evidence_id].deleted_at is not None for evidence_id in entry.evidence_ids):
                continue
            if self._authorized(entry.envelope, authority):
                result.append(entry)
        return result

    def export_release(self, release_id: str) -> None:
        self.exports[release_id] = "active"

    def rollback(self, release_id: str, *, created_at: datetime) -> Release:
        target = self.releases[release_id]
        if target.parent_release_id is None:
            entries: Tuple[ReleaseEntry, ...] = ()
        else:
            entries = self.releases[target.parent_release_id].entries
        live_entries = [
            entry
            for entry in entries
            if not any(
                self.evidence[evidence_id].deleted_at is not None
                for evidence_id in entry.evidence_ids
            )
        ]
        parent = self._latest_release()
        return self._make_release(
            parent_release_id=parent.release_id if parent else None,
            created_at=created_at,
            kind="rollback",
            entries=live_entries,
        )

    def _invalid_candidate_closure(self, evidence_id: str) -> set:
        invalid = {
            candidate.candidate_id
            for candidate in self.candidates.values()
            if evidence_id in candidate.evidence_ids
        }
        changed = True
        while changed:
            changed = False
            for candidate in self.candidates.values():
                if (
                    candidate.candidate_id not in invalid
                    and set(candidate.parent_candidate_ids).intersection(invalid)
                ):
                    invalid.add(candidate.candidate_id)
                    changed = True
        return invalid

    def delete_evidence(self, evidence_id: str, *, deleted_at: datetime) -> Dict[str, Any]:
        evidence = self.evidence[evidence_id]
        self.evidence[evidence_id] = replace(evidence, deleted_at=deleted_at)
        invalid_candidates = self._invalid_candidate_closure(evidence_id)
        invalid_releases = []
        for release_id, release in list(self.releases.items()):
            if any(entry.candidate_id in invalid_candidates for entry in release.entries):
                self.releases[release_id] = replace(release, invalidated_at=deleted_at)
                invalid_releases.append(release_id)
                if release_id in self.exports:
                    self.exports[release_id] = "invalidated"
        parent = self._latest_release()
        live_entries = [
            entry
            for entry in (parent.entries if parent else ())
            if entry.candidate_id not in invalid_candidates
        ]
        withdrawal = self._make_release(
            parent_release_id=parent.release_id if parent else None,
            created_at=deleted_at,
            kind="deletion_withdrawal",
            entries=live_entries,
        )
        return {
            "invalid_candidate_ids": sorted(invalid_candidates),
            "invalid_release_ids": sorted(invalid_releases),
            "invalidated_export_count": sum(
                self.exports.get(release_id) == "invalidated"
                for release_id in invalid_releases
            ),
            "withdrawal_release_id": withdrawal.release_id,
        }

    @staticmethod
    def independent_validation_eligible(
        candidate_id: str, influence_candidate_ids: Sequence[str]
    ) -> bool:
        return candidate_id not in set(influence_candidate_ids)


def _private_envelope(
    *,
    tenant: str = "tenant-a",
    owner: str = "subject-a",
    classification: int = 2,
    purposes: Sequence[str] = ("support", "debug"),
    epoch: int = 7,
) -> Envelope:
    return Envelope(
        tenant_id=tenant,
        owner_subject_id=owner,
        audience="private",
        team_id=None,
        classification=classification,
        purposes=tuple(purposes),
        authorization_epoch=epoch,
        policy_revision="policy-v3",
    )


def run_conformance() -> Dict[str, Any]:
    ledger = MemoryLedger()
    envelope = _private_envelope()
    authority = QueryAuthority(
        tenant_id="tenant-a",
        subject_id="subject-a",
        teams=(),
        classification_ceiling=4,
        purpose="support",
        authorization_epoch=7,
    )
    assertions: Dict[str, bool] = {}

    old = Evidence(
        evidence_id="evidence-prod-old",
        fact_key="service.endpoint",
        context=(("environment", "prod"),),
        value="old",
        valid_from=instant("2026-01-01T00:00:00Z"),
        observed_at=instant("2026-01-02T00:00:00Z"),
        envelope=envelope,
    )
    gov = Evidence(
        evidence_id="evidence-gov",
        fact_key="service.endpoint",
        context=(("environment", "gov"),),
        value="gov",
        valid_from=instant("2026-01-01T00:00:00Z"),
        observed_at=instant("2026-01-03T00:00:00Z"),
        envelope=envelope,
    )
    new = Evidence(
        evidence_id="evidence-prod-new",
        fact_key="service.endpoint",
        context=(("environment", "prod"),),
        value="new",
        valid_from=instant("2026-06-01T00:00:00Z"),
        observed_at=instant("2026-07-01T00:00:00Z"),
        envelope=envelope,
    )
    for evidence in (old, gov, new):
        ledger.add_evidence(evidence)

    old_candidate = ledger.review(
        ledger.propose(
            fact_key=old.fact_key,
            context=dict(old.context),
            value=old.value,
            valid_from=old.valid_from,
            evidence_ids=(old.evidence_id,),
        ).candidate_id
    )
    release_old = ledger.promote(
        old_candidate.candidate_id,
        dream_job_status="completed",
        created_at=instant("2026-02-01T00:00:00Z"),
    )
    gov_candidate = ledger.review(
        ledger.propose(
            fact_key=gov.fact_key,
            context=dict(gov.context),
            value=gov.value,
            valid_from=gov.valid_from,
            evidence_ids=(gov.evidence_id,),
        ).candidate_id
    )
    ledger.promote(
        gov_candidate.candidate_id,
        dream_job_status="completed",
        created_at=instant("2026-02-02T00:00:00Z"),
    )
    new_candidate = ledger.review(
        ledger.propose(
            fact_key=new.fact_key,
            context=dict(new.context),
            value=new.value,
            valid_from=new.valid_from,
            evidence_ids=(new.evidence_id,),
            parent_candidate_ids=(old_candidate.candidate_id,),
        ).candidate_id
    )
    release_new = ledger.promote(
        new_candidate.candidate_id,
        dream_job_status="completed",
        created_at=instant("2026-08-01T00:00:00Z"),
    )
    ledger.export_release(release_new.release_id)

    def query_value(valid_at: str, system_at: str, context: str) -> Optional[str]:
        rows = ledger.query(
            fact_key="service.endpoint",
            context={"environment": context},
            valid_at=instant(valid_at),
            system_at=instant(system_at),
            authority=authority,
        )
        if len(rows) > 1:
            raise AssertionError("conformance query returned overlapping active facts")
        return rows[0].value if rows else None

    assertions["old_known_before_correction"] = (
        query_value("2026-07-01T00:00:00Z", "2026-03-01T00:00:00Z", "prod")
        == "old"
    )
    assertions["historical_valid_time_retained"] = (
        query_value("2026-05-01T00:00:00Z", "2026-09-01T00:00:00Z", "prod")
        == "old"
    )
    assertions["new_value_active_after_correction"] = (
        query_value("2026-07-01T00:00:00Z", "2026-09-01T00:00:00Z", "prod")
        == "new"
    )
    assertions["different_context_not_invalidated"] = (
        query_value("2026-07-01T00:00:00Z", "2026-09-01T00:00:00Z", "gov")
        == "gov"
    )
    assertions["prior_release_immutable"] = any(
        entry.value == "old" and entry.valid_to is None
        for entry in release_old.entries
    )

    failed_blocked = False
    try:
        ledger.promote(
            old_candidate.candidate_id,
            dream_job_status="failed",
            created_at=instant("2026-09-02T00:00:00Z"),
        )
    except ConformanceError:
        failed_blocked = True
    assertions["failed_dream_cannot_promote"] = failed_blocked

    restricted = Evidence(
        evidence_id="evidence-restricted",
        fact_key="procedure",
        context=(("environment", "prod"),),
        value="bounded",
        valid_from=instant("2026-01-01T00:00:00Z"),
        observed_at=instant("2026-01-04T00:00:00Z"),
        envelope=_private_envelope(
            classification=4, purposes=("support",), epoch=7
        ),
    )
    ledger.add_evidence(restricted)
    scoped = ledger.propose(
        fact_key="procedure",
        context={"environment": "prod"},
        value="bounded",
        valid_from=restricted.valid_from,
        evidence_ids=(old.evidence_id, restricted.evidence_id),
    )
    assertions["scope_intersection_uses_max_classification"] = (
        scoped.envelope.classification == 4
    )
    assertions["scope_intersection_uses_common_purpose"] = (
        scoped.envelope.purposes == ("support",)
    )

    no_common_purpose = Evidence(
        evidence_id="evidence-no-common-purpose",
        fact_key="procedure",
        context=(("environment", "prod"),),
        value="blocked",
        valid_from=instant("2026-01-01T00:00:00Z"),
        observed_at=instant("2026-01-05T00:00:00Z"),
        envelope=_private_envelope(purposes=("audit",), epoch=7),
    )
    ledger.add_evidence(no_common_purpose)
    purpose_blocked = False
    try:
        ledger.propose(
            fact_key="procedure",
            context={"environment": "prod"},
            value="blocked",
            valid_from=no_common_purpose.valid_from,
            evidence_ids=(old.evidence_id, no_common_purpose.evidence_id),
        )
    except ConformanceError:
        purpose_blocked = True
    assertions["empty_purpose_intersection_rejected"] = purpose_blocked

    cross_tenant = Evidence(
        evidence_id="evidence-cross-tenant",
        fact_key="procedure",
        context=(("environment", "prod"),),
        value="blocked",
        valid_from=instant("2026-01-01T00:00:00Z"),
        observed_at=instant("2026-01-06T00:00:00Z"),
        envelope=_private_envelope(tenant="tenant-b"),
    )
    ledger.add_evidence(cross_tenant)
    cross_tenant_blocked = False
    try:
        ledger.propose(
            fact_key="procedure",
            context={"environment": "prod"},
            value="blocked",
            valid_from=cross_tenant.valid_from,
            evidence_ids=(old.evidence_id, cross_tenant.evidence_id),
        )
    except ConformanceError:
        cross_tenant_blocked = True
    assertions["cross_tenant_candidate_rejected"] = cross_tenant_blocked

    rollback = ledger.rollback(
        release_new.release_id, created_at=instant("2026-09-10T00:00:00Z")
    )
    assertions["rollback_is_new_copy_on_write_release"] = (
        rollback.release_id != release_new.release_id
        and rollback.kind == "rollback"
        and release_new.entries != ()
    )
    assertions["rollback_restores_parent_view"] = (
        query_value("2026-07-01T00:00:00Z", "2026-09-11T00:00:00Z", "prod")
        == "old"
    )

    deletion = ledger.delete_evidence(
        new.evidence_id, deleted_at=instant("2026-09-15T00:00:00Z")
    )
    assertions["deletion_invalidates_candidate_release_and_export"] = (
        new_candidate.candidate_id in deletion["invalid_candidate_ids"]
        and release_new.release_id in deletion["invalid_release_ids"]
        and deletion["invalidated_export_count"] == 1
    )
    assertions["influenced_trace_not_independent_validation"] = not ledger.independent_validation_eligible(
        new_candidate.candidate_id, (new_candidate.candidate_id,)
    )

    denied_authority = replace(authority, authorization_epoch=6)
    denied_rows = ledger.query(
        fact_key="service.endpoint",
        context={"environment": "prod"},
        valid_at=instant("2026-05-01T00:00:00Z"),
        system_at=instant("2026-09-20T00:00:00Z"),
        authority=denied_authority,
    )
    assertions["stale_authorization_epoch_returns_zero"] = denied_rows == []

    if not all(assertions.values()):
        failed = sorted(name for name, passed in assertions.items() if not passed)
        raise AssertionError("conformance assertions failed: " + ", ".join(failed))

    release_kinds = dict(
        sorted(Counter(release.kind for release in ledger.releases.values()).items())
    )
    result: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "engine_version": ENGINE_VERSION,
        "source_pins": SOURCE_PINS,
        "study_scope": {
            "input": "deterministic synthetic fact/evidence fixtures",
            "architecture_model": "relational copy-on-write ledger",
            "database_or_rls_executed": False,
            "model_extractor_executed": False,
            "natural_trace_memory_quality_measured": False,
        },
        "assertions": {
            "total": len(assertions),
            "passed": sum(assertions.values()),
            "failed": 0,
            "names": sorted(assertions),
        },
        "ledger_aggregate": {
            "evidence_rows": len(ledger.evidence),
            "candidate_rows": len(ledger.candidates),
            "release_rows": len(ledger.releases),
            "release_kinds": release_kinds,
            "invalidated_releases": sum(
                release.invalidated_at is not None
                for release in ledger.releases.values()
            ),
            "invalidated_exports": sum(
                status == "invalidated" for status in ledger.exports.values()
            ),
            "deletion_invalid_candidate_count": len(
                deletion["invalid_candidate_ids"]
            ),
        },
        "proven_invariants": [
            "copy-on-write release preserves prior system-time view",
            "valid-time correction closes only the matching contextual fact",
            "partial or failed dream jobs cannot promote",
            "derived authority is the intersection of evidence authority",
            "empty-purpose and cross-tenant compositions fail closed",
            "rollback creates a new release instead of mutating history",
            "source deletion reaches dependent candidate, release, and export",
            "memory-influenced traces are excluded from independent validation",
            "stale authorization epoch yields zero results",
        ],
        "not_proven": [
            "PostgreSQL transaction, RLS, concurrency, or performance behavior",
            "LLM extraction accuracy, entailment, consolidation quality, or stability",
            "Graphiti, LangMem, MemPalace, or Anthropic Dreams implementation equivalence",
            "memory benefit on held-out tasks or natural enterprise traces",
            "single-user, team, or enterprise release product validity",
        ],
    }
    result["result_sha256"] = digest(result)
    return result


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    result = run_conformance()
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, sort_keys=True, ensure_ascii=False)
        handle.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
