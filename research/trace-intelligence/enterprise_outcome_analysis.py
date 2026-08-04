#!/usr/bin/env python3
"""Content-free enterprise trace analyses layered after the scope gate.

The functions here intentionally answer only structural, reviewed questions.
They never infer employee ability from raw traces, and they never aggregate
before ``enterprise_outcome_gate`` has authorized the candidate cohort.
"""

from __future__ import annotations

from dataclasses import dataclass
from collections import Counter, defaultdict
import hashlib
from typing import Any, Iterable

import enterprise_outcome_gate as gate


SCHEMA_VERSION = "frankengate-enterprise-outcome-analysis-v1"


@dataclass(frozen=True)
class OutcomeTrace:
    authority: gate.TraceRow
    task_family: str
    observed_capabilities: frozenset[str]
    required_capabilities: frozenset[str]
    friction_events: int
    recovery_events: int
    collaboration_opt_in: bool = False


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _label_counts(rows: Iterable[OutcomeTrace]) -> dict[str, int]:
    return dict(
        sorted(
            Counter(row.authority.human_outcome_label or "unlabeled" for row in rows).items()
        )
    )


def _base_rows(
    traces: Iterable[OutcomeTrace], request: gate.ScopeRequest
) -> tuple[gate.GateDecision, tuple[OutcomeTrace, ...]]:
    traces = tuple(traces)
    decision = gate.evaluate((trace.authority for trace in traces), request)
    if decision.decision != "allow":
        return decision, ()
    authorized = set(row.trace_id for row in gate.authorized_rows(
        (trace.authority for trace in traces), request
    ))
    return decision, tuple(
        trace for trace in traces if trace.authority.trace_id in authorized
    )


def analyze(
    traces: Iterable[OutcomeTrace], request: gate.ScopeRequest
) -> dict[str, Any]:
    """Compute one approved analysis or return an empty abstention payload."""

    decision, rows = _base_rows(traces, request)
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "analysis": request.analysis,
        "decision": decision.decision,
        "reason": decision.reason,
        "candidate_count": decision.candidate_count,
        "distinct_subject_count": decision.distinct_subject_count,
        "labeled_candidate_count": decision.labeled_candidate_count,
        "payload": {},
    }
    if decision.decision != "allow":
        return result

    if request.analysis == "similar_work":
        groups: dict[tuple[str, tuple[str, ...]], list[OutcomeTrace]] = defaultdict(list)
        for row in rows:
            groups[(row.task_family, tuple(sorted(row.observed_capabilities)))].append(row)
        result["payload"] = {
            "cohorts": [
                {
                    "task_family": task_family,
                    "observed_capability_digest": _digest("\0".join(capabilities)),
                    "subject_count": len({r.authority.owner_subject_id for r in group}),
                    "outcome_counts": _label_counts(group),
                }
                for (task_family, capabilities), group in sorted(groups.items())
            ]
        }
    elif request.analysis == "friction_recovery":
        friction = [row for row in rows if row.friction_events > 0]
        recovered = [row for row in friction if row.recovery_events > 0]
        result["payload"] = {
            "friction_trace_count": len(friction),
            "recovered_trace_count": len(recovered),
            "recovery_rate": round(len(recovered) / len(friction), 4) if friction else None,
            "outcome_counts": _label_counts(friction),
        }
    elif request.analysis == "skill_gap":
        required: Counter[str] = Counter()
        observed: Counter[str] = Counter()
        outcomes: dict[str, Counter[str]] = defaultdict(Counter)
        for row in rows:
            required.update(row.required_capabilities)
            observed.update(row.observed_capabilities)
            for capability in row.required_capabilities - row.observed_capabilities:
                outcomes[capability][row.authority.human_outcome_label or "unlabeled"] += 1
        result["payload"] = {
            "capability_gaps": [
                {
                    "capability": capability,
                    "required_count": required[capability],
                    "observed_count": observed[capability],
                    "gap_count": required[capability] - observed[capability],
                    "outcome_counts": dict(sorted(outcomes[capability].items())),
                }
                for capability in sorted(required)
                if required[capability] > observed[capability]
            ]
        }
    elif request.analysis == "collaboration":
        eligible = [row for row in rows if row.collaboration_opt_in]
        pairs: list[dict[str, Any]] = []
        for left_index, left in enumerate(eligible):
            for right in eligible[left_index + 1 :]:
                complement = (
                    left.required_capabilities & right.observed_capabilities
                ) | (
                    right.required_capabilities & left.observed_capabilities
                )
                if not complement or left.authority.owner_subject_id == right.authority.owner_subject_id:
                    continue
                pairs.append({
                    "subject_pair_digest": _digest(
                        "\0".join(sorted((left.authority.owner_subject_id, right.authority.owner_subject_id)))
                    ),
                    "complement_digest": _digest("\0".join(sorted(complement))),
                    "complement_count": len(complement),
                })
        result["payload"] = {
            "opted_in_subject_count": len({row.authority.owner_subject_id for row in eligible}),
            "candidate_pairs": sorted(pairs, key=lambda row: row["subject_pair_digest"]),
        }
    else:
        raise ValueError(f"unsupported analysis: {request.analysis}")
    return result
