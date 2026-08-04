#!/usr/bin/env python3
"""Deterministic protocol primitives for query-independent dream releases.

This module does not run a model.  It provides the fail-closed state and
lineage boundaries around a later proposal generator and independent verifier.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, is_dataclass, replace
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple


class DreamProtocolError(ValueError):
    """Raised when a dream/release invariant would be violated."""


def instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise DreamProtocolError("timestamps must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return asdict(value)
    raise TypeError(f"cannot encode {type(value).__name__}")


def stable_json(value: Any) -> str:
    return json.dumps(
        value,
        default=_json_default,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _digest(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AuthorityEnvelope:
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
            raise DreamProtocolError("audience must be private or team")
        if self.audience == "private" and self.team_id is not None:
            raise DreamProtocolError("private evidence cannot have a team")
        if self.audience == "team" and not self.team_id:
            raise DreamProtocolError("team evidence requires a team")
        if not self.purposes:
            raise DreamProtocolError("authority envelope requires a purpose")
        if self.authorization_epoch <= 0:
            raise DreamProtocolError("authorization epoch must be positive")


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    content: str
    observed_at: datetime
    source_ref: str
    envelope: AuthorityEnvelope
    deleted_at: Optional[datetime] = None


@dataclass(frozen=True)
class DreamEvidence:
    evidence_id: str
    content: str
    observed_at: datetime
    source_ref: str
    content_digest: str


@dataclass(frozen=True)
class DreamInput:
    job_id: str
    cutoff: datetime
    generator_revision: str
    evidence: Tuple[DreamEvidence, ...]


@dataclass(frozen=True)
class _DreamJob:
    dream_input: DreamInput
    generator_id: str


@dataclass(frozen=True)
class Proposal:
    proposal_id: str
    job_id: str
    content: str
    citation_ids: Tuple[str, ...]
    generator_rationale: str
    envelope: AuthorityEnvelope


@dataclass(frozen=True)
class VerificationEvidence:
    evidence_id: str
    content: str
    observed_at: datetime
    source_ref: str
    content_digest: str


@dataclass(frozen=True)
class VerificationPacket:
    proposal_id: str
    content: str
    evidence: Tuple[VerificationEvidence, ...]
    envelope: AuthorityEnvelope
    packet_digest: str


@dataclass(frozen=True)
class VerificationRecord:
    verification_id: str
    proposal_id: str
    verifier_id: str
    verifier_revision: str
    verdict: str
    verified_at: datetime
    packet_digest: str


@dataclass(frozen=True)
class QuarantineRecord:
    proposal_id: str
    reason: str
    quarantined_at: datetime
    verification_id: str


@dataclass(frozen=True)
class SourceLineage:
    evidence_id: str
    source_ref: str
    observed_at: datetime
    content_digest: str


@dataclass(frozen=True)
class ReleasedProposal:
    proposal_id: str
    content: str
    citation_ids: Tuple[str, ...]
    envelope: AuthorityEnvelope
    source_lineage: Tuple[SourceLineage, ...]
    dream_job_id: str
    generator_revision: str
    verification_id: str
    verifier_revision: str


@dataclass(frozen=True)
class ReleaseSnapshot:
    release_id: str
    parent_release_id: Optional[str]
    released_at: datetime
    proposals: Tuple[ReleasedProposal, ...]


@dataclass(frozen=True)
class QueryAuthority:
    tenant_id: str
    subject_id: str
    teams: Tuple[str, ...]
    classification_ceiling: int
    purpose: str
    authorization_epoch: int


def intersect_authority_envelopes(
    envelopes: Tuple[AuthorityEnvelope, ...],
) -> AuthorityEnvelope:
    if not envelopes:
        raise DreamProtocolError("proposal requires cited evidence")
    if len({item.tenant_id for item in envelopes}) != 1:
        raise DreamProtocolError("cross-tenant evidence cannot be combined")
    if len({item.owner_subject_id for item in envelopes}) != 1:
        raise DreamProtocolError("cross-owner evidence cannot be combined")
    purposes = set(envelopes[0].purposes)
    for envelope in envelopes[1:]:
        purposes.intersection_update(envelope.purposes)
    if not purposes:
        raise DreamProtocolError("cited evidence has no common purpose")
    private = any(item.audience == "private" for item in envelopes)
    if private:
        audience = "private"
        team_id = None
    else:
        teams = {item.team_id for item in envelopes}
        if len(teams) != 1:
            raise DreamProtocolError("team evidence has no common audience")
        audience = "team"
        team_id = next(iter(teams))
    return AuthorityEnvelope(
        tenant_id=envelopes[0].tenant_id,
        owner_subject_id=envelopes[0].owner_subject_id,
        audience=audience,
        team_id=team_id,
        classification=max(item.classification for item in envelopes),
        purposes=tuple(sorted(purposes)),
        authorization_epoch=max(item.authorization_epoch for item in envelopes),
        policy_revision="intersection-" + _digest(
            sorted(item.policy_revision for item in envelopes)
        )[:16],
    )


class DreamReleasePipeline:
    def __init__(self) -> None:
        self._evidence: Dict[str, Evidence] = {}
        self._jobs: Dict[str, _DreamJob] = {}
        self._proposals: Dict[str, Proposal] = {}
        self._verifications: Dict[str, VerificationRecord] = {}
        self._proposal_statuses: Dict[str, str] = {}
        self._quarantine: Dict[str, QuarantineRecord] = {}
        self._releases: Tuple[ReleaseSnapshot, ...] = ()

    def add_evidence(self, row: Evidence) -> None:
        if row.evidence_id in self._evidence:
            raise DreamProtocolError("duplicate evidence id")
        self._evidence[row.evidence_id] = row

    def delete_evidence(self, evidence_id: str, *, deleted_at: datetime) -> None:
        try:
            row = self._evidence[evidence_id]
        except KeyError as exc:
            raise DreamProtocolError("unknown evidence") from exc
        if row.deleted_at is not None:
            raise DreamProtocolError("evidence is already deleted")
        if deleted_at < row.observed_at:
            raise DreamProtocolError("evidence cannot be deleted before it was observed")
        self._evidence[evidence_id] = replace(row, deleted_at=deleted_at)

    def start_dream(
        self,
        *,
        generator_id: str,
        generator_revision: str,
        cutoff: datetime,
    ) -> DreamInput:
        rows = tuple(
            DreamEvidence(
                evidence_id=row.evidence_id,
                content=row.content,
                observed_at=row.observed_at,
                source_ref=row.source_ref,
                content_digest=_digest(row.content),
            )
            for row in sorted(self._evidence.values(), key=lambda item: item.evidence_id)
            if row.observed_at <= cutoff
            and (row.deleted_at is None or row.deleted_at > cutoff)
        )
        job_id = "dream-" + _digest(
            {
                "generator_id": generator_id,
                "generator_revision": generator_revision,
                "cutoff": cutoff,
                "evidence": rows,
            }
        )[:24]
        dream_input = DreamInput(
            job_id=job_id,
            cutoff=cutoff,
            generator_revision=generator_revision,
            evidence=rows,
        )
        self._jobs[job_id] = _DreamJob(
            dream_input=dream_input,
            generator_id=generator_id,
        )
        return dream_input

    def submit_proposal(
        self,
        *,
        job_id: str,
        content: str,
        citation_ids: Tuple[str, ...],
        generator_rationale: str,
    ) -> Proposal:
        job = self._jobs.get(job_id)
        if job is None:
            raise DreamProtocolError("unknown dream job")
        normalized_citations = tuple(sorted(set(citation_ids)))
        if not normalized_citations:
            raise DreamProtocolError("proposal requires citations")
        frozen_ids = {row.evidence_id for row in job.dream_input.evidence}
        if any(item not in frozen_ids for item in normalized_citations):
            raise DreamProtocolError(
                "citations must exist in the frozen pre-cutoff dream input"
            )
        cited_rows = tuple(self._evidence[item] for item in normalized_citations)
        envelope = intersect_authority_envelopes(
            tuple(row.envelope for row in cited_rows)
        )
        proposal_id = "proposal-" + _digest(
            {
                "job_id": job_id,
                "content": content,
                "citation_ids": normalized_citations,
            }
        )[:24]
        if proposal_id in self._proposals:
            raise DreamProtocolError("duplicate proposal")
        proposal = Proposal(
            proposal_id=proposal_id,
            job_id=job_id,
            content=content,
            citation_ids=normalized_citations,
            generator_rationale=generator_rationale,
            envelope=envelope,
        )
        self._proposals[proposal_id] = proposal
        self._proposal_statuses[proposal_id] = "proposal"
        return proposal

    def verifier_packet(self, proposal_id: str) -> VerificationPacket:
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise DreamProtocolError("unknown proposal")
        evidence_rows = tuple(
            VerificationEvidence(
                evidence_id=row.evidence_id,
                content=row.content,
                observed_at=row.observed_at,
                source_ref=row.source_ref,
                content_digest=_digest(row.content),
            )
            for row in (self._evidence[item] for item in proposal.citation_ids)
        )
        packet_body = {
            "proposal_id": proposal.proposal_id,
            "content": proposal.content,
            "evidence": evidence_rows,
            "envelope": proposal.envelope,
        }
        return VerificationPacket(
            proposal_id=proposal.proposal_id,
            content=proposal.content,
            evidence=evidence_rows,
            envelope=proposal.envelope,
            packet_digest=_digest(packet_body),
        )

    def record_verification(
        self,
        *,
        proposal_id: str,
        verifier_id: str,
        verifier_revision: str,
        verdict: str,
        verified_at: datetime,
    ) -> VerificationRecord:
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            raise DreamProtocolError("unknown proposal")
        if self._proposal_statuses[proposal_id] != "proposal":
            raise DreamProtocolError("verification verdict is immutable")
        job = self._jobs[proposal.job_id]
        if verifier_id == job.generator_id:
            raise DreamProtocolError("proposal generator cannot verify its own output")
        if verdict not in {"verified", "contradicted", "insufficient", "unverified"}:
            raise DreamProtocolError("unknown verification verdict")
        packet = self.verifier_packet(proposal_id)
        verification_id = "verification-" + _digest(
            {
                "proposal_id": proposal_id,
                "verifier_id": verifier_id,
                "verifier_revision": verifier_revision,
                "verdict": verdict,
                "verified_at": verified_at,
                "packet_digest": packet.packet_digest,
            }
        )[:24]
        record = VerificationRecord(
            verification_id=verification_id,
            proposal_id=proposal_id,
            verifier_id=verifier_id,
            verifier_revision=verifier_revision,
            verdict=verdict,
            verified_at=verified_at,
            packet_digest=packet.packet_digest,
        )
        self._verifications[proposal_id] = record
        if verdict == "verified":
            self._proposal_statuses[proposal_id] = "verified"
        else:
            self._proposal_statuses[proposal_id] = "quarantined"
            self._quarantine[proposal_id] = QuarantineRecord(
                proposal_id=proposal_id,
                reason=verdict,
                quarantined_at=verified_at,
                verification_id=verification_id,
            )
        return record

    def proposal_status(self, proposal_id: str) -> str:
        try:
            return self._proposal_statuses[proposal_id]
        except KeyError as exc:
            raise DreamProtocolError("unknown proposal") from exc

    def quarantine_record(self, proposal_id: str) -> QuarantineRecord:
        try:
            return self._quarantine[proposal_id]
        except KeyError as exc:
            raise DreamProtocolError("proposal is not quarantined") from exc

    def release(
        self,
        *,
        proposal_ids: Tuple[str, ...],
        released_at: datetime,
    ) -> ReleaseSnapshot:
        if not proposal_ids:
            raise DreamProtocolError("release requires proposals")
        normalized_ids = tuple(proposal_ids)
        if len(set(normalized_ids)) != len(normalized_ids):
            raise DreamProtocolError("release cannot contain duplicate proposals")
        if self._releases and released_at <= self._releases[-1].released_at:
            raise DreamProtocolError("release time must advance monotonically")

        selected = []
        for proposal_id in normalized_ids:
            if self.proposal_status(proposal_id) != "verified":
                raise DreamProtocolError("only independently verified proposals can release")
            proposal = self._proposals[proposal_id]
            verification = self._verifications[proposal_id]
            job = self._jobs[proposal.job_id]
            if verification.verified_at > released_at:
                raise DreamProtocolError("verification cannot happen after release")
            if job.dream_input.cutoff > verification.verified_at:
                raise DreamProtocolError("verification cannot predate the dream cutoff")
            lineage = []
            for evidence_id in proposal.citation_ids:
                row = self._evidence.get(evidence_id)
                if row is None or (
                    row.deleted_at is not None and row.deleted_at <= released_at
                ):
                    raise DreamProtocolError(
                        "missing or deleted evidence prevents atomic release"
                    )
                lineage.append(
                    SourceLineage(
                        evidence_id=evidence_id,
                        source_ref=row.source_ref,
                        observed_at=row.observed_at,
                        content_digest=_digest(row.content),
                    )
                )
            selected.append(
                ReleasedProposal(
                    proposal_id=proposal.proposal_id,
                    content=proposal.content,
                    citation_ids=proposal.citation_ids,
                    envelope=proposal.envelope,
                    source_lineage=tuple(lineage),
                    dream_job_id=proposal.job_id,
                    generator_revision=job.dream_input.generator_revision,
                    verification_id=verification.verification_id,
                    verifier_revision=verification.verifier_revision,
                )
            )

        parent = self._releases[-1] if self._releases else None
        inherited = []
        if parent is not None:
            for item in parent.proposals:
                if all(
                    self._evidence[lineage.evidence_id].deleted_at is None
                    or self._evidence[lineage.evidence_id].deleted_at > released_at
                    for lineage in item.source_lineage
                ):
                    inherited.append(item)
        proposals = tuple(inherited + selected)
        if len({item.proposal_id for item in proposals}) != len(proposals):
            raise DreamProtocolError("proposal has already been released")
        payload = {
            "parent_release_id": parent.release_id if parent else None,
            "released_at": released_at,
            "proposals": proposals,
        }
        snapshot = ReleaseSnapshot(
            release_id="release-" + _digest(payload)[:24],
            parent_release_id=parent.release_id if parent else None,
            released_at=released_at,
            proposals=proposals,
        )

        # Commit point: no pipeline state changes occur before the complete
        # immutable snapshot has passed every validation above.
        self._releases = self._releases + (snapshot,)
        for proposal_id in normalized_ids:
            self._proposal_statuses[proposal_id] = "released"
        return snapshot

    def release_history(self) -> Tuple[ReleaseSnapshot, ...]:
        return self._releases

    def visible_proposals(
        self,
        *,
        at: datetime,
        authority: QueryAuthority,
    ) -> Tuple[ReleasedProposal, ...]:
        releases = [item for item in self._releases if item.released_at <= at]
        if not releases:
            return ()
        snapshot = releases[-1]
        visible = []
        for proposal in snapshot.proposals:
            envelope = proposal.envelope
            if envelope.tenant_id != authority.tenant_id:
                continue
            if envelope.classification > authority.classification_ceiling:
                continue
            if envelope.authorization_epoch != authority.authorization_epoch:
                continue
            if authority.purpose not in envelope.purposes:
                continue
            if envelope.audience == "private":
                if envelope.owner_subject_id != authority.subject_id:
                    continue
            elif envelope.team_id not in authority.teams:
                continue
            if any(
                self._evidence[lineage.evidence_id].deleted_at is not None
                and self._evidence[lineage.evidence_id].deleted_at <= at
                for lineage in proposal.source_lineage
            ):
                continue
            visible.append(proposal)
        return tuple(visible)
