#!/usr/bin/env python3
"""Loss-aware adapter and repeated-pass audit for CMU Agent Trajectories.

Raw CMU records are gated and license-quarantined. This module is deliberately
dependency-free so its conformance contract can be tested before access is
granted. It writes aggregate metrics only and never serializes messages, tool
arguments/results, task identifiers, trace identifiers, or per-attempt rows.

Independent passes start from scratch. A failure-to-success contrast is useful
outcome evidence, but it is not evidence that a user or model learned between
passes.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any, Iterable, Iterator


CANONICAL_VERSION = "canonical-trajectory-v1"
DATASET_ID = "cx-cmu/agent_trajectories"
DATASET_REVISION = "88e2af82c116a9a57f29be6f21b9924da081c2bd"
ADAPTER = "cmu_agent_trajectories_v1"
RESULT_VERSION = "cmu-repeated-pass-audit-v1"

ERROR_RE = re.compile(
    r"\b(error|exception|failed|failure|invalid|denied|not found|timeout)\b",
    re.IGNORECASE,
)


class CMUAdapterError(ValueError):
    """Raised when a source row cannot be represented without guessing."""


def stable_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def sha256_json(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def _required_text(row: dict[str, Any], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, (str, int)) or str(value) == "":
        raise CMUAdapterError(f"CMU row requires non-empty {key}")
    return str(value)


def repeated_pass_group_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    """Return the atomic grouping unit that must never cross a data split."""

    return (
        _required_text(row, "benchmark"),
        _required_text(row, "domain"),
        _required_text(row, "task_id"),
        _required_text(row, "source_model"),
    )


def _message_content(message: dict[str, Any]) -> str | None:
    content = message.get("content")
    if content is None:
        return None
    if isinstance(content, str):
        return content
    return stable_json(content)


def _tool_function(call: dict[str, Any]) -> tuple[str | None, Any]:
    function = call.get("function")
    if not isinstance(function, dict):
        return None, None
    name = function.get("name")
    return (str(name) if name is not None else None, function.get("arguments"))


def canonicalize_cmu(row: dict[str, Any]) -> dict[str, Any]:
    """Convert one CMU row into the Frankengate research canonical form."""

    source_id = _required_text(row, "id")
    benchmark, domain, task_id, source_model = repeated_pass_group_key(row)
    pass_number = row.get("pass")
    if not isinstance(pass_number, int) or not 1 <= pass_number <= 4:
        raise CMUAdapterError("CMU row pass must be an integer from 1 through 4")
    messages = row.get("messages")
    if not isinstance(messages, list) or not messages:
        raise CMUAdapterError("CMU row messages must be a non-empty array")
    if not all(isinstance(message, dict) for message in messages):
        raise CMUAdapterError("every CMU message must be an object")

    trace_material = {
        "id": source_id,
        "benchmark": benchmark,
        "domain": domain,
        "task_id": task_id,
        "source_model": source_model,
        "pass": pass_number,
        "messages": messages,
        "reward": row.get("reward"),
        "eval_details": row.get("eval_details"),
        "trace_meta": row.get("trace_meta"),
        "cleaning_info": row.get("cleaning_info"),
    }
    trace_id = sha256_json(trace_material)
    events: list[dict[str, Any]] = []
    proposal_by_call_id: dict[str, str] = {}
    source_tool_calls = 0
    source_tool_results = 0
    duplicate_call_ids: set[str] = set()

    def add_event(
        *,
        kind: str,
        source_role: str,
        content: str | None,
        parent_event_id: str | None,
        **extra: Any,
    ) -> str:
        sequence = len(events)
        event_id = f"{trace_id[:16]}:{sequence:06d}"
        event = {
            "event_id": event_id,
            "sequence": sequence,
            "kind": kind,
            "observation_status": "observed",
            "source_role": source_role,
            "content": content,
            "parent_event_id": parent_event_id,
        }
        event.update(extra)
        events.append(event)
        return event_id

    previous_event_id: str | None = None
    for source_index, message in enumerate(messages):
        role = str(message.get("role") or "unknown")
        content = _message_content(message)
        message_kind = {
            "system": "system_instruction",
            "user": "task_input" if source_index == 0 else "user_message",
            "assistant": "agent_message",
            "tool": "tool_result",
        }.get(role, "unknown_message")

        if role == "tool":
            source_tool_results += 1
            call_id_value = message.get("tool_call_id")
            call_id = str(call_id_value) if call_id_value is not None else None
            proposal_event_id = proposal_by_call_id.get(call_id or "")
            previous_event_id = add_event(
                kind=message_kind,
                source_role=role,
                content=content,
                parent_event_id=proposal_event_id or previous_event_id,
                tool_call_id=call_id,
                correlated_tool_proposal_event_id=proposal_event_id,
                correlation_status=(
                    "unique_observed" if proposal_event_id else "missing_proposal"
                ),
            )
            continue

        message_event_id = add_event(
            kind=message_kind,
            source_role=role,
            content=content,
            parent_event_id=previous_event_id,
            source_message_index=source_index,
        )
        previous_event_id = message_event_id

        tool_calls = message.get("tool_calls")
        if tool_calls is None:
            continue
        if role != "assistant" or not isinstance(tool_calls, list):
            raise CMUAdapterError(
                "tool_calls must be an array on an assistant message"
            )
        for call_index, call in enumerate(tool_calls):
            if not isinstance(call, dict):
                raise CMUAdapterError("every tool call must be an object")
            source_tool_calls += 1
            call_id_value = call.get("id")
            call_id = str(call_id_value) if call_id_value is not None else None
            if call_id is None or call_id in proposal_by_call_id:
                if call_id is not None:
                    duplicate_call_ids.add(call_id)
                correlation_status = "ambiguous_source_call_id"
            else:
                correlation_status = "unique_observed"
            function_name, arguments = _tool_function(call)
            proposal_event_id = add_event(
                kind="tool.proposed",
                source_role=role,
                content=None,
                parent_event_id=message_event_id,
                tool_call_id=call_id,
                function_name=function_name,
                arguments=arguments,
                source_message_index=source_index,
                source_tool_call_index=call_index,
                correlation_status=correlation_status,
            )
            if call_id is not None and call_id not in proposal_by_call_id:
                proposal_by_call_id[call_id] = proposal_event_id
            previous_event_id = proposal_event_id

    reward = row.get("reward")
    if not isinstance(reward, (int, float)) or isinstance(reward, bool):
        raise CMUAdapterError("CMU row reward must be numeric")

    known_missing = [
        "authorization_decisions",
        "authorization_epoch",
        "subject_and_tenant_identity",
        "exact_runtime_visible_tool_menu",
        "intervention_exposure",
    ]
    if duplicate_call_ids:
        known_missing.append("unique_tool_call_correlation")
    if any(
        event.get("kind") == "tool_result"
        and event.get("correlation_status") == "missing_proposal"
        for event in events
    ):
        known_missing.append("tool_result_proposal_correlation")

    return {
        "schema_version": CANONICAL_VERSION,
        "trace_id": trace_id,
        "source": {
            "dataset_id": DATASET_ID,
            "dataset_revision": DATASET_REVISION,
            "adapter": ADAPTER,
            "source_record_id_digest": hashlib.sha256(
                source_id.encode("utf-8")
            ).hexdigest(),
            "model_name": source_model,
        },
        "task": {
            "task_id": hashlib.sha256(
                "\x1f".join((benchmark, domain, task_id)).encode("utf-8")
            ).hexdigest(),
            "benchmark": benchmark,
            "domain": domain,
            "repeated_pass_group_digest": hashlib.sha256(
                "\x1f".join(
                    (benchmark, domain, task_id, source_model)
                ).encode("utf-8")
            ).hexdigest(),
            "pass": pass_number,
        },
        "events": events,
        "outcome": {
            "value": float(reward),
            "source": "dataset_benchmark_evaluation",
            "evidence_status": "publisher_supplied",
            "binary_success": bool(reward > 0),
        },
        "attachments": {
            "eval_details_present": row.get("eval_details") is not None,
            "trace_meta_present": row.get("trace_meta") is not None,
            "cleaning_info_present": row.get("cleaning_info") is not None,
            "num_passes_available": row.get("num_passes_available"),
            "has_all_4_passes": row.get("has_all_4_passes"),
        },
        "loss_receipt": {
            "source_event_count": len(messages),
            "canonical_event_count": len(events),
            "silently_dropped_event_count": 0,
            "reconstructed_fields": [],
            "known_missing_fields": sorted(set(known_missing)),
            "source_messages_preserved": len(messages),
            "source_tool_calls_observed": source_tool_calls,
            "source_tool_results_observed": source_tool_results,
            "selection_warning": (
                "publisher removed 1,445 incomplete/crashed/truncated "
                "trajectories before this release"
            ),
        },
    }


def _looks_like_error(content: str | None) -> bool:
    if not content:
        return False
    try:
        parsed = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        parsed = None
    if isinstance(parsed, dict):
        for key in ("error", "exception"):
            if parsed.get(key):
                return True
        status = str(parsed.get("status") or "").lower()
        if status in {"error", "failed", "failure", "denied"}:
            return True
        success = parsed.get("success")
        if success is False:
            return True
    return bool(ERROR_RE.search(content))


def deterministic_attempt_features(
    canonical: dict[str, Any],
) -> dict[str, float]:
    """Compute outcome-blind structural features for one independent pass."""

    events = canonical["events"]
    tool_names = [
        str(event.get("function_name") or "")
        for event in events
        if event["kind"] == "tool.proposed"
    ]
    counts = collections.Counter(tool_names)
    repeated_tool_calls = sum(
        count - 1 for name, count in counts.items() if name and count > 1
    )
    tool_results = [
        event for event in events if event["kind"] == "tool_result"
    ]
    explicit_error_results = sum(
        1 for event in tool_results if _looks_like_error(event.get("content"))
    )
    unlinked_results = sum(
        1
        for event in tool_results
        if event.get("correlation_status") != "unique_observed"
    )
    friction_score = (
        2.0 * explicit_error_results
        + 0.5 * repeated_tool_calls
        + 1.0 * unlinked_results
    )
    return {
        "message_event_count": float(
            sum(
                event["kind"]
                in {
                    "system_instruction",
                    "task_input",
                    "user_message",
                    "agent_message",
                    "unknown_message",
                }
                for event in events
            )
        ),
        "tool_call_count": float(len(tool_names)),
        "tool_result_count": float(len(tool_results)),
        "explicit_error_result_count": float(explicit_error_results),
        "repeated_tool_call_count": float(repeated_tool_calls),
        "unlinked_tool_result_count": float(unlinked_results),
        "friction_score": float(friction_score),
    }


def iter_jsonl(paths: Iterable[Path]) -> Iterator[dict[str, Any]]:
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise CMUAdapterError(
                        f"{path.name}:{line_number}: invalid JSON"
                    ) from exc
                if not isinstance(value, dict):
                    raise CMUAdapterError(
                        f"{path.name}:{line_number}: row must be an object"
                    )
                yield value


def _safe_ratio(numerator: float, denominator: float) -> float | None:
    return numerator / denominator if denominator else None


def analyze_rows(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Produce content-free aggregate readiness and repeated-pass metrics."""

    groups: dict[
        tuple[str, str, str, str], list[tuple[dict[str, Any], dict[str, float]]]
    ] = collections.defaultdict(list)
    benchmark_counts: collections.Counter[str] = collections.Counter()
    total_events = 0
    total_tool_calls = 0
    total_tool_results = 0
    total_explicit_errors = 0
    source_rows = 0

    for row in rows:
        canonical = canonicalize_cmu(row)
        features = deterministic_attempt_features(canonical)
        key = repeated_pass_group_key(row)
        groups[key].append((canonical, features))
        benchmark_counts[key[0]] += 1
        source_rows += 1
        total_events += len(canonical["events"])
        total_tool_calls += int(features["tool_call_count"])
        total_tool_results += int(features["tool_result_count"])
        total_explicit_errors += int(features["explicit_error_result_count"])

    mixed_groups = 0
    complete_four_pass_groups = 0
    friction_selected_successes = 0
    longest_selected_successes = 0
    eligible_selection_groups = 0
    ordered_failure_success_pairs = 0

    for attempts in groups.values():
        passes = {attempt[0]["task"]["pass"] for attempt in attempts}
        if len(passes) == 4:
            complete_four_pass_groups += 1
        success_values = [
            bool(attempt[0]["outcome"]["binary_success"])
            for attempt in attempts
        ]
        if not any(success_values) or all(success_values):
            continue
        mixed_groups += 1
        eligible_selection_groups += 1
        by_pass = sorted(attempts, key=lambda item: item[0]["task"]["pass"])
        for left_index, (left, _) in enumerate(by_pass):
            if left["outcome"]["binary_success"]:
                continue
            ordered_failure_success_pairs += sum(
                bool(right["outcome"]["binary_success"])
                for right, _ in by_pass[left_index + 1 :]
            )
        minimum_friction = min(
            attempts,
            key=lambda item: (
                item[1]["friction_score"],
                item[0]["task"]["pass"],
            ),
        )
        longest = max(
            attempts,
            key=lambda item: (
                item[1]["message_event_count"],
                -item[0]["task"]["pass"],
            ),
        )
        friction_selected_successes += bool(
            minimum_friction[0]["outcome"]["binary_success"]
        )
        longest_selected_successes += bool(
            longest[0]["outcome"]["binary_success"]
        )

    return {
        "schema_version": RESULT_VERSION,
        "dataset": {
            "id": DATASET_ID,
            "revision": DATASET_REVISION,
            "adapter": ADAPTER,
            "license": "NOASSERTION",
            "raw_data_committed": False,
        },
        "corpus": {
            "source_rows": source_rows,
            "canonical_events": total_events,
            "tool_calls": total_tool_calls,
            "tool_results": total_tool_results,
            "explicit_error_results": total_explicit_errors,
            "benchmark_attempt_counts": dict(sorted(benchmark_counts.items())),
            "repeated_pass_groups": len(groups),
            "complete_four_pass_groups": complete_four_pass_groups,
            "mixed_outcome_groups": mixed_groups,
        },
        "observational_selection": {
            "eligible_mixed_outcome_groups": eligible_selection_groups,
            "minimum_friction_selected_successes": friction_selected_successes,
            "minimum_friction_success_rate": _safe_ratio(
                friction_selected_successes,
                eligible_selection_groups,
            ),
            "longest_trace_selected_successes": longest_selected_successes,
            "longest_trace_success_rate": _safe_ratio(
                longest_selected_successes,
                eligible_selection_groups,
            ),
            "ordered_failure_before_success_pairs": (
                ordered_failure_success_pairs
            ),
        },
        "validity": {
            "raw_access_required_for_empirical_result": True,
            "independent_passes_are_not_learning": True,
            "outcomes_are_publisher_supplied": True,
            "removed_failure_selection_model_required": True,
            "enterprise_or_person_claim_supported": False,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the private CMU repeated-pass aggregate audit."
    )
    parser.add_argument(
        "--input",
        type=Path,
        action="append",
        required=True,
        help="Private JSONL input path; repeat for each benchmark shard.",
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = analyze_rows(iter_jsonl(args.input))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
