#!/usr/bin/env python3
"""Finalize a local-model run without copying trace content into Git.

The local runner keeps one JSONL audit file per attempt in an explicitly
provided internal directory. This finalizer verifies that closed set, derives
source-stratified and stability aggregates, and emits only content-free
statistics plus a hash commitment to the raw audit set.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence

from longitudinal_memory_local_model import (
    ARMS,
    REASONS,
    SCHEMA_VERSION as BASE_SCHEMA_VERSION,
    aggregate_budgets,
    sha256_bytes,
    sha256_file,
    stable_json,
)


FINALIZER_SCHEMA_VERSION = "frankengate.longitudinal-local-final.v1"
EXPECTED_SOURCES = ("fable5_top_level", "trace_commons")
FROZEN_SOURCE_COUNTS = {
    "fable5_top_level": 14,
    "trace_commons": 3,
}
FROZEN_REPEATS = 5
UNIT_ID_RE = re.compile(r"[0-9a-f]{64}")
SAFE_MODEL_ID_RE = re.compile(r"[A-Za-z0-9._/-]{1,200}")
REVISION_RE = re.compile(r"[0-9a-f]{40,64}")
FAILURE_CLASSES = {"LocalModelExperimentError"}
EVALUATION_KEYS = {
    "valid_reference",
    "selected_exact",
    "selected_stale",
    "selected_wrong_context",
    "correct_abstention",
    "exact_evidence_available",
    "abstained",
    "reason",
}
BUDGET_KEYS = {
    "token_budget",
    "candidate_limit",
    "original_candidates",
    "included_candidates",
    "dropped_for_candidate_limit",
    "dropped_for_token_budget",
    "last_item_utf8_tail_truncated",
    "final_pack_tokens",
}


class FinalizationError(RuntimeError):
    """Raised when the raw audit set is incomplete or inconsistent."""


def _exact_bool(value: Any, field: str) -> bool:
    if type(value) is not bool:
        raise FinalizationError(f"{field} must be a JSON boolean")
    return value


def _nonnegative_int(value: Any, field: str) -> int:
    if type(value) is not int or value < 0:
        raise FinalizationError(
            f"{field} must be a nonnegative JSON integer"
        )
    return value


def _safe_model_identity(value: Any, field: str) -> str:
    if not isinstance(value, str) or SAFE_MODEL_ID_RE.fullmatch(value) is None:
        raise FinalizationError(f"{field} is not a safe model identifier")
    return value


def _safe_revision(value: Any) -> str:
    if not isinstance(value, str) or REVISION_RE.fullmatch(value) is None:
        raise FinalizationError("model revision is not a pinned digest")
    return value


def _validate_budget_receipt(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != BUDGET_KEYS:
        raise FinalizationError(
            "budget receipt does not match the frozen schema"
        )
    receipt = dict(value)
    for field in BUDGET_KEYS - {"last_item_utf8_tail_truncated"}:
        receipt[field] = _nonnegative_int(receipt[field], field)
    receipt["last_item_utf8_tail_truncated"] = _exact_bool(
        receipt["last_item_utf8_tail_truncated"],
        "last_item_utf8_tail_truncated",
    )
    if receipt["token_budget"] < 1 or receipt["candidate_limit"] < 1:
        raise FinalizationError(
            "budget and candidate limit must be positive"
        )
    if receipt["final_pack_tokens"] > receipt["token_budget"]:
        raise FinalizationError("evidence pack exceeds its token budget")
    if receipt["included_candidates"] > receipt["candidate_limit"]:
        raise FinalizationError("evidence pack exceeds candidate limit")
    expected_limit_drop = max(
        0,
        receipt["original_candidates"] - receipt["candidate_limit"],
    )
    if receipt["dropped_for_candidate_limit"] != expected_limit_drop:
        raise FinalizationError(
            "candidate-limit accounting is inconsistent"
        )
    available_after_limit = min(
        receipt["original_candidates"],
        receipt["candidate_limit"],
    )
    if (
        receipt["included_candidates"]
        + receipt["dropped_for_token_budget"]
        != available_after_limit
    ):
        raise FinalizationError(
            "token-budget candidate accounting is inconsistent"
        )
    return receipt


def _response_transport(response: Mapping[str, Any] | None) -> str:
    if response is None:
        return "no_response"
    body = response.get("response")
    if not isinstance(body, Mapping):
        return "malformed_response"
    choices = body.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        return "noncanonical_response"
    choice = choices[0]
    if not isinstance(choice, Mapping):
        return "noncanonical_response"
    message = choice.get("message")
    if not isinstance(message, Mapping):
        return "noncanonical_response"
    calls = message.get("tool_calls")
    if not isinstance(calls, list) or len(calls) != 1:
        return "plain_json_or_other"
    call = calls[0]
    function = call.get("function") if isinstance(call, Mapping) else None
    if (
        isinstance(function, Mapping)
        and function.get("name") == "submit_state_decision"
    ):
        return "native_tool"
    return "unexpected_tool"


def _rate(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": round(numerator / denominator, 6)
        if denominator
        else None,
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise FinalizationError(
                    f"invalid JSONL at line {line_number}"
                ) from exc
            if not isinstance(value, dict):
                raise FinalizationError("JSONL event must be an object")
            rows.append(value)
    return rows


def _one_event(
    rows: Sequence[Mapping[str, Any]],
    event_name: str,
    *,
    required: bool,
) -> Mapping[str, Any] | None:
    values = [row for row in rows if row.get("event") == event_name]
    if len(values) > 1:
        raise FinalizationError(
            f"audit attempt has duplicate {event_name} events"
        )
    if required and not values:
        raise FinalizationError(
            f"audit attempt is missing {event_name}"
        )
    return values[0] if values else None


def read_attempt(path: Path) -> dict[str, Any]:
    rows = _read_jsonl(path)
    request = _one_event(rows, "model_request", required=True)
    assert request is not None
    response = _one_event(rows, "model_response", required=False)
    parsed = _one_event(rows, "parsed_decision", required=False)
    failure = _one_event(rows, "model_failure", required=False)
    if (parsed is None) == (failure is None):
        raise FinalizationError(
            "audit attempt must have exactly one terminal event"
        )
    source = str(request.get("source_label"))
    arm = str(request.get("arm"))
    if source not in EXPECTED_SOURCES:
        raise FinalizationError("audit attempt has an unknown source")
    if arm not in ARMS:
        raise FinalizationError("audit attempt has an unknown arm")
    run_index = request.get("run_index")
    if not isinstance(run_index, int) or run_index < 0:
        raise FinalizationError("audit attempt has an invalid run index")
    unit_id = request.get("unit_id")
    if not isinstance(unit_id, str) or UNIT_ID_RE.fullmatch(unit_id) is None:
        raise FinalizationError("audit attempt has an invalid unit ID")
    budget_receipt = _validate_budget_receipt(
        request.get("budget_receipt")
    )
    pack = request.get("pack")
    if not isinstance(pack, Mapping):
        raise FinalizationError("audit request has no model pack")
    if pack.get("arm") != arm:
        raise FinalizationError("model pack arm does not match request arm")
    if pack.get("evidence_budget_receipt") != budget_receipt:
        raise FinalizationError(
            "model pack and request budget receipts differ"
        )
    system_prompt = request.get("system_prompt")
    if not isinstance(system_prompt, str) or not system_prompt:
        raise FinalizationError("audit request has no system prompt")
    intervention_sha256 = sha256_bytes(
        stable_json(
            {
                "system_prompt": system_prompt,
                "pack": pack,
                "budget_receipt": budget_receipt,
            }
        ).encode("utf-8")
    )

    usage: Mapping[str, Any] = {}
    if response is not None:
        response_body = response.get("response")
        if isinstance(response_body, Mapping):
            maybe_usage = response_body.get("usage")
            if isinstance(maybe_usage, Mapping):
                usage = maybe_usage

    result: dict[str, Any] = {
        "unit_id": unit_id,
        "source": source,
        "arm": arm,
        "run_index": run_index,
        "status": "valid" if parsed is not None else "invalid",
        "prompt_tokens": _nonnegative_int(
            usage.get("prompt_tokens", 0),
            "prompt_tokens",
        ),
        "completion_tokens": _nonnegative_int(
            usage.get("completion_tokens", 0),
            "completion_tokens",
        ),
        "raw_sha256": sha256_file(path),
        "budget_receipt": budget_receipt,
        "intervention_sha256": intervention_sha256,
        "response_transport": _response_transport(response),
    }
    if parsed is not None:
        decision = parsed.get("parsed_decision")
        evaluation = parsed.get("evaluation")
        if not isinstance(decision, Mapping) or not isinstance(
            evaluation, Mapping
        ):
            raise FinalizationError(
                "parsed decision is missing its decision or evaluation"
            )
        if set(decision) != {"decision", "evidence_ref", "reason"}:
            raise FinalizationError(
                "parsed decision does not match the frozen schema"
            )
        if set(evaluation) != EVALUATION_KEYS:
            raise FinalizationError(
                "evaluation does not match the frozen schema"
            )
        decision_kind = decision.get("decision")
        evidence_ref = decision.get("evidence_ref")
        reason = decision.get("reason")
        if decision_kind not in {"select", "abstain"}:
            raise FinalizationError("decision uses an unknown enum")
        if reason not in REASONS or evaluation.get("reason") != reason:
            raise FinalizationError(
                "decision and evaluation reason are inconsistent"
            )
        if decision_kind == "select":
            if not isinstance(evidence_ref, str) or not evidence_ref:
                raise FinalizationError(
                    "selected decision has no evidence reference"
                )
        elif evidence_ref is not None:
            raise FinalizationError(
                "abstention has a non-null evidence reference"
            )
        flags = {
            key: _exact_bool(evaluation.get(key), key)
            for key in EVALUATION_KEYS - {"reason"}
        }
        if flags["abstained"] != (decision_kind == "abstain"):
            raise FinalizationError(
                "abstention evaluation contradicts the decision"
            )
        if flags["selected_exact"] and flags["selected_stale"]:
            raise FinalizationError(
                "selection cannot be both exact and stale"
            )
        if (
            flags["selected_exact"]
            or flags["selected_stale"]
            or flags["selected_wrong_context"]
        ) and decision_kind != "select":
            raise FinalizationError(
                "selection evaluation contradicts an abstention"
            )
        if flags["selected_wrong_context"] and not flags["selected_stale"]:
            raise FinalizationError(
                "wrong-context selection must also be stale"
            )
        if flags["correct_abstention"] and (
            decision_kind != "abstain"
            or flags["exact_evidence_available"]
        ):
            raise FinalizationError(
                "correct abstention is internally inconsistent"
            )
        if decision_kind == "abstain" and not flags["valid_reference"]:
            raise FinalizationError(
                "well-formed abstention must have a valid reference state"
            )
        result.update(
            {
                "decision_sha256": sha256_bytes(
                    stable_json(decision).encode("utf-8")
                ),
                "behavior_sha256": sha256_bytes(
                    stable_json(
                        {
                            "decision": decision_kind,
                            "evidence_ref": evidence_ref,
                        }
                    ).encode("utf-8")
                ),
                "decision": decision_kind,
                "reason": reason,
                **flags,
                "exact_decision_correct": (
                    flags["selected_exact"]
                    if flags["exact_evidence_available"]
                    else flags["correct_abstention"]
                ),
            }
        )
    else:
        assert failure is not None
        failure_class = failure.get("failure_class")
        if failure_class not in FAILURE_CLASSES:
            raise FinalizationError(
                "audit attempt uses an unknown failure class"
            )
        result["failure_class"] = failure_class
    return result


def _aggregate_group(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    valid = [row for row in rows if row["status"] == "valid"]
    selected = [
        row for row in valid if row["decision"] == "select"
    ]
    abstained = [
        row for row in valid if row["decision"] == "abstain"
    ]
    reasons = Counter(str(row["reason"]) for row in valid)
    failures = Counter(
        str(row["failure_class"])
        for row in rows
        if row["status"] == "invalid"
    )
    return {
        "attempts": len(rows),
        "valid": _rate(len(valid), len(rows)),
        "exact_decision_correct": _rate(
            sum(row["exact_decision_correct"] for row in valid),
            len(rows),
        ),
        "selected_exact": _rate(
            sum(row["selected_exact"] for row in valid),
            len(rows),
        ),
        "selected_stale": _rate(
            sum(row["selected_stale"] for row in valid),
            len(rows),
        ),
        "selected_wrong_context": _rate(
            sum(row["selected_wrong_context"] for row in valid),
            len(rows),
        ),
        "correct_abstention": _rate(
            sum(row["correct_abstention"] for row in valid),
            len(rows),
        ),
        "exact_evidence_available_post_budget": _rate(
            sum(row["exact_evidence_available"] for row in valid),
            len(rows),
        ),
        "citation_precision_on_selections": _rate(
            sum(row["valid_reference"] for row in selected),
            len(selected),
        ),
        "abstention_correctness_on_abstentions": _rate(
            sum(row["correct_abstention"] for row in abstained),
            len(abstained),
        ),
        "valid_conditional": {
            "exact_decision_correct": _rate(
                sum(row["exact_decision_correct"] for row in valid),
                len(valid),
            ),
            "selected_exact": _rate(
                sum(row["selected_exact"] for row in valid),
                len(valid),
            ),
            "selected_stale": _rate(
                sum(row["selected_stale"] for row in valid),
                len(valid),
            ),
            "selected_wrong_context": _rate(
                sum(
                    row["selected_wrong_context"] for row in valid
                ),
                len(valid),
            ),
            "correct_abstention": _rate(
                sum(row["correct_abstention"] for row in valid),
                len(valid),
            ),
        },
        "decision_reasons": {
            key: reasons[key] for key in sorted(reasons)
        },
        "protocol_failure_classes": {
            key: failures[key] for key in sorted(failures)
        },
        "prompt_tokens": sum(int(row["prompt_tokens"]) for row in rows),
        "completion_tokens": sum(
            int(row["completion_tokens"]) for row in rows
        ),
        "response_transports": dict(
            sorted(
                Counter(
                    str(row["response_transport"]) for row in rows
                ).items()
            )
        ),
    }


def aggregate_source_arms(
    attempts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = (
        defaultdict(list)
    )
    for row in attempts:
        grouped[(str(row["source"]), str(row["arm"]))].append(row)
    return {
        source: {
            arm: _aggregate_group(grouped[(source, arm)])
            for arm in ARMS
        }
        for source in EXPECTED_SOURCES
    }


def aggregate_overall(
    attempts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in attempts:
        grouped[str(row["arm"])].append(row)
    return {
        "arms": {
            arm: _aggregate_group(grouped[arm]) for arm in ARMS
        }
    }


def _validate_base_self_hash(base_result: Mapping[str, Any]) -> None:
    claimed = base_result.get("result_sha256")
    if not isinstance(claimed, str) or UNIT_ID_RE.fullmatch(claimed) is None:
        raise FinalizationError("base result has no valid self-hash")
    unsigned = dict(base_result)
    del unsigned["result_sha256"]
    actual = sha256_bytes(stable_json(unsigned).encode("utf-8"))
    if actual != claimed:
        raise FinalizationError("base result self-hash does not verify")


def _safe_input_receipts(
    value: Any,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise FinalizationError("base result has no input receipts")
    hashes: dict[str, str] = {}
    for field in (
        "experiment_config_sha256",
        "model_manifest_sha256",
        "ranker_config_sha256",
    ):
        digest = value.get(field)
        if not isinstance(digest, str) or UNIT_ID_RE.fullmatch(digest) is None:
            raise FinalizationError(f"{field} is not a SHA-256 digest")
        hashes[field] = digest
    units = _nonnegative_int(value.get("units"), "input units")
    if units != sum(FROZEN_SOURCE_COUNTS.values()):
        raise FinalizationError("input receipt has the wrong unit census")
    counts = value.get("source_counts")
    if not isinstance(counts, Mapping) or dict(counts) != FROZEN_SOURCE_COUNTS:
        raise FinalizationError(
            "input receipt has the wrong frozen source census"
        )
    source_receipts = value.get("source_receipts")
    if not isinstance(source_receipts, list):
        raise FinalizationError("source receipts must be a list")
    safe_sources: list[dict[str, Any]] = []
    seen: set[str] = set()
    for receipt in source_receipts:
        if not isinstance(receipt, Mapping) or set(receipt) != {
            "source_label",
            "manifest_sha256",
            "verified_source_set_sha256",
            "records",
        }:
            raise FinalizationError(
                "source receipt does not match the frozen schema"
            )
        label = receipt.get("source_label")
        if label not in EXPECTED_SOURCES or label in seen:
            raise FinalizationError("source receipt label is invalid")
        seen.add(label)
        safe = {"source_label": label}
        for field in ("manifest_sha256", "verified_source_set_sha256"):
            digest = receipt.get(field)
            if (
                not isinstance(digest, str)
                or UNIT_ID_RE.fullmatch(digest) is None
            ):
                raise FinalizationError(
                    "source receipt contains an invalid digest"
                )
            safe[field] = digest
        safe["records"] = _nonnegative_int(
            receipt.get("records"),
            "source record count",
        )
        safe_sources.append(safe)
    if seen != set(EXPECTED_SOURCES):
        raise FinalizationError("source receipt census is incomplete")
    return {
        **hashes,
        "units": units,
        "source_counts": dict(FROZEN_SOURCE_COUNTS),
        "source_receipts": sorted(
            safe_sources, key=lambda item: str(item["source_label"])
        ),
    }


def _verify_base_aggregate(
    base_aggregate: Any,
    recomputed: Mapping[str, Any],
) -> None:
    if not isinstance(base_aggregate, Mapping):
        raise FinalizationError("base result has no aggregate")
    base_arms = base_aggregate.get("arms")
    if not isinstance(base_arms, Mapping) or set(base_arms) != set(ARMS):
        raise FinalizationError("base aggregate arm census is invalid")
    metric_map = {
        "valid_structured_outputs": "valid",
        "selected_exact": "selected_exact",
        "selected_stale": "selected_stale",
        "selected_wrong_context": "selected_wrong_context",
        "correct_abstention": "correct_abstention",
    }
    for arm in ARMS:
        base_arm = base_arms.get(arm)
        current = recomputed["arms"][arm]
        if not isinstance(base_arm, Mapping):
            raise FinalizationError("base arm aggregate is invalid")
        if base_arm.get("attempts") != current["attempts"]:
            raise FinalizationError("base attempt count contradicts audit set")
        for base_name, current_name in metric_map.items():
            base_rate = base_arm.get(base_name)
            if not isinstance(base_rate, Mapping):
                raise FinalizationError("base rate is malformed")
            if current_name == "valid":
                current_rate = current[current_name]
            else:
                current_rate = current["valid_conditional"][current_name]
            if (
                base_rate.get("numerator") != current_rate["numerator"]
                or base_rate.get("denominator")
                != current_rate["denominator"]
            ):
                raise FinalizationError(
                    "base aggregate contradicts raw audit evaluations"
                )
        for token_field in ("prompt_tokens", "completion_tokens"):
            if base_arm.get(token_field) != current[token_field]:
                raise FinalizationError(
                    "base token totals contradict raw model responses"
                )


def aggregate_stability(
    attempts: Sequence[Mapping[str, Any]],
    independent_runs: int,
) -> dict[str, Any]:
    grouped: dict[tuple[str, str, str], list[Mapping[str, Any]]] = (
        defaultdict(list)
    )
    for row in attempts:
        grouped[
            (
                str(row["source"]),
                str(row["unit_id"]),
                str(row["arm"]),
            )
        ].append(row)

    by_source_arm: dict[
        tuple[str, str], dict[str, int]
    ] = defaultdict(
        lambda: {
            "intended": 0,
            "all_valid": 0,
            "behaviorally_stable": 0,
            "fully_stable": 0,
        }
    )
    for (source, _unit_id, arm), rows in grouped.items():
        counters = by_source_arm[(source, arm)]
        counters["intended"] += 1
        if len(rows) != independent_runs:
            raise FinalizationError(
                "unit-arm has an incomplete repeat census"
            )
        if sorted(int(row["run_index"]) for row in rows) != list(
            range(independent_runs)
        ):
            raise FinalizationError(
                "unit-arm has an invalid run-index census"
            )
        valid = [row for row in rows if row["status"] == "valid"]
        if len(valid) != independent_runs:
            continue
        counters["all_valid"] += 1
        behavior = {
            str(row["behavior_sha256"]) for row in valid
        }
        full_outputs = {
            str(row["decision_sha256"]) for row in valid
        }
        counters["behaviorally_stable"] += len(behavior) == 1
        counters["fully_stable"] += len(full_outputs) == 1

    return {
        source: {
            arm: {
                "strict_valid_and_behaviorally_stable": _rate(
                    by_source_arm[(source, arm)][
                        "behaviorally_stable"
                    ],
                    by_source_arm[(source, arm)]["intended"],
                ),
                "conditional_behavioral": _rate(
                    by_source_arm[(source, arm)][
                        "behaviorally_stable"
                    ],
                    by_source_arm[(source, arm)]["all_valid"],
                ),
                "conditional_full_output": _rate(
                    by_source_arm[(source, arm)]["fully_stable"],
                    by_source_arm[(source, arm)]["all_valid"],
                ),
                "all_repeats_valid": _rate(
                    by_source_arm[(source, arm)]["all_valid"],
                    by_source_arm[(source, arm)]["intended"],
                ),
            }
            for arm in ARMS
        }
        for source in EXPECTED_SOURCES
    }


def aggregate_pairwise_arm_agreement(
    attempts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    grouped: dict[
        tuple[str, str, int], dict[str, Mapping[str, Any]]
    ] = defaultdict(dict)
    for row in attempts:
        grouped[
            (
                str(row["source"]),
                str(row["unit_id"]),
                int(row["run_index"]),
            )
        ][str(row["arm"])] = row
    result: dict[str, Any] = {}
    for left_index, left in enumerate(ARMS):
        for right in ARMS[left_index + 1 :]:
            comparable = [
                (rows[left], rows[right])
                for rows in grouped.values()
                if left in rows
                and right in rows
                and rows[left]["status"] == "valid"
                and rows[right]["status"] == "valid"
            ]
            result[f"{left}__{right}"] = _rate(
                sum(
                    first["behavior_sha256"]
                    == second["behavior_sha256"]
                    for first, second in comparable
                ),
                len(comparable),
            )
    return result


def unique_budgets(
    attempts: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    seen: dict[tuple[str, str], tuple[str, str]] = {}
    receipts: list[dict[str, Any]] = []
    for row in attempts:
        key = (str(row["unit_id"]), str(row["arm"]))
        receipt = row.get("budget_receipt")
        receipt = _validate_budget_receipt(receipt)
        digest = sha256_bytes(stable_json(receipt).encode("utf-8"))
        intervention = str(row.get("intervention_sha256"))
        previous = seen.get(key)
        if previous is not None:
            if previous != (digest, intervention):
                raise FinalizationError(
                    "intervention changed across repeated invocations"
                )
            continue
        seen[key] = (digest, intervention)
        receipts.append({"arm": str(row["arm"]), **receipt})
    return receipts


def raw_set_sha256(attempts: Iterable[Mapping[str, Any]]) -> str:
    receipts = [
        {
            "attempt_key": (
                f"{row['unit_id']}:{row['arm']}:{row['run_index']}"
            ),
            "file_sha256": str(row["raw_sha256"]),
        }
        for row in attempts
    ]
    receipts.sort(key=lambda item: item["attempt_key"])
    return sha256_bytes(
        (
            "frankengate-longitudinal-raw-set-v1\n"
            + stable_json(receipts)
        ).encode("utf-8")
    )


def validate_attempt_census(
    attempts: Sequence[Mapping[str, Any]],
    *,
    independent_runs: int,
    expected_source_counts: Mapping[str, Any],
) -> None:
    if set(expected_source_counts) != set(EXPECTED_SOURCES):
        raise FinalizationError("source-count receipt has unknown keys")
    units_by_source: dict[str, set[str]] = defaultdict(set)
    runs_by_unit_arm: dict[
        tuple[str, str, str], set[int]
    ] = defaultdict(set)
    for row in attempts:
        source = str(row["source"])
        unit_id = str(row["unit_id"])
        arm = str(row["arm"])
        units_by_source[source].add(unit_id)
        runs_by_unit_arm[(source, unit_id, arm)].add(
            int(row["run_index"])
        )
    for source in EXPECTED_SOURCES:
        expected = _nonnegative_int(
            expected_source_counts[source],
            f"{source} source count",
        )
        if len(units_by_source[source]) != expected:
            raise FinalizationError(
                "raw audit source-unit census does not match input receipt"
            )
    expected_runs = set(range(independent_runs))
    for source, unit_ids in units_by_source.items():
        for unit_id in unit_ids:
            for arm in ARMS:
                if runs_by_unit_arm[(source, unit_id, arm)] != expected_runs:
                    raise FinalizationError(
                        "raw audit unit-arm run census is incomplete"
                    )


def finalize(
    *,
    raw_audit_dir: Path,
    base_result_path: Path,
    max_completion_tokens: int,
) -> dict[str, Any]:
    if max_completion_tokens < 1:
        raise FinalizationError(
            "max completion tokens must be positive"
        )
    base_result = json.loads(base_result_path.read_text(encoding="utf-8"))
    if not isinstance(base_result, Mapping):
        raise FinalizationError("base result must be a JSON object")
    if base_result.get("schema_version") != BASE_SCHEMA_VERSION:
        raise FinalizationError("base result schema is not frozen")
    _validate_base_self_hash(base_result)
    input_receipts = _safe_input_receipts(
        base_result.get("input_receipts")
    )
    execution = base_result.get("execution")
    if not isinstance(execution, Mapping):
        raise FinalizationError("base result has no execution object")
    if execution.get("endpoint_scope") != "loopback_only":
        raise FinalizationError("base result is not loopback-only")
    if execution.get("third_party_egress") is not False:
        raise FinalizationError("base result reports third-party egress")
    expected_attempts = _nonnegative_int(
        execution.get("attempts"),
        "execution attempts",
    )
    independent_runs = _nonnegative_int(
        execution.get("independent_runs"),
        "execution repeats",
    )
    if independent_runs != FROZEN_REPEATS:
        raise FinalizationError("repeat census is not frozen")
    expected_units = sum(FROZEN_SOURCE_COUNTS.values())
    if (
        _nonnegative_int(
            execution.get("units_executed"),
            "execution units",
        )
        != expected_units
        or expected_attempts
        != expected_units * len(ARMS) * FROZEN_REPEATS
    ):
        raise FinalizationError("execution census is not frozen")
    if execution.get("arms") != list(ARMS):
        raise FinalizationError(
            "base result arm order/census is not frozen"
        )
    research_root = Path(__file__).resolve().parent
    repository_root = research_root.parents[1]
    raw_root = raw_audit_dir.resolve()
    try:
        raw_root.relative_to(repository_root)
    except ValueError:
        pass
    else:
        raise FinalizationError(
            "raw audit directory must be outside the repository"
        )
    entries = sorted(raw_root.iterdir())
    if any(
        entry.is_symlink()
        or not entry.is_file()
        or entry.suffix != ".jsonl"
        for entry in entries
    ):
        raise FinalizationError(
            "raw audit directory contains an unexpected entry"
        )
    files = entries
    if len(files) != expected_attempts:
        raise FinalizationError(
            "raw audit file count does not match base result"
        )
    attempts = [read_attempt(path) for path in files]
    keys = {
        (row["unit_id"], row["arm"], row["run_index"])
        for row in attempts
    }
    if len(keys) != len(attempts):
        raise FinalizationError("raw audit attempt keys are not unique")
    units = {(row["source"], row["unit_id"]) for row in attempts}
    if len(units) != expected_units:
        raise FinalizationError(
            "raw audit unit census does not match base result"
        )
    validate_attempt_census(
        attempts,
        independent_runs=independent_runs,
        expected_source_counts=FROZEN_SOURCE_COUNTS,
    )
    if any(
        int(row["completion_tokens"]) > max_completion_tokens
        for row in attempts
    ):
        raise FinalizationError(
            "observed completion usage exceeds the asserted cap"
        )
    budgets = unique_budgets(attempts)
    token_budgets = {row["token_budget"] for row in budgets}
    candidate_limits = {row["candidate_limit"] for row in budgets}
    if len(token_budgets) != 1 or len(candidate_limits) != 1:
        raise FinalizationError(
            "evidence intervention limits are not frozen"
        )
    overall = aggregate_overall(attempts)
    _verify_base_aggregate(base_result.get("aggregate"), overall)
    model_id = _safe_model_identity(
        execution.get("model_id"),
        "model_id",
    )
    model_revision = _safe_revision(execution.get("model_revision"))
    request_model_id = _safe_model_identity(
        execution.get("request_model_id"),
        "request_model_id",
    )
    native_tool_declared = _exact_bool(
        execution.get("native_decision_tool_required"),
        "native_decision_tool_required",
    )

    final: dict[str, Any] = {
        "schema_version": FINALIZER_SCHEMA_VERSION,
        "base_result_sha256": sha256_file(base_result_path),
        "code_receipts": {
            "runner_source_at_finalization_only_sha256": sha256_file(
                research_root / "longitudinal_memory_local_model.py"
            ),
            "runner_source_at_execution_attested": False,
            "tokenizer_worker_sha256": sha256_file(
                research_root / "local_tokenizer_worker.py"
            ),
            "finalizer_sha256": sha256_file(Path(__file__).resolve()),
        },
        "input_receipts": input_receipts,
        "execution": {
            "endpoint_scope": "loopback_only",
            "model_id_declared_by_manifest": model_id,
            "model_revision_declared_by_manifest": model_revision,
            "request_model_id_declared_by_manifest": request_model_id,
            "runtime_identity_mechanically_attested": False,
            "arms": list(ARMS),
            "units_executed": expected_units,
            "attempts": expected_attempts,
            "repeated_invocations_per_unit_arm": independent_runs,
            "max_completion_tokens": max_completion_tokens,
            "completion_cap_bound_in_request_receipt": False,
            "evidence_pack_token_budget": next(iter(token_budgets)),
            "candidate_limit": next(iter(candidate_limits)),
            "runner_declared_native_decision_tool_required": (
                native_tool_declared
            ),
            "native_decision_tool_strictly_enforced": False,
            "raw_audit_set_sha256": raw_set_sha256(attempts),
            "raw_audit_files_verified": len(attempts),
            "source_unit_counts": {
                source: len(
                    {
                        row["unit_id"]
                        for row in attempts
                        if row["source"] == source
                    }
                )
                for source in EXPECTED_SOURCES
            },
        },
        "overall": overall,
        "source_stratified": aggregate_source_arms(attempts),
        "source_stratified_five_run_stability": aggregate_stability(
            attempts,
            independent_runs,
        ),
        "paired_arm_behavior_agreement": (
            aggregate_pairwise_arm_agreement(attempts)
        ),
        "evidence_budget": aggregate_budgets(budgets),
        "claim_boundary": {
            "exploratory_within_corpus": True,
            "paper_grade_confirmatory_result": False,
            "model_is_pilot_only": True,
            "human_review_completed": False,
            "enterprise_generalization_allowed": False,
            "automatic_memory_promotion_allowed": False,
            "later_observation_is_hindsight_score_not_online_ground_truth": True,
            "evaluator_labels_rederived_by_finalizer": False,
            "dream_mechanism_tested": False,
            "arm_labels_hidden_from_model": False,
            "latest_only_context_free": False,
            "bitemporal_semantics_complete": False,
            "frozen_diversity_gate_passed": False,
        },
        "privacy_boundary": {
            "authorized_internal_full_fidelity_used": True,
            "credential_only_input_gate_verified": False,
            "third_party_egress": False,
            "raw_audit_committed": False,
            "aggregate_contains_trace_content": False,
            "aggregate_contains_unit_identifiers": False,
            "aggregate_contains_raw_paths": False,
        },
    }
    final["result_sha256"] = sha256_bytes(
        stable_json(final).encode("utf-8")
    )
    return final


def _percent(rate: Mapping[str, Any]) -> str:
    value = rate.get("rate")
    return "n/a" if value is None else f"{float(value) * 100:.1f}%"


def render_summary(result: Mapping[str, Any]) -> str:
    execution = result["execution"]
    overall = result["overall"]
    source_stratified = result["source_stratified"]
    stability = result["source_stratified_five_run_stability"]
    pairwise = result["paired_arm_behavior_agreement"]
    budgets = result["evidence_budget"]
    lines = [
        "# Longitudinal memory local-model replication",
        "",
        "Status: completed exploratory within-corpus replication",
        "Date: 2026-07-30",
        "",
        "## Frozen execution",
        "",
        f"- Manifest-declared model: "
        f"`{execution['model_id_declared_by_manifest']}` at revision "
        f"`{execution['model_revision_declared_by_manifest']}`. The active "
        "server and weight/runtime hashes were not mechanically attested.",
        f"- Census: {execution['units_executed']} units, "
        f"{execution['attempts']} attempts, "
        f"{execution['repeated_invocations_per_unit_arm']} repeated "
        "invocations per unit-arm, "
        f"with a {execution['max_completion_tokens']}-token completion cap.",
        "- Sources: "
        + ", ".join(
            f"`{source}` {count}"
            for source, count in sorted(
                execution["source_unit_counts"].items()
            )
        )
        + ".",
        f"- Internal raw audit files verified: "
        f"{execution['raw_audit_files_verified']}; set commitment "
        f"`{execution['raw_audit_set_sha256']}`.",
        "- The model endpoint was loopback-only. No trace content or PII "
        "crossed a third-party boundary, and no raw trace/model payload is "
        "committed. This pilot did not mechanically verify the new "
        "credential-only input gate, so its raw audit remains restricted.",
        "",
        "## Overall results",
        "",
        "| Arm | Valid | Exact decision | Exact selection | Stale selection | "
        "Wrong context | Correct abstention |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for arm in ARMS:
        row = overall["arms"][arm]
        lines.append(
            f"| `{arm}` | {_percent(row['valid'])} | "
            f"{_percent(row['exact_decision_correct'])} | "
            f"{_percent(row['selected_exact'])} | "
            f"{_percent(row['selected_stale'])} | "
            f"{_percent(row['selected_wrong_context'])} | "
            f"{_percent(row['correct_abstention'])} |"
        )
    lines.extend(
        [
            "",
            "“Exact selection” is hindsight scoring against a later observed "
            "state, not proof that the selected evidence was online ground "
            "truth. “Correct abstention” is primarily interpretable for arms "
            "where exact evidence was absent.",
            "",
            "## Pilot finding",
            "",
            "- The four evidence-bearing arms had the same aggregate "
            "scores. Their paired behavioral agreement was: "
            + ", ".join(
                f"`{pair}` {_percent(pairwise[pair])}"
                for pair in (
                    "verbatim__latest_only",
                    "verbatim__contextual_bitemporal",
                    "verbatim__proposal_only_dream",
                )
            )
            + ". This pilot therefore does not demonstrate a benefit from "
            "context, bitemporal reasoning, or dreaming.",
            "- `no_memory` reached 100% exact-decision correctness only "
            "because it had no evidence and always abstained correctly under "
            "the pilot evaluator. That is a scoring/control artifact, not "
            "evidence that no memory is superior.",
            "- Exact-decision correctness for evidence-bearing arms was "
            "78.6% on Fable but 33.3% on Trace Commons. With only three "
            "Trace Commons units, this is a source-stratum warning rather "
            "than a generalizable effect.",
            "",
            "## Source-stratified results",
            "",
        ]
    )
    for source in EXPECTED_SOURCES:
        lines.extend(
            [
                f"### `{source}`",
                "",
                "| Arm | Attempts | Valid | Exact decision | Exact | Stale | "
                "Wrong context | Correct abstention | Strict repeatability |",
                "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for arm in ARMS:
            row = source_stratified[source][arm]
            lines.append(
                f"| `{arm}` | {row['attempts']} | "
                f"{_percent(row['valid'])} | "
                f"{_percent(row['exact_decision_correct'])} | "
                f"{_percent(row['selected_exact'])} | "
                f"{_percent(row['selected_stale'])} | "
                f"{_percent(row['selected_wrong_context'])} | "
                f"{_percent(row['correct_abstention'])} | "
                f"{_percent(stability[source][arm]['strict_valid_and_behaviorally_stable'])} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Evidence-budget pressure",
            "",
            "| Arm | Packs | Token budget | Min/max pack tokens | "
            "Truncated tails | Candidate-limit drops | Token-budget drops |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for arm in ARMS:
        row = budgets[arm]
        lines.append(
            f"| `{arm}` | {row['packs']} | {row['token_budget']} | "
            f"{row['minimum_pack_tokens']} / "
            f"{row['maximum_pack_tokens']} | "
            f"{row['last_item_truncated']} | "
            f"{row['items_dropped_for_candidate_limit']} | "
            f"{row['items_dropped_for_token_budget']} |"
        )

    lines.extend(
        [
            "",
            "Budget drops are part of the intervention, not harmless "
            "preprocessing: an arm can fail because the relevant state was "
            "ranked below the five-candidate or 2,048-token boundary. The "
            "full audit retains each budget receipt for internal review.",
            "",
            "## Interpretation boundary",
            "",
            "- This is an exploratory state-evidence selection study over "
            "two source strata, not an employee-skill assessment.",
            "- It does not establish causal memory benefit, enterprise "
            "generalization, production safety, or permission for automatic "
            "memory promotion.",
            "- The native decision-tool adapter was introduced only after "
            "plain-JSON pilot failures and is reported as a protocol "
            "amendment rather than a preregistered confirmatory result. The "
            "runner still accepted plain JSON, so native tool use was not "
            "strictly enforced.",
            "- `proposal_only_dream` did not implement proposal generation "
            "or consolidation and must be read only as a labeled contextual "
            "control. Arm labels were model-visible; `latest_only` retained "
            "context metadata; and `contextual_bitemporal` lacked complete "
            "bitemporal semantics.",
            "- The finalizer independently rebuilt aggregate counts from "
            "the audit attempts and checked them against the base result, "
            "but it did not rederive hindsight evaluator labels from the "
            "frozen source corpus.",
            "- The completion cap is operator asserted and bounded by "
            "observed usage, not bound into each request receipt.",
            "- The five invocations are a deterministic repeatability check, "
            "not five statistically independent samples; the local runtime "
            "used temperature zero and does not promise seed support.",
            "- Authorized internal full-fidelity analysis is intentional. "
            "Any future third-party, public, cross-scope, or lower-privilege "
            "copy requires its own transform and disclosure receipt.",
            "",
            f"Aggregate result commitment: `{result['result_sha256']}`.",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-audit-dir", type=Path, required=True)
    parser.add_argument("--base-result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path)
    parser.add_argument(
        "--max-completion-tokens",
        type=int,
        required=True,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = finalize(
        raw_audit_dir=args.raw_audit_dir,
        base_result_path=args.base_result,
        max_completion_tokens=args.max_completion_tokens,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if args.summary is not None:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(
            render_summary(result),
            encoding="utf-8",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
