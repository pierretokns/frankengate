#!/usr/bin/env python3
"""Blinded deterministic factorial for independently released memory mechanisms.

The executable fixture in this module is a protocol and composition check.  It
does not claim that any memory mechanism improves a model or an enterprise
user.  Natural-trace and prospective outcome studies remain separate gates.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hashlib
import hmac
import itertools
import json
from typing import Dict, Mapping, Optional, Sequence, Tuple

import dream_release_pipeline_v2 as dreams
import temporal_evidence_oracle_v2 as temporal


class ExperimentProtocolError(ValueError):
    """Raised when a fixture violates the frozen experiment boundary."""


def instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ExperimentProtocolError("timestamps must be timezone-aware")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class MemoryItem:
    item_ref: str
    content: str
    claim_key: str
    claim_value: str
    project_context: str
    artifact_context: str
    valid_from: datetime
    valid_to: Optional[datetime]
    known_at: datetime
    released_at: datetime
    citation_refs: Tuple[str, ...]
    derived: bool


@dataclass(frozen=True)
class QueryCase:
    query_ref: str
    query_text: str
    query_at: datetime
    target_valid_at: datetime
    project_context: str
    artifact_context: str
    claim_key: str
    gold_status: str
    gold_value: Optional[str]


@dataclass(frozen=True)
class ExperimentFixture:
    catalogs: Mapping[str, Tuple[MemoryItem, ...]]
    queries: Tuple[QueryCase, ...]
    release_protocol: Mapping[str, object]
    oracle_receipt: Mapping[str, object]


MECHANISMS = (
    "latest_snapshot",
    "bitemporal_ledger",
    "evidence_retrieval",
    "released_dream",
    "verbatim_state",
    "released_procedure",
)

FORBIDDEN_BLIND_FIELDS = {
    "arm",
    "mechanism",
    "mechanisms",
    "gold",
    "gold_status",
    "gold_value",
    "expected",
}


def build_deterministic_fixture() -> ExperimentFixture:
    query_at = instant("2026-03-10T00:00:00Z")
    queries = (
        QueryCase(
            query_ref="query-current-region",
            query_text="Which deployment region is current?",
            query_at=query_at,
            target_valid_at=instant("2026-03-01T00:00:00Z"),
            project_context="project-alpha",
            artifact_context="deployment.env",
            claim_key="deployment_region",
            gold_status="last_observed_only",
            gold_value="eu-west-1",
        ),
        QueryCase(
            query_ref="query-historical-region",
            query_text="Which deployment region applied on January 15?",
            query_at=query_at,
            target_valid_at=instant("2026-01-15T00:00:00Z"),
            project_context="project-alpha",
            artifact_context="deployment.env",
            claim_key="deployment_region",
            gold_status="resolved",
            gold_value="us-east-1",
        ),
        QueryCase(
            query_ref="query-feature-conflict",
            query_text="What is the feature flag state at the conflicting boundary?",
            query_at=query_at,
            target_valid_at=instant("2026-02-10T00:00:00Z"),
            project_context="project-alpha",
            artifact_context="feature.flag",
            claim_key="feature_flag",
            gold_status="conflict",
            gold_value=None,
        ),
        QueryCase(
            query_ref="query-cache-repair",
            query_text="Which successful procedure repairs a missing cache authorization epoch?",
            query_at=query_at,
            target_valid_at=instant("2026-03-01T00:00:00Z"),
            project_context="project-alpha",
            artifact_context="semantic-cache-recovery",
            claim_key="cache_repair",
            gold_status="last_observed_only",
            gold_value="refresh_authorization_epoch_before_retry",
        ),
    )
    catalog_release = instant("2026-02-20T00:00:00Z")
    sources = (
        MemoryItem(
            item_ref="state-region-old",
            content="region=us-east-1",
            claim_key="deployment_region",
            claim_value="us-east-1",
            project_context="project-alpha",
            artifact_context="deployment.env",
            valid_from=instant("2026-01-01T00:00:00Z"),
            valid_to=instant("2026-02-01T00:00:00Z"),
            known_at=instant("2026-01-01T00:00:01Z"),
            released_at=instant("2026-01-01T00:00:01Z"),
            citation_refs=("trace-region-old",),
            derived=False,
        ),
        MemoryItem(
            item_ref="state-region-current",
            content="region=eu-west-1",
            claim_key="deployment_region",
            claim_value="eu-west-1",
            project_context="project-alpha",
            artifact_context="deployment.env",
            valid_from=instant("2026-02-01T00:00:00Z"),
            valid_to=None,
            known_at=instant("2026-02-01T00:00:01Z"),
            released_at=instant("2026-02-01T00:00:01Z"),
            citation_refs=("trace-region-current",),
            derived=False,
        ),
        MemoryItem(
            item_ref="state-feature-base",
            content="feature_flag=baseline",
            claim_key="feature_flag",
            claim_value="baseline",
            project_context="project-alpha",
            artifact_context="feature.flag",
            valid_from=instant("2026-01-01T00:00:00Z"),
            valid_to=instant("2026-02-10T00:00:00Z"),
            known_at=instant("2026-01-01T00:00:02Z"),
            released_at=instant("2026-01-01T00:00:02Z"),
            citation_refs=("trace-feature-base",),
            derived=False,
        ),
        MemoryItem(
            item_ref="state-feature-on",
            content="feature_flag=on",
            claim_key="feature_flag",
            claim_value="on",
            project_context="project-alpha",
            artifact_context="feature.flag",
            valid_from=instant("2026-02-10T00:00:00Z"),
            valid_to=None,
            known_at=instant("2026-02-10T00:00:01Z"),
            released_at=instant("2026-02-10T00:00:01Z"),
            citation_refs=("trace-feature-on",),
            derived=False,
        ),
        MemoryItem(
            item_ref="state-feature-off",
            content="feature_flag=off",
            claim_key="feature_flag",
            claim_value="off",
            project_context="project-alpha",
            artifact_context="feature.flag",
            valid_from=instant("2026-02-10T00:00:00Z"),
            valid_to=None,
            known_at=instant("2026-02-10T00:00:01Z"),
            released_at=instant("2026-02-10T00:00:01Z"),
            citation_refs=("trace-feature-off",),
            derived=False,
        ),
        MemoryItem(
            item_ref="episode-cache-repair",
            content=(
                "A governed retry succeeded after "
                "refresh_authorization_epoch_before_retry."
            ),
            claim_key="cache_repair",
            claim_value="refresh_authorization_epoch_before_retry",
            project_context="project-alpha",
            artifact_context="semantic-cache-recovery",
            valid_from=instant("2026-01-20T00:00:00Z"),
            valid_to=None,
            known_at=instant("2026-01-20T00:00:01Z"),
            released_at=instant("2026-01-20T00:00:01Z"),
            citation_refs=("trace-cache-repair-success",),
            derived=False,
        ),
    )
    latest = []
    for scope in sorted(
        {(item.project_context, item.artifact_context) for item in sources}
    ):
        scoped = [
            item
            for item in sources
            if (item.project_context, item.artifact_context) == scope
        ]
        selected = sorted(
            scoped,
            key=lambda item: (
                item.valid_from,
                item.known_at,
                item.item_ref,
            ),
        )[-1]
        latest.append(
            replace(
                selected,
                item_ref="latest-" + selected.item_ref,
                released_at=catalog_release,
                citation_refs=(selected.item_ref,),
                derived=True,
            )
        )
    bitemporal = tuple(
        replace(
            item,
            item_ref="ledger-" + item.item_ref,
            released_at=catalog_release,
            citation_refs=(item.item_ref,),
            derived=True,
        )
        for item in sources
    )
    verbatim = tuple(
        replace(
            item,
            item_ref="verbatim-" + item.item_ref,
            released_at=catalog_release,
            citation_refs=(item.item_ref,),
            derived=True,
        )
        for item in sources
    )

    envelope = dreams.AuthorityEnvelope(
        tenant_id="tenant-a",
        owner_subject_id="alice",
        audience="private",
        team_id=None,
        classification=2,
        purposes=("trace_analysis",),
        authorization_epoch=7,
        policy_revision="policy-v1",
    )
    dream_pipeline = dreams.DreamReleasePipeline()
    for item in sources:
        dream_pipeline.add_evidence(
            dreams.Evidence(
                evidence_id=item.item_ref,
                content=item.content,
                observed_at=item.known_at,
                source_ref=item.citation_refs[0],
                envelope=envelope,
            )
        )
    dream_input = dream_pipeline.start_dream(
        generator_id="fixture-dream-generator",
        generator_revision="fixture-dream-v1",
        cutoff=instant("2026-02-12T00:00:00Z"),
    )
    proposal = dream_pipeline.submit_proposal(
        job_id=dream_input.job_id,
        content="The current deployment region is eu-west-1.",
        citation_ids=("state-region-old", "state-region-current"),
        generator_rationale="fixture-private-rationale",
    )
    verification = dream_pipeline.record_verification(
        proposal_id=proposal.proposal_id,
        verifier_id="fixture-independent-verifier",
        verifier_revision="fixture-verifier-v1",
        verdict="verified",
        verified_at=instant("2026-02-13T00:00:00Z"),
    )
    release = dream_pipeline.release(
        proposal_ids=(proposal.proposal_id,),
        released_at=instant("2026-02-14T00:00:00Z"),
    )
    visible = dream_pipeline.visible_proposals(
        at=query_at,
        authority=dreams.QueryAuthority(
            tenant_id="tenant-a",
            subject_id="alice",
            teams=(),
            classification_ceiling=2,
            purpose="trace_analysis",
            authorization_epoch=7,
        ),
    )
    if len(visible) != 1:
        raise ExperimentProtocolError("dream release is not query-visible")
    dream = MemoryItem(
        item_ref=visible[0].proposal_id,
        content=visible[0].content,
        claim_key="deployment_region",
        claim_value="eu-west-1",
        project_context="project-alpha",
        artifact_context="deployment.env",
        valid_from=instant("2026-02-01T00:00:00Z"),
        valid_to=None,
        known_at=dream_input.cutoff,
        released_at=release.released_at,
        citation_refs=visible[0].citation_ids,
        derived=True,
    )
    procedure_pipeline = dreams.DreamReleasePipeline()
    procedure_source = sources[-1]
    procedure_pipeline.add_evidence(
        dreams.Evidence(
            evidence_id=procedure_source.item_ref,
            content=procedure_source.content,
            observed_at=procedure_source.known_at,
            source_ref=procedure_source.citation_refs[0],
            envelope=envelope,
        )
    )
    procedure_input = procedure_pipeline.start_dream(
        generator_id="fixture-procedure-generator",
        generator_revision="fixture-reasoningbank-v1",
        cutoff=instant("2026-02-12T00:00:00Z"),
    )
    procedure_proposal = procedure_pipeline.submit_proposal(
        job_id=procedure_input.job_id,
        content=(
            "When a governed semantic-cache lookup lacks an authorization "
            "epoch, refresh_authorization_epoch_before_retry."
        ),
        citation_ids=(procedure_source.item_ref,),
        generator_rationale="fixture-private-procedure-rationale",
    )
    procedure_verification = procedure_pipeline.record_verification(
        proposal_id=procedure_proposal.proposal_id,
        verifier_id="fixture-procedure-verifier",
        verifier_revision="fixture-procedure-verifier-v1",
        verdict="verified",
        verified_at=instant("2026-02-14T00:00:00Z"),
    )
    procedure_release = procedure_pipeline.release(
        proposal_ids=(procedure_proposal.proposal_id,),
        released_at=instant("2026-02-15T00:00:00Z"),
    )
    visible_procedures = procedure_pipeline.visible_proposals(
        at=query_at,
        authority=dreams.QueryAuthority(
            tenant_id="tenant-a",
            subject_id="alice",
            teams=(),
            classification_ceiling=2,
            purpose="trace_analysis",
            authorization_epoch=7,
        ),
    )
    if len(visible_procedures) != 1:
        raise ExperimentProtocolError(
            "procedure release is not query-visible"
        )
    released_procedure = visible_procedures[0]
    procedure = MemoryItem(
        item_ref=released_procedure.proposal_id,
        content=released_procedure.content,
        claim_key="cache_repair",
        claim_value="refresh_authorization_epoch_before_retry",
        project_context="project-alpha",
        artifact_context="semantic-cache-recovery",
        valid_from=instant("2026-01-20T00:00:00Z"),
        valid_to=None,
        known_at=procedure_input.cutoff,
        released_at=procedure_release.released_at,
        citation_refs=released_procedure.citation_ids,
        derived=True,
    )
    catalogs = {
        "latest_snapshot": tuple(latest),
        "bitemporal_ledger": bitemporal,
        "evidence_retrieval": sources,
        "released_dream": (dream,),
        "verbatim_state": verbatim,
        "released_procedure": (procedure,),
    }
    temporal_parent_ids = {
        "state-region-old": (),
        "state-region-current": ("state-region-old",),
        "state-feature-base": (),
        "state-feature-on": ("state-feature-base",),
        "state-feature-off": ("state-feature-base",),
    }
    temporal_sources = sources[:5]
    temporal_events = tuple(
        temporal.TemporalEvidenceEvent(
            event_id=item.item_ref,
            event_type="write",
            succeeded=True,
            authority_subject="alice",
            project_context=item.project_context,
            artifact_context=item.artifact_context,
            content_sha256=hashlib.sha256(
                item.content.encode("utf-8")
            ).hexdigest(),
            valid_at=item.valid_from,
            known_at=item.known_at,
            parent_event_ids=temporal_parent_ids[item.item_ref],
        )
        for item in temporal_sources
    )
    oracle = temporal.TemporalEvidenceOracle(temporal_events)
    temporal_query_parents = {
        "query-current-region": ("state-region-current",),
        "query-historical-region": ("state-region-current",),
        "query-feature-conflict": (
            "state-feature-on",
            "state-feature-off",
        ),
    }
    temporal_gold_agreements = 0
    temporal_query_count = 0
    by_digest = {
        hashlib.sha256(item.content.encode("utf-8")).hexdigest():
        item.claim_value
        for item in temporal_sources
    }
    for query in queries[:3]:
        resolution = oracle.resolve(
            temporal.TemporalQuery(
                authority_subject="alice",
                project_context=query.project_context,
                artifact_context=query.artifact_context,
                valid_at=query.target_valid_at,
                known_at=query.query_at,
                parent_event_ids=temporal_query_parents[query.query_ref],
            )
        )
        selected_value = (
            by_digest[resolution.selected_revision.content_sha256]
            if resolution.selected_revision is not None
            else None
        )
        temporal_gold_agreements += int(
            resolution.status == query.gold_status
            and selected_value == query.gold_value
        )
        temporal_query_count += 1
    procedure_supported = (
        procedure_source.claim_key == queries[-1].claim_key
        and procedure_source.claim_value == queries[-1].gold_value
        and procedure_source.known_at < queries[-1].query_at
        and procedure.citation_refs == (procedure_source.item_ref,)
    )
    return ExperimentFixture(
        catalogs=catalogs,
        queries=queries,
        release_protocol={
            "catalog_cutoff": catalog_release,
            "dream_input_field_names": tuple(dream_input.__dataclass_fields__),
            "dream_generator_id": "fixture-dream-generator",
            "dream_verifier_id": verification.verifier_id,
            "dream_verdict": verification.verdict,
            "dream_released_at": release.released_at,
            "procedure_input_field_names": (
                tuple(procedure_input.__dataclass_fields__)
            ),
            "procedure_generator_id": "fixture-procedure-generator",
            "procedure_verifier_id": procedure_verification.verifier_id,
            "procedure_verdict": procedure_verification.verdict,
            "procedure_released_at": procedure.released_at,
            "procedure_release_id": procedure_release.release_id,
            "source_known_at": tuple(item.known_at for item in sources),
        },
        oracle_receipt={
            "temporal_queries_rederived": temporal_query_count,
            "temporal_gold_agreements": temporal_gold_agreements,
            "procedure_supported_by_successful_episode": procedure_supported,
            "gold_labels_seen_by_resolver": False,
            "all_query_gold_agreements": (
                temporal_gold_agreements + int(procedure_supported)
            ),
        },
    )


def replace_item(
    fixture: ExperimentFixture,
    *,
    mechanism: str,
    item_ref: str,
    released_at: datetime,
) -> ExperimentFixture:
    items = fixture.catalogs[mechanism]
    updated = tuple(
        replace(item, released_at=released_at)
        if item.item_ref == item_ref
        else item
        for item in items
    )
    catalogs: Dict[str, Tuple[MemoryItem, ...]] = dict(fixture.catalogs)
    catalogs[mechanism] = updated
    return replace(fixture, catalogs=catalogs)


def run_experiment(fixture: ExperimentFixture) -> dict:
    earliest_query = min(query.query_at for query in fixture.queries)
    all_released_before_queries = True
    for items in fixture.catalogs.values():
        for item in items:
            if item.derived and item.released_at >= earliest_query:
                raise ExperimentProtocolError(
                    "derived artifacts must release strictly before every query"
                )
            all_released_before_queries = (
                all_released_before_queries
                and item.released_at < earliest_query
            )

    arms = []
    forbidden_observed = set()
    case_count = 0
    for size in range(len(MECHANISMS) + 1):
        for enabled in itertools.combinations(MECHANISMS, size):
            arm_id = "arm-" + hashlib.sha256(
                ("\0".join(enabled) or "zero").encode("utf-8")
            ).hexdigest()[:16]
            exact_decisions = 0
            status_counts: Dict[str, int] = {}
            for query in fixture.queries:
                items = tuple(
                    item
                    for mechanism in enabled
                    for item in fixture.catalogs[mechanism]
                )
                payload = _blind_payload(
                    query=query,
                    items=items,
                    arm_id=arm_id,
                )
                forbidden_observed.update(
                    FORBIDDEN_BLIND_FIELDS.intersection(payload)
                )
                forbidden_observed.update(
                    field
                    for item in payload["items"]
                    for field in FORBIDDEN_BLIND_FIELDS.intersection(item)
                )
                decision = _blind_decide(payload)
                exact_decisions += int(
                    _score_blind_decision(
                        pack=payload,
                        decision=decision,
                        gold_status=query.gold_status,
                        gold_value=query.gold_value,
                    )
                )
                status = decision["epistemic_status"]
                status_counts[status] = status_counts.get(status, 0) + 1
                case_count += 1
            arms.append(
                {
                    "arm_id": arm_id,
                    "mechanisms": list(enabled),
                    "mechanism_count": len(enabled),
                    "exact_decisions": exact_decisions,
                    "exact_decision_rate": (
                        exact_decisions / len(fixture.queries)
                    ),
                    "decision_status_counts": status_counts,
                }
            )
    perfect_score = len(fixture.queries)
    singleton_arms = [
        arm for arm in arms if arm["mechanism_count"] == 1
    ]
    all_arm = next(
        arm
        for arm in arms
        if arm["mechanism_count"] == len(MECHANISMS)
    )
    strongest_singleton = max(
        arm["exact_decisions"] for arm in singleton_arms
    )
    result = {
        "schema_version": "frankengate-memory-mechanism-factorial-v1",
        "experiment_date": "2026-07-30",
        "fixture_revision": "memory-mechanism-authored-fixture-v1",
        "mechanisms": list(MECHANISMS),
        "design": {
            "arm_count": len(arms),
            "query_count": len(fixture.queries),
            "case_count": case_count,
            "zero_mechanism_arms": sum(
                arm["mechanism_count"] == 0 for arm in arms
            ),
            "single_mechanism_arms": sum(
                arm["mechanism_count"] == 1 for arm in arms
            ),
            "composed_arms": sum(
                arm["mechanism_count"] > 1 for arm in arms
            ),
            "all_blind_payloads_passed": not forbidden_observed,
            "forbidden_blind_payload_fields_observed": sorted(
                forbidden_observed
            ),
            "blinded_decision_fields": [
                "decision",
                "memory_ref",
                "epistemic_status",
            ],
            "scoring_interface_fields": [
                "decision",
                "gold_status",
                "gold_value",
                "pack",
            ],
        },
        "catalog_item_counts": {
            mechanism: len(fixture.catalogs[mechanism])
            for mechanism in MECHANISMS
        },
        "release_protocol": {
            "all_released_before_queries": all_released_before_queries,
            "dream_query_independent": not {
                "query",
                "query_text",
                "target_query",
                "gold",
            }.intersection(
                fixture.release_protocol["dream_input_field_names"]
            ),
            "dream_independently_verified": (
                fixture.release_protocol["dream_generator_id"]
                != fixture.release_protocol["dream_verifier_id"]
                and fixture.release_protocol["dream_verdict"] == "verified"
            ),
            "procedure_query_independent": not {
                "query",
                "query_text",
                "target_query",
                "gold",
            }.intersection(
                fixture.release_protocol[
                    "procedure_input_field_names"
                ]
            ),
            "procedure_independently_verified": (
                fixture.release_protocol["procedure_generator_id"]
                != fixture.release_protocol["procedure_verifier_id"]
                and fixture.release_protocol["procedure_verdict"]
                == "verified"
            ),
            "post_query_source_count": sum(
                timestamp >= earliest_query
                for timestamp in fixture.release_protocol["source_known_at"]
            ),
        },
        "oracle": dict(fixture.oracle_receipt),
        "arms": arms,
        "composition_summary": {
            "perfect_single_mechanism_arms": [
                arm["mechanisms"][0]
                for arm in singleton_arms
                if arm["exact_decisions"] == perfect_score
            ],
            "strongest_singleton_exact": strongest_singleton,
            "all_mechanisms_exact": all_arm["exact_decisions"],
            "all_minus_strongest_singleton": (
                all_arm["exact_decisions"] - strongest_singleton
            ),
            "perfect_composed_arm_count": sum(
                arm["mechanism_count"] > 1
                and arm["exact_decisions"] == perfect_score
                for arm in arms
            ),
            "interpretation": (
                "fixture_redundancy_not_empirical_equivalence"
            ),
        },
        "claim_boundary": {
            "mechanics_established": [
                "six_mechanism_full_factorial_enumeration",
                "pre_query_release_enforcement",
                "query_independent_generation_interface",
                "independent_verifier_and_immutable_release_path",
                "arm_and_gold_blinded_resolver_payload",
                "post_decision_independent_scoring",
                "bitemporal_gold_rederivation",
                "content_uniform_cross_mechanism_composition",
            ],
            "empirical_utility": "not_established",
            "required_utility_falsifiers": [
                "latest_snapshot_must_lose_to_bitemporal_on_predeclared_historical_or_conflict_queries",
                "released_dream_must_improve_held_out_task_outcomes_without_increasing_stale_or_contradicted_selections",
                "released_procedure_must_improve_project_and_time_held_out_verified_outcomes_versus_no_procedure_and_placebo",
                "composed_arms_must_outperform their strongest component without authority, latency, or evidence-budget regression",
                "benefit_must_replicate_on_natural_traces_and_consented_enterprise_users",
            ],
        },
        "empirical_scope": {
            "fixture_queries": len(fixture.queries),
            "natural_trace_units": 0,
            "enterprise_users": 0,
            "model_calls": 0,
            "causal_effect_estimated": False,
            "interpretation": (
                "Authored deterministic fixtures test mechanics and "
                "composition only; their exact-decision rates are not "
                "memory utility estimates."
            ),
        },
    }
    result["result_sha256"] = _result_digest(result)
    return result


def _blind_payload(
    *,
    query: QueryCase,
    items: Sequence[MemoryItem],
    arm_id: str,
) -> dict:
    keyed_items = []
    reference_key = hashlib.sha256(
        ("fixture-reference-key\0" + arm_id).encode("utf-8")
    ).digest()
    for index, item in enumerate(items):
        opaque_ref = "E_" + hmac.new(
            reference_key,
            (item.item_ref + "\0" + str(index)).encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()[:24]
        keyed_items.append(
            {
                "memory_ref": opaque_ref,
                "content": item.content,
                "claim_key": item.claim_key,
                "claim_value": item.claim_value,
                "project_context": item.project_context,
                "artifact_context": item.artifact_context,
                "valid_from": item.valid_from.isoformat(),
                "valid_to": (
                    item.valid_to.isoformat()
                    if item.valid_to is not None
                    else None
                ),
                "known_at": item.known_at.isoformat(),
                "released_at": item.released_at.isoformat(),
                "citation_count": len(item.citation_refs),
            }
        )
    return {
        "query_ref": query.query_ref,
        "query_text": query.query_text,
        "query_at": query.query_at.isoformat(),
        "target_valid_at": query.target_valid_at.isoformat(),
        "project_context": query.project_context,
        "artifact_context": query.artifact_context,
        "claim_key": query.claim_key,
        "items": keyed_items,
    }


def _blind_decide(pack: Mapping[str, object]) -> dict:
    """Resolve one pack without access to its arm or gold outcome."""

    target = instant(str(pack["target_valid_at"]))
    query_at = instant(str(pack["query_at"]))
    candidates = []
    for item in pack["items"]:
        if (
            item["project_context"] != pack["project_context"]
            or item["artifact_context"] != pack["artifact_context"]
            or item["claim_key"] != pack["claim_key"]
        ):
            continue
        valid_from = instant(item["valid_from"])
        valid_to = (
            instant(item["valid_to"])
            if item["valid_to"] is not None
            else None
        )
        if (
            instant(item["known_at"]) > query_at
            or instant(item["released_at"]) >= query_at
            or valid_from > target
            or (valid_to is not None and target >= valid_to)
        ):
            continue
        candidates.append((valid_from, item))
    if not candidates:
        return {
            "decision": "abstain",
            "memory_ref": None,
            "epistemic_status": "insufficient",
        }
    latest_boundary = max(row[0] for row in candidates)
    latest = [row[1] for row in candidates if row[0] == latest_boundary]
    values = {item["claim_value"] for item in latest}
    if len(values) != 1:
        return {
            "decision": "abstain",
            "memory_ref": None,
            "epistemic_status": "conflict",
        }
    selected = sorted(latest, key=lambda item: item["memory_ref"])[0]
    return {
        "decision": "select",
        "memory_ref": selected["memory_ref"],
        "epistemic_status": (
            "last_observed_only"
            if selected["valid_to"] is None
            else "resolved"
        ),
    }


def _score_blind_decision(
    *,
    pack: Mapping[str, object],
    decision: Mapping[str, object],
    gold_status: str,
    gold_value: Optional[str],
) -> bool:
    """Score only after the blinded resolver has returned its decision."""

    if decision["epistemic_status"] != gold_status:
        return False
    if gold_status not in {"resolved", "last_observed_only"}:
        return decision["decision"] == "abstain"
    selected = next(
        (
            item
            for item in pack["items"]
            if item["memory_ref"] == decision["memory_ref"]
        ),
        None,
    )
    return (
        decision["decision"] == "select"
        and selected is not None
        and selected["claim_value"] == gold_value
    )


def _result_digest(result: Mapping[str, object]) -> str:
    body = dict(result)
    body.pop("result_sha256", None)
    serialized = json.dumps(
        body,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def verify_result(result: Mapping[str, object]) -> bool:
    digest = result.get("result_sha256")
    return (
        isinstance(digest, str)
        and len(digest) == 64
        and hmac.compare_digest(digest, _result_digest(result))
    )


if __name__ == "__main__":
    print(
        json.dumps(
            run_experiment(build_deterministic_fixture()),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
