#!/usr/bin/env python3
"""Bounded audit of Signals, AgentRx, and OpenRCA applicability.

This does not pretend that a local deterministic implementation is the upstream
paper or repository.  It runs the existing full-fidelity Signals/invariant
pipeline, then measures what evidence is actually available for the three
concepts and compares its review queue with deterministic baselines.  The
comparison is descriptive: without independent labels it cannot establish
diagnostic accuracy or causal RCA.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import random
from typing import Any, Mapping, Sequence

from trace_signal_diagnosis_eval_chain import (
    TraceEvidence,
    cheap_signals,
    diagnose_trace,
    ingest_wisp_file,
    select_for_review,
)


SCHEMA_VERSION = "faithful-diagnosis-concept-audit-v1"


def _sha(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def _evidence_profile(trace: TraceEvidence) -> dict[str, int]:
    return {
        "events": len(trace.events),
        "tool_proposals": sum(e.kind == "tool.proposed" for e in trace.events),
        "tool_results": sum(e.kind.startswith("tool.result.") for e in trace.events),
        "tool_errors": sum(e.is_error for e in trace.events),
        "conversation_events": sum(e.kind.startswith("conversation.") for e in trace.events),
        "model_thinking_events": sum(e.kind == "model.thinking" for e in trace.events),
        "timestamps": 0,
        "metrics": 0,
        "topology_edges": 0,
        "environment_snapshots": 0,
        "branch_ids": 0,
    }


def _queue_summary(
    traces: Sequence[TraceEvidence], selected: Sequence[TraceEvidence],
) -> dict[str, Any]:
    selected_refs = {t.trace_ref for t in selected}
    reports = {t.trace_ref: cheap_signals(t) for t in traces}
    return {
        "selected": len(selected),
        "signal_positive": sum(r.score > 0 for r in reports.values()),
        "selected_signal_evidence_traces": sum(
            bool(reports[t.trace_ref].evidence_event_ids) for t in selected
        ),
        "selected_tool_error_traces": sum(
            any(e.is_error for e in t.events) for t in selected
        ),
        "selected_refs_sha256": _sha(sorted(selected_refs)),
    }


def run_audit(
    corpus_root: pathlib.Path,
    *,
    receipt_hmac_key: bytes,
    scope_ref: str,
    dataset_id: str,
    dataset_revision: str,
    review_budget: int,
    run_date: str,
) -> dict[str, Any]:
    paths = sorted(pathlib.Path(corpus_root).rglob("*.jsonl"))
    traces = tuple(
        ingest_wisp_file(
            path,
            corpus_root=pathlib.Path(corpus_root),
            receipt_hmac_key=receipt_hmac_key,
            scope_ref=scope_ref,
        )
        for path in paths
    )
    if not traces:
        raise ValueError("no JSONL traces found")
    reports = {t.trace_ref: cheap_signals(t) for t in traces}
    signal_selected = tuple(
        next(t for t in traces if t.trace_ref == r.trace_ref)
        for r in select_for_review(traces, budget=review_budget)
    )
    by_length = tuple(sorted(traces, key=lambda t: (-len(t.events), t.trace_ref))[:review_budget])
    rng = random.Random(20260730)
    random_pool = list(traces)
    rng.shuffle(random_pool)
    random_selected = tuple(random_pool[:review_budget])

    diagnoses = tuple(diagnose_trace(t, reports[t.trace_ref]) for t in signal_selected)
    return {
        "schema_version": SCHEMA_VERSION,
        "run_date": run_date,
        "content_free": True,
        "source": {
            "dataset_id": dataset_id,
            "dataset_revision": dataset_revision,
            "source_files": len(paths),
            "source_records": sum(t.source_records for t in traces),
            "canonical_events": sum(len(t.events) for t in traces),
            "source_record_set_sha256": _sha(sorted(t.source_sha256 for t in traces)),
        },
        "concept_execution": {
            "signals": {
                "status": "executed_local_concept_proxy",
                "method": "cheap_signals_from_trace_signal_diagnosis_eval_chain",
                "queue": _queue_summary(traces, signal_selected),
                "baselines": {
                    "length": _queue_summary(traces, by_length),
                    "seeded_random": _queue_summary(traces, random_selected),
                },
            },
            "agentrx": {
                "status": "executed_local_concept_proxy",
                "method": "evidence_linked_invariant_hypothesis",
                "selected_traces": len(signal_selected),
                "hypotheses": sum(d.epistemic_status == "hypothesis" for d in diagnoses),
                "abstentions": sum(d.epistemic_status == "abstain" for d in diagnoses),
                "root_cause_claims": 0,
                "independent_labels": False,
            },
            "openrca": {
                "status": "not_executable_on_source",
                "method": "multimodal_rca_requires_metrics_logs_topology_and_clocks",
                "available_modalities": {
                    key: sum(_evidence_profile(t)[key] > 0 for t in traces)
                    for key in ("events", "tool_proposals", "tool_results", "tool_errors", "timestamps", "metrics", "topology_edges", "environment_snapshots")
                },
                "reason": "Wisp conversations expose event order and tool outcomes, but no metric, topology, timestamp, or environment-clock records.",
                "causal_claims": 0,
            },
        },
        "evidence_profile": {
            key: sum(_evidence_profile(t)[key] for t in traces)
            for key in _evidence_profile(traces[0])
        },
        "claim_boundary": [
            "No upstream Signals, AgentRx, or OpenRCA replication is claimed.",
            "Queue comparisons are descriptive and have no human or task-outcome labels.",
            "AgentRx outputs are hypotheses only; OpenRCA cannot run faithfully without multimodal time-aligned inputs.",
            "No skill, productivity, employee, or causal incident inference is supported.",
        ],
    }


def render_summary(result: Mapping[str, Any]) -> str:
    concepts = result["concept_execution"]
    signals = concepts["signals"]
    agentrx = concepts["agentrx"]
    openrca = concepts["openrca"]
    return "\n".join([
        "# Faithful diagnosis-concept audit",
        "",
        f"**Run date:** {result['run_date']}",
        "",
        "This run executes the local Signals and AgentRx concept proxies over the pinned Wisp corpus and audits OpenRCA input sufficiency. It does not claim upstream replication.",
        "",
        f"- Signals queue: {signals['queue']['selected']} selected; {signals['queue']['selected_tool_error_traces']} selected traces contain tool errors.",
        f"- Length baseline: {signals['baselines']['length']['selected_tool_error_traces']} selected traces contain tool errors.",
        f"- Seeded random baseline: {signals['baselines']['seeded_random']['selected_tool_error_traces']} selected traces contain tool errors.",
        f"- AgentRx-style hypotheses: {agentrx['hypotheses']}; abstentions: {agentrx['abstentions']}; root-cause claims: 0.",
        f"- OpenRCA status: {openrca['status']}; metrics/topology/timestamps/environment snapshots are absent from this corpus.",
        "",
        "The queue comparison is a screening description, not precision or recall: no independent informative-trace labels or task outcomes were available. A faithful OpenRCA trial requires an aligned OTel/log/metric/topology fixture and is therefore a separate blocked experiment, not a silent proxy.",
        "",
    ])

