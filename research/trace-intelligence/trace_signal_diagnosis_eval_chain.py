#!/usr/bin/env python3
"""Independent trace-selection, diagnosis, and eval-promotion experiment.

The mechanisms in this module are deliberately described as concept-inspired:

* cheap deterministic selection is inspired by the Signals paper;
* invariant-backed diagnosis is inspired by AgentRx;
* stored-trace assertions and replay are inspired by AgentEvals.

This is not a reimplementation or replication of those libraries or papers.
Full authorized local trace content is inspected in memory after the
credential-only gate. PII and ordinary internal content are preserved.
"""

from __future__ import annotations

import collections
import dataclasses
import hashlib
import json
import pathlib
from typing import Any, Iterable, Mapping, Optional, Sequence

from credential_only_gate import transform_credentials


SCHEMA_VERSION = "trace-signal-diagnosis-eval-chain-v1"
PURPOSE = "trace-intelligence-experiment"


class ChainError(ValueError):
    """Raised when the experiment cannot preserve its evidence contract."""


def _stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclasses.dataclass(frozen=True)
class TraceEvent:
    event_id: str
    order: int
    kind: str
    role: str
    content: str
    tool_name: Optional[str] = None
    call_id: Optional[str] = None
    is_error: bool = False


@dataclasses.dataclass(frozen=True)
class TraceEvidence:
    trace_ref: str
    events: tuple[TraceEvent, ...]
    source_records: int
    malformed_records: int
    credential_transformations: int
    credential_counts: Mapping[str, int]
    source_sha256: str


@dataclasses.dataclass(frozen=True)
class SignalReport:
    """Cheap label-blind review-selection evidence for one trace."""

    trace_ref: str
    detector_counts: Mapping[str, int]
    score: int
    evidence_event_ids: tuple[str, ...]
    method: str = "signals-inspired-deterministic-proxy-v1"


@dataclasses.dataclass(frozen=True)
class Diagnosis:
    """Evidence-linked hypothesis; never an unqualified root-cause claim."""

    trace_ref: str
    epistemic_status: str
    failure_taxonomy: str
    decisive_event_id: Optional[str]
    evidence_event_ids: tuple[str, ...]
    hypothesis: str
    alternatives: tuple[str, ...]
    method: str = "agentrx-inspired-invariant-proxy-v1"


@dataclasses.dataclass(frozen=True)
class AssertionSpec:
    assertion_id: str
    evaluation_mode: str
    assertion_kind: str
    signature_hashes: tuple[str, ...]
    evidence_event_ids: tuple[str, ...]
    source_taxonomy: str


@dataclasses.dataclass(frozen=True)
class EvalBundle:
    trace_ref: str
    stored_trace_assertions: tuple[AssertionSpec, ...]
    changed_system_assertions: tuple[AssertionSpec, ...]
    method: str = "agentevals-inspired-assertion-proxy-v1"


@dataclasses.dataclass(frozen=True)
class AssertionResult:
    assertion_id: str
    evaluation_mode: str
    assertion_kind: str
    status: str
    matched_signatures: int


def _event_id(
    trace_ref: str,
    order: int,
    kind: str,
    content: str,
) -> str:
    return "event-" + _sha256_text(
        f"{trace_ref}\0{order}\0{kind}\0{_sha256_text(content)}"
    )


def _message_role(record: Mapping[str, Any]) -> str:
    message = record.get("message")
    if isinstance(message, Mapping) and isinstance(message.get("role"), str):
        return str(message["role"])
    record_type = record.get("type")
    if record_type == "assistant":
        return "assistant"
    if record_type == "user":
        return "user"
    return "system"


def _append_event(
    events: list[TraceEvent],
    *,
    trace_ref: str,
    kind: str,
    role: str,
    content: str,
    tool_name: Optional[str] = None,
    call_id: Optional[str] = None,
    is_error: bool = False,
) -> None:
    order = len(events)
    events.append(
        TraceEvent(
            event_id=_event_id(trace_ref, order, kind, content),
            order=order,
            kind=kind,
            role=role,
            content=content,
            tool_name=tool_name,
            call_id=call_id,
            is_error=is_error,
        )
    )


def _events_from_record(
    record: Mapping[str, Any],
    *,
    trace_ref: str,
    events: list[TraceEvent],
) -> None:
    role = _message_role(record)
    message = record.get("message")
    if not isinstance(message, Mapping):
        scalar = record.get("content")
        if isinstance(scalar, str) and scalar:
            _append_event(
                events,
                trace_ref=trace_ref,
                kind="conversation.content",
                role=role,
                content=scalar,
            )
        return

    content = message.get("content")
    if isinstance(content, str):
        _append_event(
            events,
            trace_ref=trace_ref,
            kind=f"conversation.{role}",
            role=role,
            content=content,
        )
        return
    if not isinstance(content, list):
        return

    for block in content:
        if not isinstance(block, Mapping):
            continue
        block_type = block.get("type")
        if block_type == "tool_use":
            tool_name = block.get("name")
            call_id = block.get("id")
            tool_input = block.get("input")
            _append_event(
                events,
                trace_ref=trace_ref,
                kind="tool.proposed",
                role=role,
                content=_stable_json(tool_input),
                tool_name=tool_name if isinstance(tool_name, str) else None,
                call_id=call_id if isinstance(call_id, str) else None,
            )
        elif block_type == "tool_result":
            call_id = block.get("tool_use_id")
            is_error = (
                block.get("is_error") is True
                or block.get("isError") is True
            )
            _append_event(
                events,
                trace_ref=trace_ref,
                kind=(
                    "tool.result.error"
                    if is_error
                    else "tool.result.success"
                ),
                role=role,
                content=_stable_json(block.get("content")),
                call_id=call_id if isinstance(call_id, str) else None,
                is_error=is_error,
            )
        elif block_type in {"text", "thinking"}:
            text = block.get(block_type)
            if isinstance(text, str) and text:
                _append_event(
                    events,
                    trace_ref=trace_ref,
                    kind=(
                        "conversation.text"
                        if block_type == "text"
                        else "model.thinking"
                    ),
                    role=role,
                    content=text,
                )


def ingest_wisp_file(
    path: pathlib.Path,
    *,
    corpus_root: pathlib.Path,
    receipt_hmac_key: bytes,
    scope_ref: str,
    known_secrets: Optional[Mapping[str, str]] = None,
) -> TraceEvidence:
    """Load one Wisp JSONL trace through the credential-only capture gate."""

    path = pathlib.Path(path)
    corpus_root = pathlib.Path(corpus_root)
    try:
        relative = path.resolve().relative_to(corpus_root.resolve()).as_posix()
    except ValueError as error:
        raise ChainError("trace must be inside corpus_root") from error
    source_bytes = path.read_bytes()
    trace_ref = "trace-" + _sha256_text(
        relative + "\0" + hashlib.sha256(source_bytes).hexdigest()
    )
    events: list[TraceEvent] = []
    source_records = 0
    malformed_records = 0
    transformed_values = 0
    credential_counts: dict[str, int] = {}

    for raw_line in source_bytes.splitlines(keepends=True):
        source_records += 1
        try:
            raw_record = json.loads(raw_line)
        except (UnicodeDecodeError, json.JSONDecodeError):
            malformed_records += 1
            continue
        if not isinstance(raw_record, Mapping):
            continue
        clean_record, receipt = transform_credentials(
            raw_record,
            boundary="capture",
            receipt_hmac_key=receipt_hmac_key,
            scope_ref=scope_ref,
            purpose=PURPOSE,
            known_secrets=known_secrets,
        )
        transformed_values += int(receipt["transformed_values"])
        for credential_class, count in receipt["counts_by_class"].items():
            credential_counts[credential_class] = (
                credential_counts.get(credential_class, 0) + int(count)
            )
        _events_from_record(
            clean_record,
            trace_ref=trace_ref,
            events=events,
        )

    return TraceEvidence(
        trace_ref=trace_ref,
        events=tuple(events),
        source_records=source_records,
        malformed_records=malformed_records,
        credential_transformations=transformed_values,
        credential_counts=dict(sorted(credential_counts.items())),
        source_sha256=hashlib.sha256(source_bytes).hexdigest(),
    )


def _normalized_text(value: str) -> str:
    return " ".join(value.casefold().split())


def cheap_signals(trace: TraceEvidence) -> SignalReport:
    """Run deterministic review selectors without assigning a diagnosis."""

    detector_counts: dict[str, int] = {}
    evidence_ids: set[str] = set()
    proposals: dict[str, list[TraceEvent]] = {}
    result_call_ids: set[str] = set()
    user_text: dict[str, list[TraceEvent]] = {}
    action_signatures: dict[str, list[TraceEvent]] = {}
    failure_signatures: dict[str, list[TraceEvent]] = {}

    for event in trace.events:
        if event.kind == "tool.proposed":
            if event.call_id:
                proposals.setdefault(event.call_id, []).append(event)
            signature = _sha256_text(
                _normalized_text(event.tool_name or "")
                + "\0"
                + _normalized_text(event.content)
            )
            action_signatures.setdefault(signature, []).append(event)
        elif event.kind.startswith("tool.result."):
            if event.call_id:
                result_call_ids.add(event.call_id)
            if event.is_error:
                detector_counts["explicit_tool_error"] = (
                    detector_counts.get("explicit_tool_error", 0) + 1
                )
                evidence_ids.add(event.event_id)
                proposal = (
                    proposals.get(event.call_id or "", [None])[-1]
                    if event.call_id
                    else None
                )
                signature = _sha256_text(
                    _normalized_text(
                        proposal.tool_name
                        if isinstance(proposal, TraceEvent)
                        else ""
                    )
                    + "\0"
                    + _normalized_text(event.content)
                )
                failure_signatures.setdefault(signature, []).append(event)
        elif (
            event.role == "user"
            and event.kind.startswith("conversation.")
        ):
            normalized = _normalized_text(event.content)
            if normalized:
                user_text.setdefault(normalized, []).append(event)

    dangling = [
        proposal
        for call_id, matches in proposals.items()
        if call_id not in result_call_ids
        for proposal in matches
    ]
    if dangling:
        detector_counts["dangling_tool_proposal"] = len(dangling)
        evidence_ids.update(item.event_id for item in dangling)

    repeated_actions = [
        matches for matches in action_signatures.values() if len(matches) >= 3
    ]
    if repeated_actions:
        detector_counts["repeated_tool_action"] = len(repeated_actions)
        for matches in repeated_actions:
            evidence_ids.update(item.event_id for item in matches)

    repeated_failures = [
        matches for matches in failure_signatures.values() if len(matches) >= 2
    ]
    if repeated_failures:
        detector_counts["repeated_failure"] = len(repeated_failures)
        for matches in repeated_failures:
            evidence_ids.update(item.event_id for item in matches)

    rephrased = [matches for matches in user_text.values() if len(matches) >= 2]
    if rephrased:
        detector_counts["rephrasing"] = len(rephrased)
        for matches in rephrased:
            evidence_ids.update(item.event_id for item in matches)

    weights = {
        "explicit_tool_error": 3,
        "repeated_failure": 4,
        "dangling_tool_proposal": 2,
        "repeated_tool_action": 2,
        "rephrasing": 1,
    }
    score = sum(
        weights[detector] * count
        for detector, count in detector_counts.items()
    )
    event_order = {event.event_id: event.order for event in trace.events}
    return SignalReport(
        trace_ref=trace.trace_ref,
        detector_counts=dict(sorted(detector_counts.items())),
        score=score,
        evidence_event_ids=tuple(
            sorted(evidence_ids, key=lambda item: event_order[item])
        ),
    )


def select_for_review(
    traces: Sequence[TraceEvidence],
    *,
    budget: int,
) -> tuple[SignalReport, ...]:
    """Return the highest-scoring review candidates with stable tie-breaking."""

    if not isinstance(budget, int) or budget <= 0:
        raise ChainError("review budget must be a positive integer")
    reports = [
        report
        for trace in traces
        if (report := cheap_signals(trace)).score > 0
    ]
    reports.sort(
        key=lambda report: (
            -report.score,
            _sha256_text(report.trace_ref),
        )
    )
    return tuple(reports[: min(budget, len(reports))])


def _proposal_for_result(
    trace: TraceEvidence,
    result: TraceEvent,
) -> Optional[TraceEvent]:
    if not result.call_id:
        return None
    matches = [
        event
        for event in trace.events
        if (
            event.kind == "tool.proposed"
            and event.call_id == result.call_id
            and event.order < result.order
        )
    ]
    return matches[-1] if matches else None


def _failure_signature(
    trace: TraceEvidence,
    event: TraceEvent,
) -> str:
    proposal = _proposal_for_result(trace, event)
    return _sha256_text(
        _normalized_text(proposal.tool_name if proposal else "")
        + "\0"
        + _normalized_text(event.content)
    )


def diagnose_trace(
    trace: TraceEvidence,
    signal_report: SignalReport,
) -> Diagnosis:
    """Localize the earliest evidence for a deterministic failure hypothesis."""

    if signal_report.trace_ref != trace.trace_ref:
        raise ChainError("signal report belongs to a different trace")
    orphan_results = [
        event
        for event in trace.events
        if (
            event.kind.startswith("tool.result.")
            and _proposal_for_result(trace, event) is None
        )
    ]
    if orphan_results:
        decisive = orphan_results[0]
        return Diagnosis(
            trace_ref=trace.trace_ref,
            epistemic_status="hypothesis",
            failure_taxonomy="orphan_tool_result",
            decisive_event_id=decisive.event_id,
            evidence_event_ids=(decisive.event_id,),
            hypothesis=(
                "A tool result lacks a unique earlier proposal, so the "
                "trajectory cannot establish which requested action produced it."
            ),
            alternatives=(
                "source_export_loss",
                "parallel_branch_mismatch",
                "tool_protocol_violation",
            ),
        )
    failures: dict[str, list[TraceEvent]] = {}
    for event in trace.events:
        if event.is_error:
            failures.setdefault(
                _failure_signature(trace, event),
                [],
            ).append(event)
    repeated = [events for events in failures.values() if len(events) >= 2]
    if repeated:
        chosen = min(repeated, key=lambda events: events[0].order)
        return Diagnosis(
            trace_ref=trace.trace_ref,
            epistemic_status="hypothesis",
            failure_taxonomy="repeated_tool_failure",
            decisive_event_id=chosen[0].event_id,
            evidence_event_ids=tuple(event.event_id for event in chosen),
            hypothesis=(
                "Repeated equivalent tool failures may indicate an unresolved "
                "blocker at the first failed attempt."
            ),
            alternatives=(
                "permission_or_authority",
                "environment_or_incident",
                "tool_contract_or_availability",
                "invalid_input_or_assumption",
                "provider_or_model_behavior",
            ),
        )
    explicit_failures = [event for event in trace.events if event.is_error]
    if explicit_failures:
        decisive = explicit_failures[0]
        return Diagnosis(
            trace_ref=trace.trace_ref,
            epistemic_status="hypothesis",
            failure_taxonomy="explicit_tool_failure",
            decisive_event_id=decisive.event_id,
            evidence_event_ids=(decisive.event_id,),
            hypothesis=(
                "The exporter recorded an explicit tool failure at this step; "
                "the underlying blocker remains unresolved."
            ),
            alternatives=(
                "permission_or_authority",
                "environment_or_incident",
                "tool_contract_or_availability",
                "invalid_input_or_assumption",
                "provider_or_model_behavior",
            ),
        )
    return Diagnosis(
        trace_ref=trace.trace_ref,
        epistemic_status="abstain",
        failure_taxonomy="insufficient_evidence",
        decisive_event_id=None,
        evidence_event_ids=(),
        hypothesis="No deterministic invariant supports a failure hypothesis.",
        alternatives=(),
    )


def _assertion_id(
    trace_ref: str,
    mode: str,
    kind: str,
    signatures: Sequence[str],
) -> str:
    return "assertion-" + _sha256_text(
        _stable_json(
            {
                "trace_ref": trace_ref,
                "mode": mode,
                "kind": kind,
                "signatures": list(signatures),
            }
        )
    )


def promote_eval_bundle(
    trace: TraceEvidence,
    diagnosis: Diagnosis,
) -> EvalBundle:
    """Promote evidence into separate audit and prospective replay assertions."""

    if diagnosis.trace_ref != trace.trace_ref:
        raise ChainError("diagnosis belongs to a different trace")
    if diagnosis.epistemic_status != "hypothesis":
        return EvalBundle(
            trace_ref=trace.trace_ref,
            stored_trace_assertions=(),
            changed_system_assertions=(),
        )
    evidence_by_id = {event.event_id: event for event in trace.events}
    try:
        evidence = [
            evidence_by_id[event_id]
            for event_id in diagnosis.evidence_event_ids
        ]
    except KeyError as error:
        raise ChainError("diagnosis references missing evidence") from error

    if diagnosis.failure_taxonomy not in {
        "repeated_tool_failure",
        "explicit_tool_failure",
    }:
        return EvalBundle(
            trace_ref=trace.trace_ref,
            stored_trace_assertions=(),
            changed_system_assertions=(),
        )
    signatures = tuple(
        _failure_signature(trace, event)
        for event in evidence
        if event.is_error
    )
    stored_kind = "ordered_failure_evidence"
    changed_kind = "forbidden_failure_signature"
    stored = AssertionSpec(
        assertion_id=_assertion_id(
            trace.trace_ref,
            "stored_trace_audit",
            stored_kind,
            signatures,
        ),
        evaluation_mode="stored_trace_audit",
        assertion_kind=stored_kind,
        signature_hashes=signatures,
        evidence_event_ids=diagnosis.evidence_event_ids,
        source_taxonomy=diagnosis.failure_taxonomy,
    )
    changed = AssertionSpec(
        assertion_id=_assertion_id(
            trace.trace_ref,
            "changed_system_replay",
            changed_kind,
            signatures[:1],
        ),
        evaluation_mode="changed_system_replay",
        assertion_kind=changed_kind,
        signature_hashes=signatures[:1],
        evidence_event_ids=diagnosis.evidence_event_ids,
        source_taxonomy=diagnosis.failure_taxonomy,
    )
    return EvalBundle(
        trace_ref=trace.trace_ref,
        stored_trace_assertions=(stored,),
        changed_system_assertions=(changed,),
    )


def _ordered_subsequence(
    expected: Sequence[str],
    observed: Sequence[str],
) -> bool:
    cursor = 0
    for item in observed:
        if cursor < len(expected) and item == expected[cursor]:
            cursor += 1
    return cursor == len(expected)


def evaluate_assertions(
    trace: TraceEvidence,
    assertions: Sequence[AssertionSpec],
) -> tuple[AssertionResult, ...]:
    """Evaluate stored-trace or changed-system assertions against one trace."""

    failure_signatures = [
        _failure_signature(trace, event)
        for event in trace.events
        if event.is_error
    ]
    results: list[AssertionResult] = []
    for assertion in assertions:
        if assertion.assertion_kind == "ordered_failure_evidence":
            matched = sum(
                1
                for signature in assertion.signature_hashes
                if signature in failure_signatures
            )
            passed = _ordered_subsequence(
                assertion.signature_hashes,
                failure_signatures,
            )
        elif assertion.assertion_kind == "forbidden_failure_signature":
            matched = sum(
                failure_signatures.count(signature)
                for signature in set(assertion.signature_hashes)
            )
            passed = matched == 0
        else:
            raise ChainError(
                f"unsupported assertion kind: {assertion.assertion_kind}"
            )
        results.append(
            AssertionResult(
                assertion_id=assertion.assertion_id,
                evaluation_mode=assertion.evaluation_mode,
                assertion_kind=assertion.assertion_kind,
                status="pass" if passed else "fail",
                matched_signatures=matched,
            )
        )
    return tuple(results)


def _trace_with_events(
    trace: TraceEvidence,
    events: Iterable[TraceEvent],
    *,
    variant: str,
) -> TraceEvidence:
    normalized = tuple(
        dataclasses.replace(event, order=index)
        for index, event in enumerate(events)
    )
    return dataclasses.replace(
        trace,
        trace_ref="variant-" + _sha256_text(trace.trace_ref + "\0" + variant),
        events=normalized,
    )


def _without_event(
    trace: TraceEvidence,
    event_id: Optional[str],
) -> TraceEvidence:
    return _trace_with_events(
        trace,
        (event for event in trace.events if event.event_id != event_id),
        variant="remove-decisive-event",
    )


def _with_irrelevant_tail(trace: TraceEvidence) -> TraceEvidence:
    tail = TraceEvent(
        event_id="variant-event-" + _sha256_text(trace.trace_ref + "\0tail"),
        order=len(trace.events),
        kind="conversation.text",
        role="assistant",
        content="allowed unrelated tail event",
    )
    return _trace_with_events(
        trace,
        (*trace.events, tail),
        variant="irrelevant-tail",
    )


def _without_failure_signatures(
    trace: TraceEvidence,
    signatures: Sequence[str],
) -> TraceEvidence:
    blocked = set(signatures)
    retained = [
        event
        for event in trace.events
        if not (
            event.is_error
            and _failure_signature(trace, event) in blocked
        )
    ]
    return _trace_with_events(
        trace,
        retained,
        variant="remove-target-failure-signature",
    )


def _all_status(
    results: Sequence[AssertionResult],
    expected: str,
) -> bool:
    return bool(results) and all(item.status == expected for item in results)


def run_wisp_experiment(
    corpus_root: pathlib.Path,
    *,
    receipt_hmac_key: bytes,
    scope_ref: str,
    review_budget: int,
    dataset_id: str,
    dataset_revision: str,
    run_date: str,
    known_secrets: Optional[Mapping[str, str]] = None,
) -> dict[str, Any]:
    """Run the complete chain and return aggregate, content-free evidence."""

    corpus_root = pathlib.Path(corpus_root)
    paths = sorted(corpus_root.rglob("*.jsonl"))
    if not paths:
        raise ChainError("Wisp corpus contains no JSONL files")
    traces = [
        ingest_wisp_file(
            path,
            corpus_root=corpus_root,
            receipt_hmac_key=receipt_hmac_key,
            scope_ref=scope_ref,
            known_secrets=known_secrets,
        )
        for path in paths
    ]
    trace_by_ref = {trace.trace_ref: trace for trace in traces}
    all_reports = [cheap_signals(trace) for trace in traces]
    selected = select_for_review(traces, budget=review_budget)
    diagnoses = [
        diagnose_trace(trace_by_ref[report.trace_ref], report)
        for report in selected
    ]
    bundles = [
        promote_eval_bundle(trace_by_ref[diagnosis.trace_ref], diagnosis)
        for diagnosis in diagnoses
    ]

    detector_counts: collections.Counter[str] = collections.Counter()
    for report in all_reports:
        detector_counts.update(report.detector_counts)
    taxonomy_counts = collections.Counter(
        diagnosis.failure_taxonomy for diagnosis in diagnoses
    )
    credential_counts: collections.Counter[str] = collections.Counter()
    for trace in traces:
        credential_counts.update(trace.credential_counts)

    stored_observed_pass = 0
    stored_decisive_removal_killed = 0
    stored_irrelevant_tail_false_positive = 0
    changed_unchanged_failed = 0
    changed_failure_removed_passed = 0
    changed_irrelevant_tail_failed = 0
    promotable = 0
    for diagnosis, bundle in zip(diagnoses, bundles):
        trace = trace_by_ref[diagnosis.trace_ref]
        if not bundle.stored_trace_assertions:
            continue
        promotable += 1
        if _all_status(
            evaluate_assertions(
                trace,
                bundle.stored_trace_assertions,
            ),
            "pass",
        ):
            stored_observed_pass += 1
        if _all_status(
            evaluate_assertions(
                _without_event(trace, diagnosis.decisive_event_id),
                bundle.stored_trace_assertions,
            ),
            "fail",
        ):
            stored_decisive_removal_killed += 1
        if not _all_status(
            evaluate_assertions(
                _with_irrelevant_tail(trace),
                bundle.stored_trace_assertions,
            ),
            "pass",
        ):
            stored_irrelevant_tail_false_positive += 1

        changed_assertions = bundle.changed_system_assertions
        if _all_status(
            evaluate_assertions(trace, changed_assertions),
            "fail",
        ):
            changed_unchanged_failed += 1
        target_signatures = tuple(
            signature
            for assertion in changed_assertions
            for signature in assertion.signature_hashes
        )
        if _all_status(
            evaluate_assertions(
                _without_failure_signatures(trace, target_signatures),
                changed_assertions,
            ),
            "pass",
        ):
            changed_failure_removed_passed += 1
        if _all_status(
            evaluate_assertions(
                _with_irrelevant_tail(trace),
                changed_assertions,
            ),
            "fail",
        ):
            changed_irrelevant_tail_failed += 1

    source_set_sha256 = _sha256_text(
        _stable_json(sorted(trace.source_sha256 for trace in traces))
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "run_date": run_date,
        "content_free": True,
        "source": {
            "dataset_id": dataset_id,
            "dataset_revision": dataset_revision,
            "source_files": len(traces),
            "source_records": sum(trace.source_records for trace in traces),
            "canonical_events": sum(len(trace.events) for trace in traces),
            "malformed_records": sum(
                trace.malformed_records for trace in traces
            ),
            "source_record_set_sha256": source_set_sha256,
        },
        "credential_gate": {
            "policy": "credential_only_pii_preserved",
            "transformed_values": sum(
                trace.credential_transformations for trace in traces
            ),
            "counts_by_class": dict(sorted(credential_counts.items())),
            "known_secret_snapshot_entries": len(known_secrets or {}),
        },
        "selection": {
            "method": "signals-inspired-deterministic-proxy-v1",
            "review_budget": review_budget,
            "signal_positive_traces": sum(
                report.score > 0 for report in all_reports
            ),
            "selected_traces": len(selected),
            "detector_counts": dict(sorted(detector_counts.items())),
            "trace_length_used_for_ranking": False,
        },
        "diagnosis": {
            "method": "agentrx-inspired-invariant-proxy-v1",
            "diagnosed_traces": len(diagnoses),
            "taxonomy_counts": dict(sorted(taxonomy_counts.items())),
            "root_cause_claims": 0,
            "hypotheses": sum(
                diagnosis.epistemic_status == "hypothesis"
                for diagnosis in diagnoses
            ),
            "abstentions": sum(
                diagnosis.epistemic_status == "abstain"
                for diagnosis in diagnoses
            ),
        },
        "eval_promotion": {
            "method": "agentevals-inspired-assertion-proxy-v1",
            "promotable_diagnoses": promotable,
            "stored_trace_assertions": sum(
                len(bundle.stored_trace_assertions) for bundle in bundles
            ),
            "changed_system_assertions": sum(
                len(bundle.changed_system_assertions) for bundle in bundles
            ),
        },
        "replay": {
            "actual_changed_system_runs": 0,
            "supplied_changed_trace_evaluations": 0,
            "upstream_agentevals_runs": 0,
            "proxy_kind": "mutation_proxy_not_changed_system_replay",
            "stored_observed_pass": stored_observed_pass,
            "stored_decisive_removal_killed": (
                stored_decisive_removal_killed
            ),
            "stored_irrelevant_tail_false_positive": (
                stored_irrelevant_tail_false_positive
            ),
            "unchanged_trace_failed_regression_assertion": (
                changed_unchanged_failed
            ),
            "failure_removed_mutant_passed_regression_assertion": (
                changed_failure_removed_passed
            ),
            "irrelevant_tail_mutant_still_failed_regression_assertion": (
                changed_irrelevant_tail_failed
            ),
        },
        "claim_boundary": [
            "No Signals paper, AgentRx, or AgentEvals library replication is claimed.",
            "Diagnosis outputs are evidence-linked hypotheses, never root causes.",
            "Replay metrics are assertion evaluations over deterministic trace mutations, not executions of a changed agent or environment.",
            "A failure-removed mutant is not proof that a real system change fixes the task.",
            "No skill, productivity, collaboration, or employee-level inference is supported.",
        ],
    }


def render_markdown(result: Mapping[str, Any]) -> str:
    """Render the content-free result without expanding trace evidence."""

    source = result["source"]
    gate = result["credential_gate"]
    selection = result["selection"]
    diagnosis = result["diagnosis"]
    promotion = result["eval_promotion"]
    replay = result["replay"]
    lines = [
        "# Signals → diagnosis → eval-promotion Wisp experiment",
        "",
        f"**Run date:** {result['run_date']}",
        "",
        "## Claim boundary",
        "",
        "This is a dependency-light, concept-inspired experiment. It is not a "
        "replication or execution of the Signals paper, AgentRx, or "
        "AgentEvals.",
        "",
        "The final replay section is deterministic assertion mutation testing, "
        "**not changed-system replay**. Actual changed-system executions: "
        f"**{replay['actual_changed_system_runs']}**.",
        "",
        "## Full-fidelity internal corpus",
        "",
        f"- Files / source records: {source['source_files']} / "
        f"{source['source_records']}",
        f"- Canonical analysis events: {source['canonical_events']}",
        f"- Malformed records excluded from content analysis: "
        f"{source['malformed_records']}",
        f"- Credential transformations: {gate['transformed_values']}; "
        "PII and ordinary internal content were preserved",
        "",
        "## Chain result",
        "",
        f"- Signal-positive / selected traces: "
        f"{selection['signal_positive_traces']} / "
        f"{selection['selected_traces']}",
        f"- Evidence-linked hypotheses / root-cause claims: "
        f"{diagnosis['hypotheses']} / {diagnosis['root_cause_claims']}",
        f"- Stored-trace / changed-system assertion specifications: "
        f"{promotion['stored_trace_assertions']} / "
        f"{promotion['changed_system_assertions']}",
        f"- Stored audits passing the source trace: "
        f"{replay['stored_observed_pass']}",
        f"- Decisive-evidence removal mutants killed: "
        f"{replay['stored_decisive_removal_killed']}",
        f"- Irrelevant-tail stored-audit false positives: "
        f"{replay['stored_irrelevant_tail_false_positive']}",
        f"- Failure-removed mutants passing the prospective assertion: "
        f"{replay['failure_removed_mutant_passed_regression_assertion']}",
        "",
        "## Interpretation",
        "",
        "The chain can cheaply select real traces, attach deterministic "
        "evidence to contestable hypotheses, and emit separate stored-audit "
        "and prospective replay assertions. Mutation sensitivity only proves "
        "mechanical assertion behavior. It does not establish diagnostic "
        "accuracy, task recovery, causal benefit, or future-system behavior.",
        "",
        "The next gate is to execute the promoted prospective assertions "
        "against baseline and changed agents in a resettable environment with "
        "an independent outcome verifier.",
        "",
    ]
    return "\n".join(lines)
