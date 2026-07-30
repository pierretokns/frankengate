#!/usr/bin/env python3
"""Source-pinned empirical audit of the public MAST-Data release.

This program deliberately keeps three authorities apart:

* raw multi-agent execution text is structural evidence;
* ``MAD_full_dataset.json`` contains LLM-judge label codes; and
* ``MAD_human_labelled_dataset.json`` contains per-human votes under several
  evolving taxonomy versions.

No raw trace or annotation text is written to the aggregate result.  The
canonical adapter is lossless at the source-line layer, while role and
communication structure is only emitted when a source marker supports it.
Sequential-turn edges are explicitly ``reconstructed`` and never presented as
observed handoffs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence


RESULT_SCHEMA_VERSION = "mast-multiagent-empirical-result-v1"
CANONICAL_SCHEMA_VERSION = "canonical-trajectory-v1"
ADAPTER_VERSION = "mast-heterogeneous-text-v1"
DATASET_ID = "mcemri/MAST-Data"
DATASET_REVISION = "5a82e32347f70a701a3c68637de12f8a0be3de3c"
CODE_REPOSITORY = "multi-agent-systems-failure-taxonomy/MAST"
CODE_REVISION = "a70542e541b2104ef8fcd785778179e173fb8d70"
DECLARED_DATASET_LICENSE = "CC-BY-4.0"

MAST_TAXONOMY = {
    "1.1": "Disobey Task Specification",
    "1.2": "Disobey Role Specification",
    "1.3": "Step Repetition",
    "1.4": "Loss of Conversation History",
    "1.5": "Unaware of Termination Conditions",
    "2.1": "Conversation Reset",
    "2.2": "Fail to Ask for Clarification",
    "2.3": "Task Derailment",
    "2.4": "Information Withholding",
    "2.5": "Ignored Other Agent's Input",
    "2.6": "Action-Reasoning Mismatch",
    "3.1": "Premature Termination",
    "3.2": "No or Incomplete Verification",
    "3.3": "Incorrect Verification",
}
MAST_CODES = tuple(MAST_TAXONOMY)
KNOWN_MISSING_FIELDS = (
    "stable_span_and_message_ids",
    "tool_call_and_result_ids",
    "causal_parent_ids",
    "task_outcome_ground_truth",
    "authorization_and_governance_context",
    "agent_configuration_versions",
    "environment_snapshot_and_replay_seed",
)

_META_FROM_TO = re.compile(
    r"\bFROM:\s*(?P<sender>.+?)\s+TO:\s*(?P<receiver>.+?)\s*$",
    re.IGNORECASE,
)
_METAGPT_SPEAKER = re.compile(
    r"^\s*(?P<speaker>[A-Z][A-Za-z0-9 _.-]{1,80}):\s*$"
)
_CHATDEV_TURN = re.compile(
    r"^\[[^\]]+\]\s+(?P<speaker>[^:]+):\s+\*{0,2}"
    r"(?P<left>[^*<]+)<->(?P<right>[^*]+?)\s+on\s*:\s*"
    r"(?P<phase>[^,*]+)",
)
_MAGENTIC_HEADER = re.compile(r"^\s*-{5,}\s*(?P<speaker>[^-].*?)\s*-{5,}\s*$")
_APP_MESSAGE_TO = re.compile(r"^\s*Message to (?P<receiver>.+? Agent)\s*$", re.I)
_APP_RESPONSE_FROM = re.compile(
    r"^\s*Response from (?P<sender>.+?(?: Agent| API))\s*$", re.I
)
_HYPER_RESPONSE = re.compile(
    r"\bINFO\s+-\s+(?P<speaker>[^:]+?)'s Response:", re.I
)
_HYPER_INTERN = re.compile(r"^\s*Intern Name:\s*(?P<speaker>.+?)\s*$", re.I)
_AG2_ROLE = re.compile(r"^\s*role:\s*(?P<role>[A-Za-z0-9_. -]+)\s*$")
_AG2_NAME = re.compile(r"^\s*name:\s*(?P<speaker>[A-Za-z0-9_. -]+)\s*$")
_OPENMANUS_THOUGHT = re.compile(r"\bManus's thoughts:", re.I)

_SURFACE_RULES: dict[str, re.Pattern[str]] = {
    "1.1": re.compile(
        r"\b(?:violat(?:e|ed|ion)|task specification|failed? requirements?|"
        r"constraint compliance)\b",
        re.I,
    ),
    "1.2": re.compile(
        r"\b(?:role specification|outside (?:its|their) role|wrong role|"
        r"disobey(?:ed)? role)\b",
        re.I,
    ),
    "1.3": re.compile(
        r"\b(?:step repetition|repeated (?:the )?same|repeat(?:ed|ing) "
        r"(?:step|action|request)|same (?:step|action).{0,40}again)\b",
        re.I | re.S,
    ),
    "1.4": re.compile(
        r"\b(?:loss of conversation history|lost (?:the )?context|"
        r"forgot (?:the )?(?:previous|recent)|context truncat)\w*\b",
        re.I,
    ),
    "1.5": re.compile(
        r"\b(?:termination condition|stopping condition|max(?:imum)?[_ ]steps|"
        r"executing step \d+/\d+)\b",
        re.I,
    ),
    "2.1": re.compile(
        r"\b(?:conversation reset|restart(?:ed|ing)? (?:the )?"
        r"(?:dialogue|conversation)|start(?:ed|ing)? over)\b",
        re.I,
    ),
    "2.2": re.compile(
        r"\b(?:ask for clarification|need more information|"
        r"missing information|ambiguous (?:request|instruction))\b",
        re.I,
    ),
    "2.3": re.compile(
        r"\b(?:task derailment|off[- ]topic|unrelated (?:task|response)|"
        r"deviat(?:e|ed|ion) from (?:the )?(?:task|objective))\b",
        re.I,
    ),
    "2.4": re.compile(
        r"\b(?:information withholding|withheld|failed? to (?:share|communicate)|"
        r"did not (?:share|communicate))\b",
        re.I,
    ),
    "2.5": re.compile(
        r"\b(?:ignored? (?:the )?(?:other )?agent|ignored? "
        r"(?:the )?suggestion|did not consider (?:the )?input)\b",
        re.I,
    ),
    "2.6": re.compile(
        r"\b(?:action[- ]reasoning mismatch|reasoning[- ]action mismatch|"
        r"(?:reasoning|plan).{0,50}(?:inconsistent|mismatch).{0,30}action)\b",
        re.I | re.S,
    ),
    "3.1": re.compile(
        r"\b(?:premature termination|ended prematurely|task (?:is )?"
        r"(?:not|incompletely) completed|gave up before)\b",
        re.I,
    ),
    "3.2": re.compile(
        r"\b(?:no verification|without verification|not verified|"
        r"incomplete verification|failed? to (?:test|check|verify))\b",
        re.I,
    ),
    "3.3": re.compile(
        r"\b(?:incorrect verification|falsely verified|verification "
        r"(?:was|is) wrong|tests? (?:passed|succeeded).{0,50}(?:error|fail))\b",
        re.I | re.S,
    ),
}


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _clean_actor(value: str) -> str:
    value = value.strip().strip("*").strip()
    value = re.sub(r"\s+", " ", value)
    return value


def _event_id(trace_id: str, sequence: int) -> str:
    return f"{trace_id[:16]}:{sequence:07d}"


def _edge_id(trace_id: str, sequence: int, ordinal: int) -> str:
    return f"{trace_id[:16]}:edge:{sequence:07d}:{ordinal:02d}"


def _speaker_and_edges(
    line: str,
    framework: str,
    trace_id: str,
    sequence: int,
) -> tuple[str | None, str | None, list[dict[str, Any]]]:
    """Extract only structure lexically asserted by one source line."""

    event_id = _event_id(trace_id, sequence)
    edges: list[dict[str, Any]] = []

    match = _META_FROM_TO.search(line)
    if match and framework == "MetaGPT":
        sender = _clean_actor(match.group("sender"))
        receiver = _clean_actor(match.group("receiver"))
        edges.append(
            {
                "edge_id": _edge_id(trace_id, sequence, 0),
                "source_event_id": event_id,
                "sender": sender,
                "receiver": receiver,
                "relation": "explicit_message",
                "observation_status": "observed",
                "complete_endpoints": True,
            }
        )
        return sender, "observed", edges

    match = _CHATDEV_TURN.search(line)
    if match and framework == "ChatDev":
        speaker = _clean_actor(match.group("speaker"))
        left = _clean_actor(match.group("left"))
        right = _clean_actor(match.group("right"))
        receiver = right if speaker == left else left if speaker == right else None
        edges.append(
            {
                "edge_id": _edge_id(trace_id, sequence, 0),
                "source_event_id": event_id,
                "sender": speaker,
                "receiver": receiver,
                "participants": [left, right],
                "relation": "chatdev_phase_turn",
                "phase": _clean_actor(match.group("phase")),
                "observation_status": "observed",
                "complete_endpoints": receiver is not None,
            }
        )
        return speaker, "observed", edges

    match = _APP_MESSAGE_TO.search(line)
    if match and framework == "AppWorld":
        receiver = _clean_actor(match.group("receiver"))
        edges.append(
            {
                "edge_id": _edge_id(trace_id, sequence, 0),
                "source_event_id": event_id,
                "sender": None,
                "receiver": receiver,
                "relation": "explicit_message_target",
                "observation_status": "observed",
                "complete_endpoints": False,
            }
        )
        return None, None, edges

    match = _APP_RESPONSE_FROM.search(line)
    if match and framework == "AppWorld":
        sender = _clean_actor(match.group("sender"))
        edges.append(
            {
                "edge_id": _edge_id(trace_id, sequence, 0),
                "source_event_id": event_id,
                "sender": sender,
                "receiver": None,
                "relation": "explicit_response_source",
                "observation_status": "observed",
                "complete_endpoints": False,
            }
        )
        return sender, "observed", edges

    match = _MAGENTIC_HEADER.search(line)
    if match and framework == "Magentic":
        return _clean_actor(match.group("speaker")), "observed", edges

    match = _HYPER_RESPONSE.search(line)
    if match and framework == "HyperAgent":
        return _clean_actor(match.group("speaker")), "observed", edges

    match = _HYPER_INTERN.search(line)
    if match and framework == "HyperAgent":
        return _clean_actor(match.group("speaker")), "observed", edges

    match = _METAGPT_SPEAKER.search(line)
    if match and framework == "MetaGPT":
        speaker = _clean_actor(match.group("speaker"))
        if speaker not in {"ACTION", "CONTENT", "NEW MESSAGES"}:
            return speaker, "observed", edges

    match = _AG2_NAME.search(line)
    if match and framework == "AG2":
        return _clean_actor(match.group("speaker")), "observed", edges

    match = _AG2_ROLE.search(line)
    if match and framework == "AG2":
        return _clean_actor(match.group("role")), "observed", edges

    if framework == "OpenManus" and _OPENMANUS_THOUGHT.search(line):
        return "Manus", "observed", edges

    return None, None, edges


def canonicalize_mast_trace(
    trace_text: str,
    *,
    framework: str,
    benchmark: str,
    source_trace_key: str,
) -> dict[str, Any]:
    """Create a source-line-lossless canonical projection.

    ``splitlines(keepends=True)`` makes the exact source text reconstructable.
    Speaker scope on non-marker lines and adjacency between distinct speakers
    are reconstructions.  They remain separate from observed endpoint edges.
    """

    if not isinstance(trace_text, str):
        raise ValueError("MAST trace must be a string")
    trace_id = sha256_text(
        stable_json(
            {
                "dataset_revision": DATASET_REVISION,
                "framework": framework,
                "benchmark": benchmark,
                "source_trace_key": source_trace_key,
                "trace_sha256": sha256_text(trace_text),
            }
        )
    )
    source_lines = trace_text.splitlines(keepends=True)
    events: list[dict[str, Any]] = []
    communications: list[dict[str, Any]] = []
    roles: set[str] = set()
    current_speaker: str | None = None
    last_observed_speaker: str | None = None
    last_observed_event_id: str | None = None

    for sequence, line in enumerate(source_lines):
        event_id = _event_id(trace_id, sequence)
        observed_speaker, speaker_status, line_edges = _speaker_and_edges(
            line, framework, trace_id, sequence
        )
        if observed_speaker is not None:
            roles.add(observed_speaker)
            if (
                last_observed_speaker is not None
                and last_observed_speaker != observed_speaker
                and not any(edge["complete_endpoints"] for edge in line_edges)
            ):
                communications.append(
                    {
                        "edge_id": _edge_id(trace_id, sequence, len(line_edges)),
                        "source_event_id": event_id,
                        "parent_event_id": last_observed_event_id,
                        "sender": last_observed_speaker,
                        "receiver": observed_speaker,
                        "relation": "adjacent_speaker_markers",
                        "observation_status": "reconstructed",
                        "complete_endpoints": True,
                    }
                )
            current_speaker = observed_speaker
            last_observed_speaker = observed_speaker
            last_observed_event_id = event_id

        communications.extend(line_edges)
        effective_speaker = observed_speaker or current_speaker or "unknown"
        effective_status = (
            speaker_status
            if observed_speaker is not None
            else "reconstructed"
            if current_speaker is not None
            else "missing"
        )
        events.append(
            {
                "event_id": event_id,
                "sequence": sequence,
                "kind": (
                    "communication.marker"
                    if line_edges or observed_speaker is not None
                    else "raw.trace.line"
                ),
                "observation_status": "observed",
                "source_role": effective_speaker,
                "source_role_status": effective_status,
                "content": line,
                "parent_event_id": events[-1]["event_id"] if events else None,
            }
        )

    reconstructed_text = "".join(event["content"] for event in events)
    if reconstructed_text != trace_text:
        raise AssertionError("source-line projection did not round trip")

    observed_edges = [
        edge for edge in communications if edge["observation_status"] == "observed"
    ]
    reconstructed_edges = [
        edge
        for edge in communications
        if edge["observation_status"] == "reconstructed"
    ]
    return {
        "schema_version": CANONICAL_SCHEMA_VERSION,
        "trace_id": trace_id,
        "source": {
            "dataset_id": DATASET_ID,
            "dataset_revision": DATASET_REVISION,
            "adapter": ADAPTER_VERSION,
            "framework": framework,
            "benchmark": benchmark,
            "source_trace_key_sha256": sha256_text(source_trace_key),
            "source_trace_sha256": sha256_text(trace_text),
        },
        "task": {"task_id": sha256_text(source_trace_key)},
        "events": events,
        "communications": communications,
        "agent_roles": sorted(roles),
        "outcome": {
            "value": None,
            "source": "missing_independent_task_outcome",
        },
        "loss_receipt": {
            "source_event_unit": "physical_line_with_line_ending",
            "source_event_count": len(source_lines),
            "canonical_event_count": len(events),
            "silently_dropped_event_count": 0,
            "source_text_round_trip": True,
            "observed_role_marker_count": sum(
                event["source_role_status"] == "observed" for event in events
            ),
            "reconstructed_role_scope_line_count": sum(
                event["source_role_status"] == "reconstructed" for event in events
            ),
            "unknown_role_line_count": sum(
                event["source_role_status"] == "missing" for event in events
            ),
            "observed_complete_communication_edges": sum(
                edge["complete_endpoints"] for edge in observed_edges
            ),
            "observed_partial_communication_edges": sum(
                not edge["complete_endpoints"] for edge in observed_edges
            ),
            "reconstructed_adjacent_speaker_edges": len(reconstructed_edges),
            "reconstructed_fields": [
                "source_role_on_lines_after_an_observed_speaker_marker",
                "adjacent_speaker_marker_edges",
            ],
            "known_missing_fields": list(KNOWN_MISSING_FIELDS),
        },
    }


def _full_trace_text(row: Mapping[str, Any]) -> str:
    trace = row.get("trace")
    if not isinstance(trace, dict) or not isinstance(trace.get("trajectory"), str):
        raise ValueError("full row trace.trajectory must be a string")
    return trace["trajectory"]


def _full_source_key(row: Mapping[str, Any]) -> str:
    trace = row["trace"]
    return stable_json(
        {
            "mas_name": row.get("mas_name"),
            "benchmark_name": row.get("benchmark_name"),
            "llm_name": row.get("llm_name"),
            "trace_id": row.get("trace_id"),
            "trace_key": trace.get("key"),
            "trace_index": trace.get("index"),
            "trace_sha256": sha256_text(trace["trajectory"]),
        }
    )


def _validate_judge_labels(row: Mapping[str, Any]) -> dict[str, int]:
    annotation = row.get("mast_annotation")
    if not isinstance(annotation, dict) or tuple(annotation) != MAST_CODES:
        raise ValueError("judge annotation must contain the ordered 14-code MAST schema")
    result = {}
    for code in MAST_CODES:
        value = annotation[code]
        if value not in (0, 1, False, True):
            raise ValueError(f"judge label {code} is not binary")
        result[code] = int(bool(value))
    return result


def _human_mode_title(annotation: Mapping[str, Any]) -> tuple[str, str]:
    raw = annotation.get("failure mode")
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("human failure mode description is missing")
    first_line = raw.strip().splitlines()[0].strip()
    match = re.match(r"(?P<code>\d+\.\d+)\s+(?P<title>.+)", first_line)
    if match is None:
        raise ValueError("human failure mode description has no numeric code")
    return match.group("code"), match.group("title").strip()


def _human_votes(annotation: Mapping[str, Any]) -> tuple[int, int, int]:
    return tuple(int(bool(annotation[f"annotator_{index}"])) for index in (1, 2, 3))


def _finalized_human_schema(row: Mapping[str, Any]) -> bool:
    annotations = row.get("annotations")
    if not isinstance(annotations, list):
        return False
    parsed = [_human_mode_title(annotation) for annotation in annotations]
    # The final released four-row round has exactly the 14 final codes in
    # canonical order, but its titles contain harmless editorial variants
    # ("Other Agents'" vs "Other Agent's"; "Reasoning-Action" vs
    # "Action-Reasoning").  Earlier development rounds contain 17 or 18 codes,
    # so code sequence is the stable discriminator and raw titles remain in the
    # schema receipt rather than being rewritten.
    return tuple(code for code, _ in parsed) == MAST_CODES


def _prediction_metrics(
    labels: Sequence[Mapping[str, int]],
    predictions: Sequence[Mapping[str, int]],
) -> dict[str, Any]:
    if len(labels) != len(predictions) or not labels:
        raise ValueError("labels and predictions must be non-empty and aligned")
    per_mode = []
    micro = Counter()
    exact = 0
    for label, prediction in zip(labels, predictions):
        exact += all(int(label[code]) == int(prediction[code]) for code in MAST_CODES)
    for code in MAST_CODES:
        counts = Counter()
        for label, prediction in zip(labels, predictions):
            truth = int(label[code])
            guess = int(prediction[code])
            counts[
                "tp"
                if truth and guess
                else "fp"
                if guess
                else "fn"
                if truth
                else "tn"
            ] += 1
        micro.update(counts)
        precision = counts["tp"] / (counts["tp"] + counts["fp"]) if counts["tp"] + counts["fp"] else 0.0
        recall = counts["tp"] / (counts["tp"] + counts["fn"]) if counts["tp"] + counts["fn"] else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_mode.append(
            {
                "code": code,
                "support": counts["tp"] + counts["fn"],
                "predicted_positive": counts["tp"] + counts["fp"],
                "precision": precision,
                "recall": recall,
                "f1": f1,
            }
        )
    micro_precision = micro["tp"] / (micro["tp"] + micro["fp"]) if micro["tp"] + micro["fp"] else 0.0
    micro_recall = micro["tp"] / (micro["tp"] + micro["fn"]) if micro["tp"] + micro["fn"] else 0.0
    micro_f1 = (
        2 * micro_precision * micro_recall / (micro_precision + micro_recall)
        if micro_precision + micro_recall
        else 0.0
    )
    total = sum(micro.values())
    return {
        "n": len(labels),
        "exact_match_accuracy": exact / len(labels),
        "hamming_accuracy": (micro["tp"] + micro["tn"]) / total,
        "micro_precision": micro_precision,
        "micro_recall": micro_recall,
        "micro_f1": micro_f1,
        "macro_f1": sum(item["f1"] for item in per_mode) / len(per_mode),
        "per_mode": per_mode,
    }


def _surface_prediction(trace_text: str) -> dict[str, int]:
    return {
        code: int(bool(_SURFACE_RULES[code].search(trace_text)))
        for code in MAST_CODES
    }


def _split_is_test(source_key: str) -> bool:
    return int(sha256_text(source_key)[:8], 16) % 5 == 0


def _baseline_study(full_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    train = []
    test = []
    for row in full_rows:
        item = {
            "key": _full_source_key(row),
            "trace": _full_trace_text(row),
            "labels": _validate_judge_labels(row),
            "framework": str(row["mas_name"]),
        }
        (test if _split_is_test(item["key"]) else train).append(item)
    if not train or not test:
        raise ValueError("deterministic split produced an empty partition")
    train_support = Counter()
    for item in train:
        train_support.update(
            code for code in MAST_CODES if item["labels"][code]
        )
    top_three = [
        code
        for code, _ in sorted(
            train_support.items(), key=lambda pair: (-pair[1], pair[0])
        )[:3]
    ]
    labels = [item["labels"] for item in test]
    zero = [{code: 0 for code in MAST_CODES} for _ in test]
    top = [
        {code: int(code in top_three) for code in MAST_CODES}
        for _ in test
    ]
    surface = [_surface_prediction(item["trace"]) for item in test]
    return {
        "evaluation_authority": "released_llm_judge_codes_only",
        "human_labels_used_for_fitting_or_scoring": False,
        "split": {
            "rule": "first_32_bits_sha256(source_key) modulo 5 equals 0",
            "train_n": len(train),
            "test_n": len(test),
            "train_framework_counts": dict(
                sorted(Counter(item["framework"] for item in train).items())
            ),
            "test_framework_counts": dict(
                sorted(Counter(item["framework"] for item in test).items())
            ),
        },
        "always_negative": _prediction_metrics(labels, zero),
        "train_prevalence_top_three": {
            "predicted_codes": top_three,
            "metrics": _prediction_metrics(labels, top),
        },
        "surface_rule_baseline": {
            "rule_revision": "mast-surface-rules-v1",
            "metrics": _prediction_metrics(labels, surface),
        },
        "interpretation_limit": (
            "These are agreement baselines against model-generated codes, not "
            "failure-ground-truth or causal-diagnosis measurements."
        ),
    }


def _structural_study(full_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    totals = Counter()
    by_framework: dict[str, Counter[str]] = defaultdict(Counter)
    role_sets: dict[str, set[str]] = defaultdict(set)
    trace_digests = []
    for row in full_rows:
        framework = str(row["mas_name"])
        canonical = canonicalize_mast_trace(
            _full_trace_text(row),
            framework=framework,
            benchmark=str(row["benchmark_name"]),
            source_trace_key=_full_source_key(row),
        )
        receipt = canonical["loss_receipt"]
        trace_digests.append(canonical["source"]["source_trace_sha256"])
        metrics = {
            "traces": 1,
            "source_lines": receipt["source_event_count"],
            "canonical_events": receipt["canonical_event_count"],
            "silently_dropped_lines": receipt["silently_dropped_event_count"],
            "observed_role_markers": receipt["observed_role_marker_count"],
            "reconstructed_role_scope_lines": receipt[
                "reconstructed_role_scope_line_count"
            ],
            "unknown_role_lines": receipt["unknown_role_line_count"],
            "observed_complete_edges": receipt[
                "observed_complete_communication_edges"
            ],
            "observed_partial_edges": receipt[
                "observed_partial_communication_edges"
            ],
            "reconstructed_adjacent_edges": receipt[
                "reconstructed_adjacent_speaker_edges"
            ],
        }
        totals.update(metrics)
        by_framework[framework].update(metrics)
        role_sets[framework].update(canonical["agent_roles"])

    framework_rows = []
    for framework in sorted(by_framework):
        counts = by_framework[framework]
        framework_rows.append(
            {
                "framework": framework,
                **dict(counts),
                "distinct_observed_roles": len(role_sets[framework]),
                "role_marker_line_coverage": (
                    counts["observed_role_markers"] / counts["source_lines"]
                    if counts["source_lines"]
                    else 0.0
                ),
                "role_available_line_coverage": (
                    (
                        counts["observed_role_markers"]
                        + counts["reconstructed_role_scope_lines"]
                    )
                    / counts["source_lines"]
                    if counts["source_lines"]
                    else 0.0
                ),
            }
        )
    return {
        "adapter": ADAPTER_VERSION,
        "unit_of_preservation": "physical source line including line ending",
        "aggregate": dict(totals),
        "frameworks": framework_rows,
        "source_trace_digest_set_sha256": sha256_text(
            stable_json(sorted(trace_digests))
        ),
        "known_missing_fields": list(KNOWN_MISSING_FIELDS),
        "edge_semantics": {
            "observed_complete": "one source marker names both endpoints",
            "observed_partial": "one source marker names only sender or receiver",
            "reconstructed_adjacent": (
                "two consecutive explicit speaker markers differ; this is a "
                "turn-order reconstruction, not an observed handoff"
            ),
        },
    }


def _judge_study(full_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    overall = Counter()
    by_framework: dict[str, Counter[str]] = defaultdict(Counter)
    framework_counts = Counter()
    benchmark_counts = Counter()
    model_counts = Counter()
    for row in full_rows:
        labels = _validate_judge_labels(row)
        framework = str(row["mas_name"])
        framework_counts[framework] += 1
        benchmark_counts[str(row["benchmark_name"])] += 1
        model_counts[str(row["llm_name"])] += 1
        for code, value in labels.items():
            if value:
                overall[code] += 1
                by_framework[framework][code] += 1
    return {
        "authority": "llm_judge",
        "n": len(full_rows),
        "taxonomy_codes": list(MAST_CODES),
        "positive_counts": {code: overall[code] for code in MAST_CODES},
        "positive_rates": {
            code: overall[code] / len(full_rows) for code in MAST_CODES
        },
        "framework_counts": dict(sorted(framework_counts.items())),
        "benchmark_counts": dict(sorted(benchmark_counts.items())),
        "model_counts": dict(sorted(model_counts.items())),
        "framework_positive_counts": {
            framework: {code: by_framework[framework][code] for code in MAST_CODES}
            for framework in sorted(by_framework)
        },
        "reason_or_evidence_fields_present": False,
        "semantic_warning": (
            "The released rows contain codes only. The pinned definitions file, "
            "judge notebook, finalized human schema, and paper disagree on the "
            "3.2/3.3 verification-mode wording; code identity is preserved "
            "without pretending that the released judge semantics are resolved."
        ),
    }


def _human_study(human_rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    round_counts = Counter()
    schema_counts = Counter()
    schema_details: dict[str, list[dict[str, str]]] = {}
    finalized_rows = []
    development_rows = []
    finalized_votes = Counter()
    finalized_majorities = Counter()
    all_trace_hashes = []
    finalized_trace_hashes = []
    development_trace_hashes = []

    for row in human_rows:
        trace = row.get("trace")
        annotations = row.get("annotations")
        if not isinstance(trace, str) or not isinstance(annotations, list):
            raise ValueError("human row trace/annotations schema is invalid")
        parsed = [_human_mode_title(annotation) for annotation in annotations]
        signature = sha256_text(stable_json(parsed))
        schema_counts[signature] += 1
        schema_details.setdefault(
            signature,
            [{"code": code, "title": title} for code, title in parsed],
        )
        round_counts[str(row.get("round"))] += 1
        trace_hash = sha256_text(trace)
        all_trace_hashes.append(trace_hash)
        if _finalized_human_schema(row):
            finalized_rows.append(row)
            finalized_trace_hashes.append(trace_hash)
            for annotation in annotations:
                code, _ = _human_mode_title(annotation)
                votes = _human_votes(annotation)
                finalized_votes[code] += sum(votes)
                finalized_majorities[code] += sum(votes) >= 2
        else:
            development_rows.append(row)
            development_trace_hashes.append(trace_hash)

    return {
        "authority": "human_expert_votes",
        "n": len(human_rows),
        "round_counts": dict(sorted(round_counts.items())),
        "taxonomy_schema_count": len(schema_counts),
        "taxonomy_schemas": [
            {
                "schema_signature_sha256": signature,
                "row_count": schema_counts[signature],
                "modes": schema_details[signature],
            }
            for signature in sorted(schema_counts)
        ],
        "finalized_14_mode_partition": {
            "n": len(finalized_rows),
            "three_annotator_vote_totals": {
                code: finalized_votes[code] for code in MAST_CODES
            },
            "majority_positive_trace_counts": {
                code: finalized_majorities[code] for code in MAST_CODES
            },
            "trace_digest_set_sha256": sha256_text(
                stable_json(sorted(finalized_trace_hashes))
            ),
        },
        "taxonomy_development_partition": {
            "n": len(development_rows),
            "aggregation_status": "not_aggregated_across_incompatible_taxonomies",
            "trace_digest_set_sha256": sha256_text(
                stable_json(sorted(development_trace_hashes))
            ),
        },
        "trace_digest_set_sha256": sha256_text(stable_json(sorted(all_trace_hashes))),
        "llm_name_field_present": False,
        "label_handling": (
            "Per-annotator votes are retained. Development-round numeric codes "
            "are not remapped to finalized modes."
        ),
    }


def _overlap_study(
    full_rows: Sequence[Mapping[str, Any]],
    human_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    judge_hashes = {sha256_text(_full_trace_text(row)) for row in full_rows}
    final_hashes = {
        sha256_text(str(row["trace"]))
        for row in human_rows
        if _finalized_human_schema(row)
    }
    development_hashes = {
        sha256_text(str(row["trace"]))
        for row in human_rows
        if not _finalized_human_schema(row)
    }
    finalized_overlap = judge_hashes & final_hashes
    development_overlap = judge_hashes & development_hashes
    return {
        "exact_trace_sha256_overlap": {
            "finalized_human_vs_judge": len(finalized_overlap),
            "development_human_vs_judge": len(development_overlap),
        },
        "human_vs_judge_scoring_status": (
            "not_run_no_finalized_taxonomy_trace_overlap"
            if not finalized_overlap
            else "eligible_but_not_run"
        ),
        "development_overlap_exclusion": (
            "Development-round labels use incompatible mode definitions and "
            "numeric identities, so their overlapping traces are not used to "
            "score the judge."
        ),
    }


def _source_file_receipt(path: Path, authority: str) -> dict[str, Any]:
    return {
        "path": path.name,
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "annotation_authority": authority,
    }


def analyze_release(
    full_path: Path,
    human_path: Path,
    definitions_path: Path | None = None,
    judge_notebook_path: Path | None = None,
) -> dict[str, Any]:
    full_rows = json.loads(full_path.read_text(encoding="utf-8"))
    human_rows = json.loads(human_path.read_text(encoding="utf-8"))
    if not isinstance(full_rows, list) or not isinstance(human_rows, list):
        raise ValueError("MAST source files must each contain one JSON array")
    if not full_rows or not human_rows:
        raise ValueError("MAST source arrays must be non-empty")

    source_receipts = [
        _source_file_receipt(full_path, "llm_judge"),
        _source_file_receipt(human_path, "human_expert_votes"),
    ]
    code_file_receipts = []
    for path, role in (
        (definitions_path, "taxonomy_definitions"),
        (judge_notebook_path, "llm_judge_pipeline"),
    ):
        if path is not None:
            code_file_receipts.append(
                {
                    "path": path.name,
                    "role": role,
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )

    result = {
        "schema_version": RESULT_SCHEMA_VERSION,
        "study_design": {
            "dataset_id": DATASET_ID,
            "dataset_revision": DATASET_REVISION,
            "code_repository": CODE_REPOSITORY,
            "code_revision": CODE_REVISION,
            "code_stable_tag": None,
            "declared_dataset_license": DECLARED_DATASET_LICENSE,
            "code_license_file_present_at_revision": False,
            "raw_data_policy": "temporary_storage_only",
            "unit_of_analysis": "released_multi_agent_execution_trace",
            "annotation_authorities_never_merged": True,
            "single_agent_or_enterprise_transfer_claim": False,
        },
        "source_receipts": source_receipts,
        "pinned_code_file_receipts": code_file_receipts,
        "release_conformance": {
            "released_judge_rows": len(full_rows),
            "paper_claimed_judge_rows": 1642,
            "released_human_rows": len(human_rows),
            "paper_claimed_human_rows": 21,
            "judge_row_shortfall_vs_paper": 1642 - len(full_rows),
            "human_row_shortfall_vs_paper": 21 - len(human_rows),
            "huggingface_viewer_status": (
                "schema_cast_failure_when_mixing_human_and_judge_files"
            ),
        },
        "canonical_projection": _structural_study(full_rows),
        "llm_judge_annotations": _judge_study(full_rows),
        "human_annotations": _human_study(human_rows),
        "annotation_overlap": _overlap_study(full_rows, human_rows),
        "naive_baselines": _baseline_study(full_rows),
        "claim_boundary": {
            "supported": [
                "source-line-lossless projection of this released data",
                "conservative extraction coverage for roles and communications",
                "agreement of naive baselines with released model-judge codes",
                "released annotation and taxonomy-version conformance audit",
            ],
            "not_supported": [
                "causal localization of a decisive failing step",
                "independent task success or failure verification",
                "single-agent diagnosis transfer",
                "human skill, productivity, intent, or learning inference",
                "enterprise user, team, or collaboration recommendations",
            ],
        },
    }
    result["result_sha256"] = sha256_text(stable_json(result))
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", type=Path, required=True)
    parser.add_argument("--human", type=Path, required=True)
    parser.add_argument("--definitions", type=Path)
    parser.add_argument("--judge-notebook", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = analyze_release(
        args.full,
        args.human,
        definitions_path=args.definitions,
        judge_notebook_path=args.judge_notebook,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
