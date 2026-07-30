#!/usr/bin/env python3
"""Corrected, blinded longitudinal-memory experiment primitives.

This module is intentionally separate from the completed exploratory pilot.
It exposes the protocol surfaces that must remain stable before a new model
run is permitted.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import json
import re
from typing import Any, Mapping, Optional, Sequence


STATE_VIEWS = (
    "latest_snapshot",
    "temporal_ledger",
    "temporal_plus_released_dream",
)


class CorrectedProtocolError(RuntimeError):
    """Raised when a corrected-run protocol invariant is violated."""


@dataclass(frozen=True)
class CorrectedEvidence:
    evidence_ref: str
    content: str
    content_sha256: str
    source_kind: str
    authority_subject: str
    project_context: str
    artifact_context: str
    revision_digest: str
    known_at: str
    valid_from: str
    valid_to: Optional[str]
    interval_gap_known_at_cutoff: bool


def frozen_intervention_order(
    *,
    unit_key: str,
    seed: int,
) -> tuple[str, ...]:
    """Return a reproducible, unit-specific intervention order."""

    if (
        not isinstance(unit_key, str)
        or not unit_key
        or not isinstance(seed, int)
    ):
        raise CorrectedProtocolError(
            "unit key and integer seed are required"
        )
    return tuple(
        sorted(
            STATE_VIEWS,
            key=lambda view: hashlib.sha256(
                (
                    "frankengate-intervention-order-v2\0"
                    + str(seed)
                    + "\0"
                    + unit_key
                    + "\0"
                    + view
                ).encode("utf-8")
            ).digest(),
        )
    )


def pack_whole_evidence(
    *,
    base_evidence: Sequence[CorrectedEvidence],
    proposal_evidence: Sequence[CorrectedEvidence],
    token_cost_by_ref: Mapping[str, int],
    token_budget: int,
) -> tuple[list[CorrectedEvidence], dict[str, Any]]:
    """Pack complete base items first, then complete proposals."""

    if not isinstance(token_budget, int) or token_budget <= 0:
        raise CorrectedProtocolError("token budget must be positive")
    all_items = [*base_evidence, *proposal_evidence]
    refs = [item.evidence_ref for item in all_items]
    if len(refs) != len(set(refs)):
        raise CorrectedProtocolError(
            "evidence references must be unique"
        )
    for item in all_items:
        if (
            hashlib.sha256(
                item.content.encode("utf-8")
            ).hexdigest()
            != item.content_sha256
        ):
            raise CorrectedProtocolError(
                "evidence content digest mismatch"
            )
        cost = token_cost_by_ref.get(item.evidence_ref)
        if not isinstance(cost, int) or cost <= 0:
            raise CorrectedProtocolError(
                "every evidence item needs a positive token cost"
            )

    base_tokens = sum(
        token_cost_by_ref[item.evidence_ref]
        for item in base_evidence
    )
    if base_tokens > token_budget:
        raise CorrectedProtocolError(
            "required base evidence exceeds token budget"
        )
    packed = list(base_evidence)
    dropped: list[str] = []
    tokens_used = base_tokens
    for item in proposal_evidence:
        item_tokens = token_cost_by_ref[item.evidence_ref]
        if tokens_used + item_tokens <= token_budget:
            packed.append(item)
            tokens_used += item_tokens
        else:
            dropped.append(item.evidence_ref)
    return packed, {
        "schema_version": "frankengate.whole-item-budget.v2",
        "token_budget": token_budget,
        "tokens_used": tokens_used,
        "base_items": len(base_evidence),
        "proposal_items_retained": (
            len(packed) - len(base_evidence)
        ),
        "proposal_items_dropped": len(dropped),
        "dropped_refs": dropped,
        "whole_items_only": True,
    }


def opaque_evidence_ref(
    *,
    source_label: str,
    event_key: str,
    unit_key: str,
    intervention_key: str,
    repeat_index: int,
    reference_hmac_key: bytes,
) -> str:
    """Return a rank-free reference re-keyed per intervention execution."""

    if (
        not isinstance(reference_hmac_key, bytes)
        or len(reference_hmac_key) < 32
        or not isinstance(repeat_index, int)
        or repeat_index < 0
    ):
        raise CorrectedProtocolError(
            "reference key and repeat index are invalid"
        )
    digest = hmac.new(
        reference_hmac_key,
        (
            "frankengate-corrected-evidence-ref-v2\0"
            + unit_key
            + "\0"
            + intervention_key
            + "\0"
            + str(repeat_index)
            + "\0"
            + source_label
            + "\0"
            + event_key
        ).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return "E_" + digest[:24]


def parse_native_state_decision(
    response: Mapping[str, Any],
) -> Mapping[str, Any]:
    """Parse only the corrected native-tool response protocol."""

    choices = response.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise CorrectedProtocolError("exactly one response choice is required")
    choice = choices[0]
    if (
        not isinstance(choice, Mapping)
        or choice.get("finish_reason") != "tool_calls"
    ):
        raise CorrectedProtocolError(
            "native tool_calls finish reason is required"
        )
    message = choice.get("message")
    if not isinstance(message, Mapping):
        raise CorrectedProtocolError("response message is missing")
    calls = message.get("tool_calls")
    if not isinstance(calls, list) or len(calls) != 1:
        raise CorrectedProtocolError(
            "exactly one native tool call is required"
        )
    call = calls[0]
    if not isinstance(call, Mapping) or call.get("type") != "function":
        raise CorrectedProtocolError("tool call type must be function")
    function = call.get("function")
    if (
        not isinstance(function, Mapping)
        or function.get("name") != "submit_state_decision"
    ):
        raise CorrectedProtocolError(
            "submit_state_decision tool is required"
        )
    arguments = function.get("arguments")
    if not isinstance(arguments, str):
        raise CorrectedProtocolError("tool arguments must be JSON text")
    try:
        value = json.loads(arguments)
    except json.JSONDecodeError as exc:
        raise CorrectedProtocolError(
            "tool arguments are not strict JSON"
        ) from exc
    if not isinstance(value, dict) or set(value) != {
        "decision",
        "memory_ref",
        "epistemic_status",
        "reason",
    }:
        raise CorrectedProtocolError(
            "state decision fields do not match the frozen schema"
        )
    decision = value["decision"]
    memory_ref = value["memory_ref"]
    expected_reason = {
        "resolved": "unique_supported_state",
        "last_observed_only": "last_observation_with_open_gap",
        "conflict": "incompatible_overlap",
        "insufficient": "no_eligible_evidence",
    }.get(value["epistemic_status"])
    if expected_reason is None or value["reason"] != expected_reason:
        raise CorrectedProtocolError(
            "epistemic status and reason are inconsistent"
        )
    if decision == "select":
        if (
            value["epistemic_status"]
            not in {"resolved", "last_observed_only"}
            or not isinstance(memory_ref, str)
            or re.fullmatch(r"E_[0-9a-f]{24}", memory_ref) is None
        ):
            raise CorrectedProtocolError(
                "selection requires one opaque evidence reference"
            )
    elif decision == "abstain":
        if (
            value["epistemic_status"] not in {"conflict", "insufficient"}
            or memory_ref is not None
        ):
            raise CorrectedProtocolError(
                "abstention requires a null evidence reference"
            )
    else:
        raise CorrectedProtocolError("state decision enum is invalid")
    return value


def evaluate_state_decision(
    *,
    oracle_pre_cutoff: Sequence[CorrectedEvidence],
    arm_pre_budget: Sequence[CorrectedEvidence],
    supplied_post_budget: Sequence[CorrectedEvidence],
    gold_epistemic_status: str,
    acceptable_content_sha256: set[str],
    decision: Mapping[str, Any],
    later_observation_content_sha256: Optional[str] = None,
) -> dict[str, Any]:
    """Score online state reasoning separately from later observations."""

    def acceptable(item: CorrectedEvidence) -> bool:
        return item.content_sha256 in acceptable_content_sha256

    oracle_exact = any(acceptable(item) for item in oracle_pre_cutoff)
    arm_exact = any(acceptable(item) for item in arm_pre_budget)
    retained_exact = any(
        acceptable(item) for item in supplied_post_budget
    )
    supplied_by_ref = {
        item.evidence_ref: item for item in supplied_post_budget
    }
    selected = supplied_by_ref.get(str(decision.get("memory_ref") or ""))
    selected_exact = selected is not None and acceptable(selected)
    abstained = decision.get("decision") == "abstain"
    selection_required = gold_epistemic_status in {
        "resolved",
        "last_observed_only",
    }
    if selection_required and not oracle_exact:
        raise CorrectedProtocolError(
            "selection gold has no acceptable pre-cutoff evidence"
        )
    epistemic_status_correct = (
        decision.get("epistemic_status") == gold_epistemic_status
    )
    if selection_required:
        task_correct = selected_exact and epistemic_status_correct
    else:
        task_correct = abstained and epistemic_status_correct
    later_agreement: Optional[bool]
    if later_observation_content_sha256 is None:
        later_agreement = None
    else:
        later_agreement = (
            selected is not None
            and selected.content_sha256
            == later_observation_content_sha256
        )
    return {
        "oracle_exact_available": oracle_exact,
        "arm_exact_available_pre_budget": arm_exact,
        "exact_retained_post_budget": retained_exact,
        "retrieval_stage_success": (
            arm_exact and retained_exact
            if selection_required
            else True
        ),
        "selected_exact": selected_exact,
        "valid_reference": (
            selected is not None if not abstained else True
        ),
        "epistemic_status_correct": epistemic_status_correct,
        "task_decision_correct": task_correct,
        "reasoning_correct_given_retained_exact": (
            task_correct if retained_exact else None
        ),
        "later_observation_agreement": later_agreement,
    }


def serialize_state_pack(
    *,
    target_query: Mapping[str, Any],
    evidence: Sequence[CorrectedEvidence],
    view: str,
) -> dict[str, Any]:
    """Serialize one blinded state-selection intervention."""

    if view not in STATE_VIEWS:
        raise ValueError("unknown state evidence view")
    required_query_fields = {
        "artifact_name",
        "project_context",
        "valid_at",
        "known_at",
    }
    if (
        not isinstance(target_query, Mapping)
        or set(target_query) != required_query_fields
        or any(
            not isinstance(target_query[field], str)
            or not target_query[field]
            for field in required_query_fields
        )
    ):
        raise CorrectedProtocolError(
            "query does not match the frozen blinded schema"
        )
    selected = evidence
    if view == "latest_snapshot":
        serialized = [
            {
                "memory_ref": item.evidence_ref,
                "content": item.content,
                "context": [],
                "valid_time": None,
                "recorded_at": None,
                "source_refs": [],
            }
            for item in selected
        ]
    else:
        serialized = [
            {
                "memory_ref": item.evidence_ref,
                "content": item.content,
                "context": [
                    ["authority_subject", item.authority_subject],
                    ["project", item.project_context],
                    ["artifact", item.artifact_context],
                    ["source_kind", item.source_kind],
                    ["revision", item.revision_digest],
                ],
                "valid_time": {
                    "lower": item.valid_from,
                    "upper": item.valid_to,
                    "precision": (
                        "interval_censored"
                        if item.interval_gap_known_at_cutoff
                        else "exact"
                    ),
                },
                "recorded_at": item.known_at,
                "source_refs": [item.evidence_ref],
            }
            for item in selected
        ]
    return {
        "protocol": "longitudinal-state-v2",
        "task": "context_artifact_state_selection",
        "query": dict(target_query),
        "eligible_pre_cutoff_evidence": serialized,
        "response_contract": {
            "decision": ["select", "abstain"],
            "memory_ref": (
                "one supplied memory_ref for select; null for abstain"
            ),
            "epistemic_status": [
                "resolved",
                "last_observed_only",
                "conflict",
                "insufficient",
            ],
            "reason": [
                "unique_supported_state",
                "last_observation_with_open_gap",
                "incompatible_overlap",
                "no_eligible_evidence",
            ],
            "additional_properties": False,
        },
    }
