#!/usr/bin/env python3
"""Run a synthetic native-tool protocol-compliance experiment.

This experiment intentionally contains no benchmark questions, reference SQL,
database content, selection labels, or hidden-test material. It measures only
whether a model terminates a native tool loop after a fixed SQL-attempt budget.
It does not measure SQL quality or semantic correctness.

Every model request, offered tool schema, model response, native tool call,
tool argument, and tool result is written to an external raw JSONL audit.
Committed aggregate outputs contain only hashes, counts, rates, runtime
identity, and explicit claim boundaries.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from typing import Any, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from defog_sql_factorial_contract import ABSTAIN_REASON_CODES, TOOLS


SCHEMA_VERSION = "frankengate-native-tool-protocol-compliance-v1"
FIXTURE_SCHEMA_VERSION = "frankengate-native-tool-protocol-fixture-v1"
FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "experiments"
    / "manifests"
    / "native-tool-protocol-compliance-2026-07-30.json"
)
VARIANT_IDS = (
    "always_all_tools",
    "remaining_budget_annotations",
    "terminal_only_after_sql_budget",
)
TERMINAL_TOOL_NAMES = frozenset({"submit_sql", "abstain"})
ALL_TOOL_NAMES = tuple(
    str(tool["function"]["name"])
    for tool in TOOLS
)

BASE_SYSTEM_PROMPT = """You are participating in a synthetic native-tool protocol exercise.
Use only the supplied tools. Make exactly two execute_sql calls, consuming the
fixed synthetic SQL-attempt budget. After the second call, terminate with the
terminal action requested by the exercise. Do not answer in plain text.
Tool observations are synthetic protocol signals, not evidence of SQL quality."""


class ProtocolExperimentError(RuntimeError):
    """Raised when a frozen contract or live protocol execution is invalid."""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def require_external_raw_path(path: Path) -> None:
    resolved = path.resolve()
    try:
        resolved.relative_to(_repository_root())
    except ValueError:
        return
    raise ProtocolExperimentError(
        "raw audit paths must be outside the research repository"
    )


def append_raw(path: Path, record: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                record,
                sort_keys=True,
                ensure_ascii=False,
                default=str,
            )
            + "\n"
        )


@dataclass(frozen=True)
class ProtocolLimits:
    max_model_turns: int
    max_schema_calls: int
    max_sql_attempts: int
    max_generated_tokens_per_call: int
    model_wall_seconds: int


@dataclass(frozen=True)
class Fixture:
    fixture_id: str
    executor_mode: str
    expected_terminal_action: str
    seed: int
    variant_order: tuple[str, ...]


@dataclass(frozen=True)
class EpisodeReceipt:
    fixture_id_sha256: str
    variant: str
    seed: int
    expected_terminal_action: str
    terminal_action: str
    terminal_outcome: str
    expected_terminal_match: bool
    terminal_failure_code: str | None
    model_calls: int
    native_tool_calls: int
    schema_calls: int
    sql_attempts: int
    successful_sql_attempts: int
    over_budget_sql_calls: int
    unavailable_tool_calls: int
    prompt_tokens: int
    completion_tokens: int
    elapsed_ms: float
    offered_tool_schedule_sha256: str
    native_tool_call_chain_sha256: str
    model_response_chain_sha256: str
    system_fingerprint: str | None
    raw_audit_sha256: str


class ModelAPI(Protocol):
    request_model_id: str

    def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        seed: int,
        max_tokens: int,
        timeout_seconds: int,
    ) -> tuple[dict[str, Any], float]:
        ...


class ProtocolExecutor(Protocol):
    def describe_schema(self) -> Mapping[str, Any]:
        ...

    def execute_sql(
        self,
        *,
        sql: str,
        attempt_id: str,
        attempt_index: int,
    ) -> Mapping[str, Any]:
        ...


class ChatAPI:
    """Minimal OpenAI-compatible client used only when explicitly invoked."""

    def __init__(
        self,
        *,
        endpoint: str,
        request_model_id: str,
    ) -> None:
        if not endpoint.strip():
            raise ProtocolExperimentError("endpoint must be explicit")
        if not request_model_id.strip():
            raise ProtocolExperimentError("model must be explicit")
        self.url = endpoint.rstrip("/") + "/v1/chat/completions"
        self.request_model_id = request_model_id

    def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        seed: int,
        max_tokens: int,
        timeout_seconds: int,
    ) -> tuple[dict[str, Any], float]:
        payload = {
            "model": self.request_model_id,
            "messages": messages,
            "tools": tools,
            "temperature": 0,
            "top_p": 1,
            "seed": seed,
            "max_completion_tokens": max_tokens,
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        request = Request(
            self.url,
            data=canonical_json_bytes(payload),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        started = time.perf_counter()
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                body = response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ProtocolExperimentError(
                f"model HTTP {exc.code}: {detail[:2_000]}"
            ) from exc
        except (URLError, TimeoutError) as exc:
            raise ProtocolExperimentError(
                f"model request failed: {exc}"
            ) from exc
        elapsed_ms = (time.perf_counter() - started) * 1_000
        try:
            value = json.loads(body)
        except json.JSONDecodeError as exc:
            raise ProtocolExperimentError(
                "model returned invalid JSON"
            ) from exc
        if not isinstance(value.get("choices"), list) or not value["choices"]:
            raise ProtocolExperimentError(
                "model response contains no choices"
            )
        return value, elapsed_ms


class SyntheticProtocolExecutor:
    """Deterministic synthetic executor; it never parses or runs SQL."""

    def __init__(self, mode: str) -> None:
        if mode not in {"success", "deny"}:
            raise ProtocolExperimentError(
                f"unsupported synthetic executor mode: {mode}"
            )
        self.mode = mode

    def describe_schema(self) -> Mapping[str, Any]:
        return {
            "status": "ok",
            "synthetic_schema": {
                "synthetic_protocol_relation": ["synthetic_id"]
            },
        }

    def execute_sql(
        self,
        *,
        sql: str,
        attempt_id: str,
        attempt_index: int,
    ) -> Mapping[str, Any]:
        if not isinstance(sql, str) or not sql.strip():
            return {
                "status": "invalid_tool_arguments",
                "attempt_id": attempt_id,
            }
        if self.mode == "deny":
            return {
                "status": "synthetic_policy_denied",
                "attempt_id": attempt_id,
                "attempt_index": attempt_index,
            }
        return {
            "status": "ok",
            "attempt_id": attempt_id,
            "attempt_index": attempt_index,
            "synthetic_row_count": 1,
        }


def load_fixture(
    path: Path = FIXTURE_PATH,
) -> tuple[dict[str, Any], ProtocolLimits, tuple[Fixture, ...]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProtocolExperimentError(
            f"invalid fixture manifest: {path}"
        ) from exc
    if value.get("schema_version") != FIXTURE_SCHEMA_VERSION:
        raise ProtocolExperimentError("unsupported fixture schema")
    if value.get("claim_scope") != "native_tool_protocol_compliance_only":
        raise ProtocolExperimentError("fixture claim scope is not frozen")
    if value.get("benchmark_content_used") is not False:
        raise ProtocolExperimentError("benchmark content must remain excluded")
    variants = value.get("variants")
    if not isinstance(variants, list):
        raise ProtocolExperimentError("variants must be a list")
    variant_ids = tuple(item.get("id") for item in variants)
    if variant_ids != VARIANT_IDS:
        raise ProtocolExperimentError("variant order or identity changed")
    limits_value = value.get("limits")
    if not isinstance(limits_value, dict):
        raise ProtocolExperimentError("limits are missing")
    limits = ProtocolLimits(**limits_value)
    if limits.max_sql_attempts != 2:
        raise ProtocolExperimentError(
            "this compliance fixture requires two SQL attempts"
        )
    episodes_value = value.get("episodes")
    if not isinstance(episodes_value, list) or not episodes_value:
        raise ProtocolExperimentError("episodes are missing")
    fixtures: list[Fixture] = []
    for item in episodes_value:
        fixture = Fixture(
            fixture_id=str(item["fixture_id"]),
            executor_mode=str(item["executor_mode"]),
            expected_terminal_action=str(
                item["expected_terminal_action"]
            ),
            seed=int(item["seed"]),
            variant_order=tuple(item["variant_order"]),
        )
        if fixture.executor_mode not in {"success", "deny"}:
            raise ProtocolExperimentError("invalid executor mode")
        if fixture.expected_terminal_action not in {"submit", "abstain"}:
            raise ProtocolExperimentError("invalid expected terminal action")
        if set(fixture.variant_order) != set(VARIANT_IDS):
            raise ProtocolExperimentError(
                f"{fixture.fixture_id}: incomplete variant order"
            )
        fixtures.append(fixture)
    if len({item.fixture_id for item in fixtures}) != len(fixtures):
        raise ProtocolExperimentError("fixture IDs must be unique")
    if len({item.seed for item in fixtures}) != len(fixtures):
        raise ProtocolExperimentError("fixture seeds must be unique")
    position_counts: Counter[tuple[str, int]] = Counter()
    for fixture in fixtures:
        for position, variant in enumerate(fixture.variant_order):
            position_counts[(variant, position)] += 1
    expected_per_position = len(fixtures) // len(VARIANT_IDS)
    if len(fixtures) % len(VARIANT_IDS) or any(
        position_counts[(variant, position)] != expected_per_position
        for variant in VARIANT_IDS
        for position in range(len(VARIANT_IDS))
    ):
        raise ProtocolExperimentError(
            "variant ordering is not position-balanced"
        )
    return value, limits, tuple(fixtures)


def tools_for_state(
    *,
    variant: str,
    remaining_sql_attempts: int,
    remaining_schema_calls: int,
) -> list[dict[str, Any]]:
    if variant not in VARIANT_IDS:
        raise ProtocolExperimentError(f"unknown variant: {variant}")
    if remaining_sql_attempts < 0 or remaining_schema_calls < 0:
        raise ProtocolExperimentError("remaining budgets cannot be negative")
    tools = deepcopy(TOOLS)
    if (
        variant == "terminal_only_after_sql_budget"
        and remaining_sql_attempts == 0
    ):
        return [
            tool
            for tool in tools
            if tool["function"]["name"] in TERMINAL_TOOL_NAMES
        ]
    if variant == "remaining_budget_annotations":
        annotation = (
            " Protocol state: "
            f"remaining_sql_attempts={remaining_sql_attempts}; "
            f"remaining_schema_calls={remaining_schema_calls}. "
            "When the SQL budget reaches zero, choose submit_sql or abstain."
        )
        for tool in tools:
            tool["function"]["description"] += annotation
    return tools


def _fixture_user_prompt(fixture: Fixture) -> str:
    if fixture.expected_terminal_action == "submit":
        terminal = (
            "After exactly two execute_sql calls, call submit_sql with the "
            "attempt_id from the latest successful synthetic observation."
        )
    else:
        terminal = (
            "The synthetic executor will deny both attempts. After exactly "
            "two execute_sql calls, call abstain with reason_code "
            "tool_budget_exhausted."
        )
    return (
        "Inspect the synthetic schema once. Make exactly two execute_sql "
        "calls using any non-empty synthetic SELECT; SQL meaning is not "
        f"scored. {terminal}"
    )


def _attempt_id(*, fixture: Fixture, attempt_index: int) -> str:
    digest = hashlib.sha256(
        (
            f"{fixture.seed}\0{fixture.fixture_id}\0"
            f"synthetic-attempt\0{attempt_index}"
        ).encode("utf-8")
    ).hexdigest()
    return f"attempt_{digest[:24]}"


def _tool_message(
    *,
    call_id: str,
    name: str,
    result: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "role": "tool",
        "tool_call_id": call_id,
        "name": name,
        "content": json.dumps(
            result,
            sort_keys=True,
            separators=(",", ":"),
        ),
    }


def run_episode(
    *,
    fixture: Fixture,
    variant: str,
    limits: ProtocolLimits,
    api: ModelAPI,
    executor: ProtocolExecutor,
    raw_audit_path: Path,
) -> EpisodeReceipt:
    require_external_raw_path(raw_audit_path)
    if raw_audit_path.exists():
        raise ProtocolExperimentError(
            f"refusing to append to existing raw audit: {raw_audit_path}"
        )
    if variant not in fixture.variant_order:
        raise ProtocolExperimentError(
            f"{fixture.fixture_id}: variant is not in frozen schedule"
        )
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": BASE_SYSTEM_PROMPT},
        {"role": "user", "content": _fixture_user_prompt(fixture)},
    ]
    append_raw(
        raw_audit_path,
        {
            "event": "protocol_episode_start",
            "fixture": asdict(fixture),
            "variant": variant,
            "limits": asdict(limits),
            "messages": messages,
            "claim_scope": "native_tool_protocol_compliance_only",
        },
    )

    model_calls = 0
    native_tool_calls = 0
    schema_calls = 0
    sql_attempts = 0
    successful_attempt_ids: list[str] = []
    over_budget_sql_calls = 0
    unavailable_tool_calls = 0
    prompt_tokens = 0
    completion_tokens = 0
    elapsed_ms = 0.0
    terminal_action = "none"
    terminal_failure_code: str | None = None
    system_fingerprint: str | None = None
    offered_tool_schedule: list[list[dict[str, Any]]] = []
    native_tool_call_chain: list[dict[str, Any]] = []
    model_response_chain: list[dict[str, Any]] = []

    for turn in range(limits.max_model_turns):
        remaining_seconds = limits.model_wall_seconds - elapsed_ms / 1_000
        if remaining_seconds <= 0:
            terminal_failure_code = "model_wall_time_exhausted"
            break
        remaining_sql = limits.max_sql_attempts - sql_attempts
        remaining_schema = limits.max_schema_calls - schema_calls
        offered_tools = tools_for_state(
            variant=variant,
            remaining_sql_attempts=remaining_sql,
            remaining_schema_calls=remaining_schema,
        )
        offered_tool_schedule.append(offered_tools)
        request_record = {
            "event": "model_request",
            "turn": turn,
            "model": api.request_model_id,
            "seed": fixture.seed,
            "messages": messages,
            "tools": offered_tools,
            "remaining_sql_attempts": remaining_sql,
            "remaining_schema_calls": remaining_schema,
        }
        append_raw(raw_audit_path, request_record)
        response, call_elapsed_ms = api.complete(
            messages=messages,
            tools=offered_tools,
            seed=fixture.seed,
            max_tokens=limits.max_generated_tokens_per_call,
            timeout_seconds=max(1, int(remaining_seconds)),
        )
        elapsed_ms += call_elapsed_ms
        model_calls += 1
        usage = response.get("usage") or {}
        prompt_tokens += int(usage.get("prompt_tokens") or 0)
        completion_tokens += int(usage.get("completion_tokens") or 0)
        system_fingerprint = (
            response.get("system_fingerprint") or system_fingerprint
        )
        model_response_chain.append(response)
        append_raw(
            raw_audit_path,
            {
                "event": "model_response",
                "turn": turn,
                "elapsed_ms": call_elapsed_ms,
                "response": response,
            },
        )

        choice = response["choices"][0]
        assistant = choice.get("message") or {}
        returned_calls = assistant.get("tool_calls") or []
        assistant_message: dict[str, Any] = {
            "role": "assistant",
            "content": assistant.get("content") or "",
        }
        if returned_calls:
            assistant_message["tool_calls"] = returned_calls
        messages.append(assistant_message)
        if not returned_calls:
            terminal_failure_code = (
                "tool_parser_dropped_tool_calls"
                if choice.get("finish_reason") == "tool_calls"
                else "text_without_terminal_tool"
            )
            break

        offered_names = {
            str(tool["function"]["name"])
            for tool in offered_tools
        }
        for returned_call in returned_calls:
            native_tool_calls += 1
            native_tool_call_chain.append(returned_call)
            call_id = str(
                returned_call.get("id")
                or f"call-{turn}-{native_tool_calls}"
            )
            function = returned_call.get("function") or {}
            name = str(function.get("name") or "")
            raw_arguments = function.get("arguments") or "{}"
            try:
                arguments = (
                    json.loads(raw_arguments)
                    if isinstance(raw_arguments, str)
                    else raw_arguments
                )
            except json.JSONDecodeError:
                arguments = None
            append_raw(
                raw_audit_path,
                {
                    "event": "native_tool_call",
                    "turn": turn,
                    "call": returned_call,
                    "parsed_arguments": arguments,
                    "tool_was_offered": name in offered_names,
                },
            )

            if terminal_action != "none":
                result: Mapping[str, Any] = {
                    "status": "terminal_action_already_selected",
                    "terminal_action": terminal_action,
                }
            elif name not in offered_names:
                unavailable_tool_calls += 1
                result = {
                    "status": "tool_not_available",
                    "tool_name": name,
                }
            elif not isinstance(arguments, dict):
                result = {"status": "invalid_tool_arguments"}
            elif name == "describe_schema":
                if schema_calls >= limits.max_schema_calls:
                    result = {
                        "status": "schema_call_limit",
                        "max_schema_calls": limits.max_schema_calls,
                    }
                else:
                    schema_calls += 1
                    result = executor.describe_schema()
            elif name == "execute_sql":
                sql = arguments.get("sql")
                if not isinstance(sql, str) or not sql.strip():
                    result = {
                        "status": "invalid_tool_arguments",
                        "message": "sql must be a non-empty string",
                    }
                elif sql_attempts >= limits.max_sql_attempts:
                    over_budget_sql_calls += 1
                    result = {
                        "status": "sql_attempt_limit",
                        "max_sql_attempts": limits.max_sql_attempts,
                    }
                else:
                    attempt_index = sql_attempts
                    attempt_id = _attempt_id(
                        fixture=fixture,
                        attempt_index=attempt_index,
                    )
                    sql_attempts += 1
                    result = executor.execute_sql(
                        sql=sql,
                        attempt_id=attempt_id,
                        attempt_index=attempt_index,
                    )
                    if (
                        result.get("status") == "ok"
                        and result.get("attempt_id") == attempt_id
                    ):
                        successful_attempt_ids.append(attempt_id)
            elif name == "submit_sql":
                attempt_id = arguments.get("attempt_id")
                if (
                    isinstance(attempt_id, str)
                    and attempt_id in successful_attempt_ids
                ):
                    terminal_action = "submit"
                    result = {
                        "status": "submitted",
                        "attempt_id": attempt_id,
                    }
                else:
                    result = {
                        "status": "invalid_submission",
                        "message": (
                            "attempt_id must identify a successful attempt"
                        ),
                    }
            elif name == "abstain":
                reason_code = arguments.get("reason_code")
                if reason_code in ABSTAIN_REASON_CODES:
                    terminal_action = "abstain"
                    result = {
                        "status": "abstained",
                        "reason_code": reason_code,
                    }
                else:
                    result = {
                        "status": "invalid_abstention",
                        "allowed_reason_codes": list(
                            ABSTAIN_REASON_CODES
                        ),
                    }
            else:
                result = {
                    "status": "unknown_tool",
                    "tool_name": name,
                }
            append_raw(
                raw_audit_path,
                {
                    "event": "native_tool_result",
                    "turn": turn,
                    "call_id": call_id,
                    "tool_name": name,
                    "result": result,
                },
            )
            messages.append(
                _tool_message(
                    call_id=call_id,
                    name=name,
                    result=result,
                )
            )
        if terminal_action != "none":
            break
    else:
        terminal_failure_code = "model_turn_limit_exhausted"

    terminal_outcome = {
        "submit": "submitted",
        "abstain": "abstained",
        "none": "terminal_failure",
    }[terminal_action]
    expected_match = terminal_action == fixture.expected_terminal_action
    append_raw(
        raw_audit_path,
        {
            "event": "protocol_episode_end",
            "terminal_action": terminal_action,
            "terminal_outcome": terminal_outcome,
            "expected_terminal_match": expected_match,
            "terminal_failure_code": terminal_failure_code,
            "model_calls": model_calls,
            "native_tool_calls": native_tool_calls,
            "schema_calls": schema_calls,
            "sql_attempts": sql_attempts,
            "successful_sql_attempts": len(successful_attempt_ids),
            "over_budget_sql_calls": over_budget_sql_calls,
            "unavailable_tool_calls": unavailable_tool_calls,
        },
    )
    raw_hash = sha256_file(raw_audit_path)
    return EpisodeReceipt(
        fixture_id_sha256=hashlib.sha256(
            fixture.fixture_id.encode("utf-8")
        ).hexdigest(),
        variant=variant,
        seed=fixture.seed,
        expected_terminal_action=fixture.expected_terminal_action,
        terminal_action=terminal_action,
        terminal_outcome=terminal_outcome,
        expected_terminal_match=expected_match,
        terminal_failure_code=terminal_failure_code,
        model_calls=model_calls,
        native_tool_calls=native_tool_calls,
        schema_calls=schema_calls,
        sql_attempts=sql_attempts,
        successful_sql_attempts=len(successful_attempt_ids),
        over_budget_sql_calls=over_budget_sql_calls,
        unavailable_tool_calls=unavailable_tool_calls,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        elapsed_ms=round(elapsed_ms, 3),
        offered_tool_schedule_sha256=sha256_value(
            offered_tool_schedule
        ),
        native_tool_call_chain_sha256=sha256_value(
            native_tool_call_chain
        ),
        model_response_chain_sha256=sha256_value(
            model_response_chain
        ),
        system_fingerprint=system_fingerprint,
        raw_audit_sha256=raw_hash,
    )


def aggregate_receipts(
    *,
    receipts: list[EpisodeReceipt],
    fixture_manifest: Mapping[str, Any],
    fixture_sha256: str,
    request_model_id: str,
) -> dict[str, Any]:
    expected_runs = len(fixture_manifest["episodes"]) * len(VARIANT_IDS)
    if len(receipts) != expected_runs:
        raise ProtocolExperimentError(
            f"expected {expected_runs} receipts, got {len(receipts)}"
        )
    grouped: dict[str, list[EpisodeReceipt]] = defaultdict(list)
    for receipt in receipts:
        grouped[receipt.variant].append(receipt)
    variant_results: dict[str, Any] = {}
    for variant in VARIANT_IDS:
        items = grouped[variant]
        if len(items) != len(fixture_manifest["episodes"]):
            raise ProtocolExperimentError(
                f"{variant}: incomplete paired schedule"
            )
        denominator = len(items)
        submit_count = sum(
            item.terminal_outcome == "submitted" for item in items
        )
        abstain_count = sum(
            item.terminal_outcome == "abstained" for item in items
        )
        failure_count = sum(
            item.terminal_outcome == "terminal_failure"
            for item in items
        )
        match_count = sum(item.expected_terminal_match for item in items)
        variant_results[variant] = {
            "episodes": denominator,
            "terminal_submit_count": submit_count,
            "terminal_submit_rate": submit_count / denominator,
            "terminal_abstain_count": abstain_count,
            "terminal_abstain_rate": abstain_count / denominator,
            "terminal_failure_count": failure_count,
            "terminal_failure_rate": failure_count / denominator,
            "expected_terminal_match_count": match_count,
            "expected_terminal_match_rate": match_count / denominator,
            "over_budget_sql_calls": sum(
                item.over_budget_sql_calls for item in items
            ),
            "unavailable_tool_calls": sum(
                item.unavailable_tool_calls for item in items
            ),
            "model_calls": sum(item.model_calls for item in items),
            "native_tool_calls": sum(
                item.native_tool_calls for item in items
            ),
            "terminal_failure_codes": dict(
                sorted(
                    Counter(
                        item.terminal_failure_code
                        for item in items
                        if item.terminal_failure_code is not None
                    ).items()
                )
            ),
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "experiment_id": fixture_manifest["experiment_id"],
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "claim_scope": "native_tool_protocol_compliance_only",
        "claim_exclusions": list(
            fixture_manifest["claim_exclusions"]
        ),
        "benchmark_content_used": False,
        "raw_model_content_committed": False,
        "raw_audit_policy": (
            "external_jsonl_only; aggregate contains hashes and counts"
        ),
        "request_model_id": request_model_id,
        "fixture_manifest_sha256": fixture_sha256,
        "frozen_tool_schema_sha256": sha256_value(TOOLS),
        "frozen_schedule_sha256": sha256_value(
            fixture_manifest["episodes"]
        ),
        "variant_definitions": fixture_manifest["variants"],
        "variant_results": variant_results,
        "episode_receipts": [
            asdict(receipt)
            for receipt in receipts
        ],
    }


def run_experiment(
    *,
    endpoint: str,
    request_model_id: str,
    raw_audit_dir: Path,
    output_path: Path,
    fixture_path: Path = FIXTURE_PATH,
) -> dict[str, Any]:
    require_external_raw_path(raw_audit_dir)
    if output_path.exists():
        raise ProtocolExperimentError(
            f"refusing to overwrite aggregate output: {output_path}"
        )
    fixture_manifest, limits, fixtures = load_fixture(fixture_path)
    api = ChatAPI(
        endpoint=endpoint,
        request_model_id=request_model_id,
    )
    planned: list[tuple[Fixture, str, Path]] = []
    for fixture in fixtures:
        fixture_hash = hashlib.sha256(
            fixture.fixture_id.encode("utf-8")
        ).hexdigest()[:16]
        for variant in fixture.variant_order:
            raw_path = raw_audit_dir / (
                f"{fixture_hash}-{variant}.jsonl"
            )
            require_external_raw_path(raw_path)
            if raw_path.exists():
                raise ProtocolExperimentError(
                    f"raw audit already exists: {raw_path}"
                )
            planned.append((fixture, variant, raw_path))
    receipts: list[EpisodeReceipt] = []
    for fixture, variant, raw_path in planned:
        receipts.append(
            run_episode(
                fixture=fixture,
                variant=variant,
                limits=limits,
                api=api,
                executor=SyntheticProtocolExecutor(
                    fixture.executor_mode
                ),
                raw_audit_path=raw_path,
            )
        )
    aggregate = aggregate_receipts(
        receipts=receipts,
        fixture_manifest=fixture_manifest,
        fixture_sha256=sha256_file(fixture_path),
        request_model_id=request_model_id,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(canonical_json_bytes(aggregate) + b"\n")
    return aggregate


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the synthetic native-tool protocol-compliance experiment. "
            "No SQL-quality claim is produced."
        )
    )
    parser.add_argument(
        "--endpoint",
        required=True,
        help="Explicit OpenAI-compatible loopback or test endpoint.",
    )
    parser.add_argument(
        "--model",
        required=True,
        help="Explicit request model identifier.",
    )
    parser.add_argument(
        "--raw-audit-dir",
        required=True,
        type=Path,
        help="External directory for full raw JSONL model/tool transcripts.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Content-minimized aggregate JSON output.",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=FIXTURE_PATH,
        help="Frozen synthetic fixture manifest.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    aggregate = run_experiment(
        endpoint=args.endpoint,
        request_model_id=args.model,
        raw_audit_dir=args.raw_audit_dir,
        output_path=args.output,
        fixture_path=args.fixture,
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "schema_version": aggregate["schema_version"],
                "claim_scope": aggregate["claim_scope"],
                "aggregate_sha256": sha256_value(aggregate),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
