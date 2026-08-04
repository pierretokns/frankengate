#!/usr/bin/env python3
"""Run leakage-safe governed Defog SQL agent arms through a local model API.

Raw prompts, model responses, SQL, schema metadata, and result previews are
written only below ``--raw-audit-dir``. The committed aggregate contains
content hashes, task receipts, outcomes, usage, latency, and claim boundaries.

The initial three arms are explicitly *not* trace-mined. They establish the
baseline tool loop, placebo behavior, and intervention sensitivity before a
candidate skill is learned exclusively from evidence-family trajectories.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import time
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sqlglot import exp

from defog_factorial_authority import (
    AuthorityReceipt,
    StaticAuthorityEpochStore,
)
from defog_sql_factorial_contract import (
    ABSTAIN_REASON_CODES,
    ARM_ARTIFACTS as ARM_PROMPTS,
    BASE_SYSTEM_PROMPT,
    LIMITS as FROZEN_LIMITS,
    TOOLS,
)
from defog_governed_sql_replay import (
    AuthorizationError,
    GovernanceAuthority,
    GovernedPostgresExecutor,
    PinnedTaskResolver,
    QueryResult,
    RuntimeTask,
    SQLPolicyError,
    ValidatedSQL,
    result_content_hash,
    results_equal,
    sha256_text,
    strict_answer_shape_results_equal,
)


SCHEMA_VERSION = "frankengate-defog-sql-factorial-v3-terminal-only"
AUTHORITY_SCOPE = "enterprise"
AUTHORIZATION_EPOCH_REF = "defog-factorial-authority-v1"
AUTHORITY_USER_ID = "factorial-pilot-user"
AUTHORITY_TEAM_ID = "factorial-pilot-team"
AUTHORITY_VIRTUAL_KEY_ID = "factorial-pilot-vk"
TERMINAL_TOOL_NAMES = frozenset({"submit_sql", "abstain"})
TERMINAL_STATE_CONTROL_MESSAGE = (
    "Protocol controller: remaining_sql_attempts=0. The only valid next "
    "action is exactly one native call to submit_sql or abstain. Do not "
    "analyze, explain, or call an unavailable tool."
)


class FactorialError(RuntimeError):
    """Raised when the experiment contract or model API fails."""


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_external_raw_audit_dir(path: Path) -> None:
    repository_root = Path(__file__).resolve().parents[2]
    resolved = path.resolve()
    try:
        resolved.relative_to(repository_root)
    except ValueError:
        return
    raise FactorialError(
        "raw_audit_dir must be outside the research repository"
    )


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _append_raw(path: Path, record: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(record, sort_keys=True, ensure_ascii=False, default=str)
            + "\n"
        )


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, bytes):
        return {"bytes_hex": value.hex()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _json_safe(item)
            for key, item in value.items()
        }
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _model_result(
    result: QueryResult,
    *,
    preview_rows: int = FROZEN_LIMITS["model_result_max_rows"],
    preview_bytes: int = FROZEN_LIMITS["model_result_max_bytes"],
) -> str:
    """Render a row- and byte-bounded model observation."""

    payload: dict[str, Any] = {
        "status": "ok",
        "columns": list(result.columns),
        "row_count": len(result.rows),
        "rows": [],
        "preview_truncated": bool(result.rows),
        "result_bytes": result.result_bytes,
    }
    for row in result.rows[:preview_rows]:
        payload["rows"].append(_json_safe(row))
        payload["preview_truncated"] = (
            len(payload["rows"]) < len(result.rows)
        )
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )
        if len(encoded.encode("utf-8")) > preview_bytes:
            payload["rows"].pop()
            payload["preview_truncated"] = True
            break
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    if len(encoded.encode("utf-8")) > preview_bytes:
        payload = {
            "status": "result_preview_too_large",
            "column_count": len(result.columns),
            "row_count": len(result.rows),
            "rows": [],
            "preview_truncated": True,
            "result_bytes": result.result_bytes,
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    if len(encoded.encode("utf-8")) > preview_bytes:
        raise FactorialError("model result envelope exceeds byte limit")
    return encoded


def _model_error(exc: Exception) -> str:
    if isinstance(exc, SQLPolicyError):
        return json.dumps(
            {
                "status": "policy_denied",
                "code": exc.code,
                "message": str(exc)[:1_000],
            }
        )
    return json.dumps(
        {
            "status": "database_error",
            "error_class": type(exc).__name__,
            "message": str(exc)[:1_000],
        }
    )


class ChatAPI:
    def __init__(
        self,
        *,
        endpoint: str,
        request_model_id: str,
        timeout_seconds: int,
        max_tokens: int,
    ) -> None:
        self.url = endpoint.rstrip("/") + "/v1/chat/completions"
        self.request_model_id = request_model_id
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens

    def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        seed: int,
        max_tokens: int | None = None,
        timeout_seconds: int | None = None,
    ) -> tuple[dict[str, Any], float]:
        payload = {
            "model": self.request_model_id,
            "messages": messages,
            "tools": TOOLS if tools is None else tools,
            "temperature": 0,
            "top_p": 1,
            "top_k": 0,
            "min_p": 0,
            "seed": seed,
            "max_completion_tokens": (
                self.max_tokens if max_tokens is None else max_tokens
            ),
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        encoded = canonical_json_bytes(payload)
        request = Request(
            self.url,
            data=encoded,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        started = time.perf_counter()
        try:
            with urlopen(
                request,
                timeout=(
                    self.timeout_seconds
                    if timeout_seconds is None
                    else timeout_seconds
                ),
            ) as response:
                body = response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise FactorialError(
                f"model HTTP {exc.code}: {detail[:2_000]}"
            ) from exc
        except (URLError, TimeoutError) as exc:
            raise FactorialError(f"model request failed: {exc}") from exc
        elapsed_ms = (time.perf_counter() - started) * 1_000
        try:
            value = json.loads(body)
        except json.JSONDecodeError as exc:
            raise FactorialError("model returned invalid JSON") from exc
        if not value.get("choices"):
            raise FactorialError(f"model response has no choices: {value}")
        return value, elapsed_ms


@dataclass(frozen=True)
class AgentLimits:
    max_model_turns: int = FROZEN_LIMITS["max_model_turns"]
    max_schema_calls: int = FROZEN_LIMITS["max_schema_calls"]
    max_sql_attempts: int = FROZEN_LIMITS["max_sql_attempts"]
    result_preview_rows: int = FROZEN_LIMITS["model_result_max_rows"]
    result_preview_bytes: int = FROZEN_LIMITS["model_result_max_bytes"]
    max_generated_tokens_per_episode: int = FROZEN_LIMITS[
        "max_generated_tokens_per_episode"
    ]
    model_wall_seconds: int = FROZEN_LIMITS["model_wall_seconds"]


@dataclass(frozen=True)
class AttemptReceipt:
    """Content-free, immutable record of one model-requested SQL attempt."""

    attempt_id: str
    attempt_index: int
    sql_sha256: str
    authority_valid: bool
    policy_accepted: bool | None
    execution_completed: bool
    unauthorized_observation: bool
    status: str
    policy_error_code: str | None
    error_class: str | None
    result_sha256: str | None
    row_count: int | None
    column_count: int | None


@dataclass(frozen=True)
class AttemptRecord:
    """In-memory execution evidence; raw SQL never enters the aggregate."""

    receipt: AttemptReceipt
    sql: str
    validation: ValidatedSQL | None
    result: QueryResult | None


@dataclass(frozen=True)
class RunReceipt:
    task_id_sha256: str
    arm: str
    seed: int
    semantic_correct: bool
    strict_answer_shape_correct: bool
    authority_valid: bool
    policy_accepted: bool | None
    execution_completed: bool
    unauthorized_observation: bool
    outcome: str
    terminal_action: str
    submitted_attempt_id: str | None
    abstain_reason_code: str | None
    protocol_failure_code: str | None
    policy_error_code: str | None
    candidate_sql_sha256: str | None
    final_answer_sha256: str | None
    attempt_receipts: tuple[AttemptReceipt, ...]
    attempt_receipt_chain_sha256: str
    authority_binding_sha256: str | None
    authority_epoch_ref_sha256: str | None
    authority_snapshot_sha256: str | None
    model_calls: int
    tool_calls: int
    schema_calls: int
    sql_attempts: int
    successful_sql_attempts: int
    prompt_tokens: int
    completion_tokens: int
    elapsed_ms: float
    system_fingerprint: str | None
    raw_audit_sha256: str
    terminal_fallback_used: bool = False


def _task_seed(task_id: str, base_seed: int) -> int:
    digest = hashlib.sha256(
        f"{base_seed}\0{task_id}".encode("utf-8")
    ).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def _attempt_id(*, seed: int, attempt_index: int) -> str:
    digest = sha256_text(f"{seed}\0sql-attempt\0{attempt_index}")
    return f"attempt_{digest[:24]}"


def _frozen_arm_order(
    *,
    fold: Mapping[str, Any],
    task_id: str,
    arms: list[str],
) -> list[str]:
    """Resolve the preregistered per-task order without recomputing it."""

    if not arms or len(set(arms)) != len(arms):
        raise FactorialError("arms must be non-empty and unique")
    try:
        frozen = fold["arm_order"]["mechanics_smoke"][task_id]
    except (KeyError, TypeError) as exc:
        raise FactorialError(
            f"{task_id}: missing frozen mechanics_smoke arm order"
        ) from exc
    if (
        not isinstance(frozen, list)
        or len(set(frozen)) != len(frozen)
        or set(frozen) != set(ARM_PROMPTS)
    ):
        raise FactorialError(
            f"{task_id}: invalid frozen mechanics_smoke arm order"
        )
    ordered = [arm for arm in frozen if arm in arms]
    if set(ordered) != set(arms):
        raise FactorialError(
            f"{task_id}: frozen arm order omits a requested arm"
        )
    return ordered


def _authority_valid(executor: GovernedPostgresExecutor) -> bool:
    authority = getattr(executor, "authority", None)
    if authority is None:
        return True
    try:
        authority.validate()
    except AuthorizationError:
        return False
    return True


def _evaluate_submitted_attempt(
    *,
    task: RuntimeTask,
    attempt: AttemptRecord,
    executor: GovernedPostgresExecutor,
) -> tuple[bool, bool, str | None]:
    """Compare stored execution evidence; never run candidate SQL again."""

    if attempt.validation is None or attempt.result is None:
        return False, False, "submitted_attempt_not_executable"
    try:
        gold_results = executor.execute_gold_alternatives(task.gold_sql)
    except Exception as exc:
        return False, False, type(exc).__name__
    benchmark_match = False
    strict_match = False
    for gold_statement, gold_result in gold_results:
        gold_order_sensitive = any(
            bool(select.args.get("order"))
            for select in gold_statement.find_all(exp.Select)
        )
        if results_equal(
            attempt.result,
            gold_result,
            order_sensitive=gold_order_sensitive,
        ):
            benchmark_match = True
        if strict_answer_shape_results_equal(
            attempt.result,
            gold_result,
            order_sensitive=gold_order_sensitive,
        ):
            strict_match = True
    return benchmark_match, strict_match, None


def _system_prompt(arm: str) -> str:
    if arm not in ARM_PROMPTS:
        raise FactorialError(f"unknown arm: {arm}")
    addition = ARM_PROMPTS[arm].strip()
    return BASE_SYSTEM_PROMPT + (f"\n\n{addition}" if addition else "")


def _user_prompt(task: RuntimeTask) -> str:
    value = f"Question:\n{task.question}"
    if task.instructions:
        value += f"\n\nAdditional domain instructions:\n{task.instructions}"
    return value


def _tool_message(
    *,
    tool_call_id: str,
    name: str,
    content: str,
) -> dict[str, Any]:
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "name": name,
        "content": content,
    }


def _tools_for_attempt_count(
    *,
    sql_attempts: int,
    max_sql_attempts: int,
) -> list[dict[str, Any]]:
    """Preserve the frozen tool contract while enforcing terminal scheduling."""

    if sql_attempts < 0 or max_sql_attempts <= 0:
        raise FactorialError("SQL attempt budgets must be positive")
    if sql_attempts < max_sql_attempts:
        return TOOLS
    return [
        tool
        for tool in TOOLS
        if tool["function"]["name"] in TERMINAL_TOOL_NAMES
    ]


def run_agent(
    *,
    task: RuntimeTask,
    arm: str,
    seed: int,
    api: ChatAPI,
    executor: GovernedPostgresExecutor,
    limits: AgentLimits,
    raw_audit_path: Path,
    authority_receipt: AuthorityReceipt | None = None,
    terminal_fallback: bool = False,
) -> RunReceipt:
    system_prompt = _system_prompt(arm)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": _user_prompt(task)},
    ]
    _append_raw(
        raw_audit_path,
        {
            "event": "factorial_task_start",
            "task_id": task.task_id,
            "database": task.database,
            "query_category": task.query_category,
            "question": task.question,
            "instructions": task.instructions,
            "arm": arm,
            "system_prompt": system_prompt,
            "seed": seed,
            "authority_receipt": (
                asdict(authority_receipt)
                if authority_receipt is not None
                else None
            ),
        },
    )

    model_calls = 0
    tool_calls = 0
    schema_calls = 0
    attempt_records: dict[str, AttemptRecord] = {}
    successful_sql_attempts = 0
    prompt_tokens = 0
    completion_tokens = 0
    total_elapsed_ms = 0.0
    final_answer = ""
    system_fingerprint: str | None = None
    terminal_action = "none"
    submitted_attempt: AttemptRecord | None = None
    abstain_reason_code: str | None = None
    authority_checks: list[bool] = [_authority_valid(executor)]
    unauthorized_observation = False
    protocol_failure_code: str | None = None

    for turn in range(limits.max_model_turns):
        remaining_model_seconds = (
            limits.model_wall_seconds - total_elapsed_ms / 1_000
        )
        remaining_generated_tokens = (
            limits.max_generated_tokens_per_episode - completion_tokens
        )
        if remaining_model_seconds <= 0:
            protocol_failure_code = "model_wall_time_exhausted"
            break
        if remaining_generated_tokens <= 0:
            protocol_failure_code = "generated_token_budget_exhausted"
            break
        offered_tools = _tools_for_attempt_count(
            sql_attempts=len(attempt_records),
            max_sql_attempts=limits.max_sql_attempts,
        )
        request_receipt = {
            "event": "model_request",
            "turn": turn,
            "messages": messages,
            "tools": offered_tools,
            "seed": seed,
            "model": api.request_model_id,
        }
        _append_raw(raw_audit_path, request_receipt)
        response, elapsed_ms = api.complete(
            messages=messages,
            tools=offered_tools,
            seed=seed,
            max_tokens=min(api.max_tokens, remaining_generated_tokens),
            timeout_seconds=max(1, int(remaining_model_seconds)),
        )
        total_elapsed_ms += elapsed_ms
        model_calls += 1
        usage = response.get("usage") or {}
        prompt_tokens += int(usage.get("prompt_tokens") or 0)
        completion_tokens += int(usage.get("completion_tokens") or 0)
        system_fingerprint = (
            response.get("system_fingerprint") or system_fingerprint
        )
        _append_raw(
            raw_audit_path,
            {
                "event": "model_response",
                "turn": turn,
                "elapsed_ms": elapsed_ms,
                "response": response,
            },
        )

        choice = response["choices"][0]
        assistant = choice.get("message") or {}
        assistant_message = {
            "role": "assistant",
            "content": assistant.get("content") or "",
        }
        returned_tool_calls = assistant.get("tool_calls") or []
        if returned_tool_calls:
            assistant_message["tool_calls"] = returned_tool_calls
        messages.append(assistant_message)
        if not returned_tool_calls:
            if choice.get("finish_reason") == "tool_calls":
                protocol_failure_code = "tool_parser_dropped_tool_calls"
                break
            final_answer = assistant_message["content"]
            break

        for call in returned_tool_calls:
            tool_calls += 1
            call_id = str(call.get("id") or f"call-{tool_calls}")
            function = call.get("function") or {}
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

            enter_terminal_state = False
            offered_names = {
                str(tool["function"]["name"])
                for tool in offered_tools
            }
            if terminal_action != "none":
                content = json.dumps(
                    {
                        "status": "terminal_action_already_selected",
                        "terminal_action": terminal_action,
                    }
                )
            elif name not in offered_names:
                content = json.dumps(
                    {
                        "status": "tool_not_available",
                        "tool_name": name,
                        "available_tools": sorted(offered_names),
                    }
                )
            elif name == "describe_schema" and isinstance(arguments, dict):
                if schema_calls >= limits.max_schema_calls:
                    content = json.dumps(
                        {
                            "status": "schema_call_limit",
                            "max_schema_calls": limits.max_schema_calls,
                        }
                    )
                else:
                    schema_calls += 1
                    call_authority_valid = _authority_valid(executor)
                    authority_checks.append(call_authority_valid)
                    if not call_authority_valid:
                        content = json.dumps(
                            {
                                "status": "authority_denied",
                                "message": "governance authority is invalid",
                            }
                        )
                    else:
                        try:
                            catalog = executor.catalog()
                        except AuthorizationError:
                            authority_checks.append(False)
                            content = json.dumps(
                                {
                                    "status": "authority_denied",
                                    "message": (
                                        "governance authority is invalid"
                                    ),
                                }
                            )
                        except Exception as exc:
                            content = _model_error(exc)
                        else:
                            content = json.dumps(
                                {
                                    "status": "ok",
                                    "tables": {
                                        table: sorted(columns)
                                        for table, columns in catalog.items()
                                    },
                                },
                                sort_keys=True,
                            )
            elif name == "execute_sql" and isinstance(arguments, dict):
                sql = arguments.get("sql")
                if not isinstance(sql, str) or not sql.strip():
                    content = json.dumps(
                        {
                            "status": "invalid_tool_arguments",
                            "message": "sql must be a non-empty string",
                        }
                    )
                elif len(attempt_records) >= limits.max_sql_attempts:
                    content = json.dumps(
                        {
                            "status": "sql_attempt_limit",
                            "max_sql_attempts": limits.max_sql_attempts,
                        }
                    )
                else:
                    attempt_index = len(attempt_records)
                    attempt_id = _attempt_id(
                        seed=seed,
                        attempt_index=attempt_index,
                    )
                    call_authority_valid = _authority_valid(executor)
                    authority_checks.append(call_authority_valid)
                    validation: ValidatedSQL | None = None
                    query_result: QueryResult | None = None
                    policy_accepted: bool | None = None
                    execution_completed = False
                    attempt_unauthorized_observation = False
                    policy_error_code: str | None = None
                    error_class: str | None = None
                    try:
                        if not call_authority_valid:
                            raise AuthorizationError(
                                "governance authority is invalid"
                            )
                        validation, query_result = (
                            executor.execute_candidate(sql)
                        )
                    except AuthorizationError as exc:
                        authority_checks.append(False)
                        call_authority_valid = False
                        error_class = type(exc).__name__
                        status = "authority_denied"
                        content_value = {
                            "status": status,
                            "message": "governance authority is invalid",
                        }
                    except SQLPolicyError as exc:
                        policy_accepted = False
                        policy_error_code = exc.code
                        error_class = type(exc).__name__
                        status = "policy_denied"
                        content_value = json.loads(_model_error(exc))
                    except Exception as exc:
                        error_class = type(exc).__name__
                        status = "database_error"
                        content_value = json.loads(_model_error(exc))
                    else:
                        policy_accepted = True
                        execution_completed = True
                        successful_sql_attempts += 1
                        status = "ok"
                        content_value = json.loads(
                            _model_result(
                                query_result,
                                preview_rows=limits.result_preview_rows,
                                preview_bytes=limits.result_preview_bytes,
                            )
                        )
                        attempt_unauthorized_observation = (
                            not call_authority_valid
                        )
                    content_value["attempt_id"] = attempt_id
                    if (
                        len(attempt_records) + 1
                        >= limits.max_sql_attempts
                    ):
                        enter_terminal_state = True
                        content_value["protocol_state"] = {
                            "remaining_sql_attempts": 0,
                            "available_actions": [
                                "submit_sql",
                                "abstain",
                            ],
                            "required_terminal_action": True,
                        }
                    content = json.dumps(
                        content_value,
                        ensure_ascii=False,
                        sort_keys=True,
                    )
                    unauthorized_observation = (
                        unauthorized_observation
                        or attempt_unauthorized_observation
                    )
                    receipt = AttemptReceipt(
                        attempt_id=attempt_id,
                        attempt_index=attempt_index,
                        sql_sha256=sha256_text(sql),
                        authority_valid=call_authority_valid,
                        policy_accepted=policy_accepted,
                        execution_completed=execution_completed,
                        unauthorized_observation=(
                            attempt_unauthorized_observation
                        ),
                        status=status,
                        policy_error_code=policy_error_code,
                        error_class=error_class,
                        result_sha256=(
                            result_content_hash(query_result)
                            if query_result is not None
                            else None
                        ),
                        row_count=(
                            len(query_result.rows)
                            if query_result is not None
                            else None
                        ),
                        column_count=(
                            len(query_result.columns)
                            if query_result is not None
                            else None
                        ),
                    )
                    attempt_records[attempt_id] = AttemptRecord(
                        receipt=receipt,
                        sql=sql,
                        validation=validation,
                        result=query_result,
                    )
            elif name == "submit_sql" and isinstance(arguments, dict):
                attempt_id = arguments.get("attempt_id")
                record = (
                    attempt_records.get(attempt_id)
                    if isinstance(attempt_id, str)
                    else None
                )
                if record is None:
                    content = json.dumps(
                        {
                            "status": "invalid_submission",
                            "code": "unknown_attempt_id",
                        }
                    )
                elif not (
                    record.receipt.authority_valid
                    and record.receipt.policy_accepted is True
                    and record.receipt.execution_completed
                    and record.result is not None
                ):
                    content = json.dumps(
                        {
                            "status": "invalid_submission",
                            "code": "attempt_not_successful",
                            "attempt_id": record.receipt.attempt_id,
                        }
                    )
                else:
                    submitted_attempt = record
                    terminal_action = "submit_sql"
                    final_answer = assistant_message["content"]
                    content = json.dumps(
                        {
                            "status": "accepted",
                            "terminal": True,
                            "attempt_id": record.receipt.attempt_id,
                        }
                    )
            elif name == "abstain" and isinstance(arguments, dict):
                reason_code = arguments.get("reason_code")
                if reason_code not in ABSTAIN_REASON_CODES:
                    content = json.dumps(
                        {
                            "status": "invalid_tool_arguments",
                            "message": "reason_code is not allowed",
                        }
                    )
                else:
                    abstain_reason_code = str(reason_code)
                    terminal_action = "abstain"
                    final_answer = assistant_message["content"]
                    content = json.dumps(
                        {"status": "accepted", "terminal": True}
                    )
            else:
                content = json.dumps(
                    {
                        "status": "unknown_or_invalid_tool_call",
                        "name": name,
                    }
                )

            _append_raw(
                raw_audit_path,
                {
                    "event": "agent_tool_result",
                    "turn": turn,
                    "tool_call_id": call_id,
                    "name": name,
                    "arguments": arguments,
                    "tool_was_offered": name in offered_names,
                    "content": content,
                },
            )
            messages.append(
                _tool_message(
                    tool_call_id=call_id,
                    name=name or "unknown",
                    content=content,
                )
            )
            if enter_terminal_state:
                messages.append(
                    {
                        "role": "user",
                        "content": TERMINAL_STATE_CONTROL_MESSAGE,
                    }
                )
            if terminal_action != "none":
                break
        if terminal_action != "none":
            break

    terminal_fallback_used = False
    if terminal_action == "none" and terminal_fallback:
        successful_records = [
            record
            for record in attempt_records.values()
            if (
                record.receipt.authority_valid
                and record.receipt.policy_accepted is True
                and record.receipt.execution_completed
                and record.result is not None
            )
        ]
        terminal_fallback_used = True
        if successful_records:
            submitted_attempt = successful_records[-1]
            terminal_action = "submit_sql"
            final_answer = ""
        else:
            terminal_action = "abstain"
            abstain_reason_code = "tool_budget_exhausted"
        _append_raw(
            raw_audit_path,
            {
                "event": "terminal_fallback_controller",
                "policy": "submit_most_recent_successful_authorized_attempt_or_abstain",
                "used": True,
                "submitted_attempt_id": (
                    submitted_attempt.receipt.attempt_id
                    if submitted_attempt is not None
                    else None
                ),
                "abstain_reason_code": abstain_reason_code,
            },
        )

    semantic_correct = False
    strict_answer_shape_correct = False
    authority_valid = all(authority_checks)
    policy_accepted: bool | None = None
    execution_completed = False
    policy_error_code = None
    evaluation_error_class: str | None = None
    candidate_sql: str | None = None
    if terminal_action == "submit_sql" and submitted_attempt is not None:
        candidate_sql = submitted_attempt.sql
        authority_valid = submitted_attempt.receipt.authority_valid
        policy_accepted = submitted_attempt.receipt.policy_accepted
        execution_completed = submitted_attempt.receipt.execution_completed
        policy_error_code = submitted_attempt.receipt.policy_error_code
        (
            semantic_correct,
            strict_answer_shape_correct,
            evaluation_error_class,
        ) = (
            _evaluate_submitted_attempt(
                task=task,
                attempt=submitted_attempt,
                executor=executor,
            )
        )
        if evaluation_error_class:
            outcome = f"evaluation_error:{evaluation_error_class}"
        elif semantic_correct:
            outcome = "semantic_correct"
        else:
            outcome = "semantic_incorrect"
    elif terminal_action == "abstain":
        outcome = f"abstained:{abstain_reason_code}"
    elif protocol_failure_code:
        outcome = f"tool_protocol_failure:{protocol_failure_code}"
    else:
        outcome = "no_terminal_submission"

    attempt_receipts = tuple(
        record.receipt for record in attempt_records.values()
    )
    attempt_chain_sha256 = hashlib.sha256(
        canonical_json_bytes(
            [asdict(receipt) for receipt in attempt_receipts]
        )
    ).hexdigest()

    _append_raw(
        raw_audit_path,
        {
            "event": "factorial_task_end",
            "task_id": task.task_id,
            "arm": arm,
            "outcome": outcome,
            "semantic_correct": semantic_correct,
            "strict_answer_shape_correct": strict_answer_shape_correct,
            "authority_valid": authority_valid,
            "policy_accepted": policy_accepted,
            "execution_completed": execution_completed,
            "unauthorized_observation": unauthorized_observation,
            "terminal_action": terminal_action,
            "submitted_attempt_id": (
                submitted_attempt.receipt.attempt_id
                if submitted_attempt is not None
                else None
            ),
            "abstain_reason_code": abstain_reason_code,
            "protocol_failure_code": protocol_failure_code,
            "candidate_sql": candidate_sql,
            "final_answer": final_answer,
            "attempt_receipts": [
                asdict(receipt) for receipt in attempt_receipts
            ],
            "messages": messages,
        },
    )
    raw_hash = sha256_file(raw_audit_path)
    return RunReceipt(
        task_id_sha256=sha256_text(task.task_id),
        arm=arm,
        seed=seed,
        semantic_correct=semantic_correct,
        strict_answer_shape_correct=strict_answer_shape_correct,
        authority_valid=authority_valid,
        policy_accepted=policy_accepted,
        execution_completed=execution_completed,
        unauthorized_observation=unauthorized_observation,
        outcome=outcome,
        terminal_action=terminal_action,
        submitted_attempt_id=(
            submitted_attempt.receipt.attempt_id
            if submitted_attempt is not None
            else None
        ),
        abstain_reason_code=abstain_reason_code,
        protocol_failure_code=protocol_failure_code,
        policy_error_code=policy_error_code,
        candidate_sql_sha256=(
            sha256_text(candidate_sql) if candidate_sql else None
        ),
        final_answer_sha256=(
            sha256_text(final_answer) if final_answer else None
        ),
        attempt_receipts=attempt_receipts,
        attempt_receipt_chain_sha256=attempt_chain_sha256,
        authority_binding_sha256=(
            authority_receipt.binding_sha256
            if authority_receipt is not None
            else None
        ),
        authority_epoch_ref_sha256=(
            authority_receipt.epoch_ref_sha256
            if authority_receipt is not None
            else None
        ),
        authority_snapshot_sha256=(
            authority_receipt.authority_snapshot_sha256
            if authority_receipt is not None
            else None
        ),
        model_calls=model_calls,
        tool_calls=tool_calls,
        schema_calls=schema_calls,
        sql_attempts=len(attempt_records),
        successful_sql_attempts=successful_sql_attempts,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        elapsed_ms=round(total_elapsed_ms, 3),
        system_fingerprint=system_fingerprint,
        raw_audit_sha256=raw_hash,
        terminal_fallback_used=terminal_fallback_used,
    )


def _aggregate(receipts: list[RunReceipt]) -> dict[str, Any]:
    by_arm: dict[str, list[RunReceipt]] = defaultdict(list)
    for receipt in receipts:
        by_arm[receipt.arm].append(receipt)
    arm_results = {}
    for arm, rows in sorted(by_arm.items()):
        outcomes = Counter(row.outcome for row in rows)
        arm_results[arm] = {
            "tasks": len(rows),
            "semantic_correct": sum(row.semantic_correct for row in rows),
            "strict_answer_shape_correct": sum(
                row.strict_answer_shape_correct for row in rows
            ),
            "authority_valid": sum(row.authority_valid for row in rows),
            "policy_accepted": sum(
                row.policy_accepted is True for row in rows
            ),
            "execution_completed": sum(
                row.execution_completed for row in rows
            ),
            "unauthorized_observation": sum(
                row.unauthorized_observation for row in rows
            ),
            "terminal_submissions": sum(
                row.terminal_action == "submit_sql" for row in rows
            ),
            "terminal_abstentions": sum(
                row.terminal_action == "abstain" for row in rows
            ),
            "missing_terminal_action": sum(
                row.terminal_action == "none" for row in rows
            ),
            "tasks_with_tool_calls": sum(row.tool_calls > 0 for row in rows),
            "tasks_with_schema_calls": sum(
                row.schema_calls > 0 for row in rows
            ),
            "tasks_with_sql": sum(row.sql_attempts > 0 for row in rows),
            "model_calls": sum(row.model_calls for row in rows),
            "tool_calls": sum(row.tool_calls for row in rows),
            "sql_attempts": sum(row.sql_attempts for row in rows),
            "successful_sql_attempts": sum(
                row.successful_sql_attempts for row in rows
            ),
            "prompt_tokens": sum(row.prompt_tokens for row in rows),
            "completion_tokens": sum(row.completion_tokens for row in rows),
            "elapsed_ms": round(sum(row.elapsed_ms for row in rows), 3),
            "outcomes": dict(sorted(outcomes.items())),
        }
    return arm_results


def _validate_frozen_design_contract(
    *,
    design: Mapping[str, Any],
    model_manifest_path: Path,
    authority_manifest_path: Path,
    max_model_turns: int,
    max_sql_attempts: int,
    max_tokens: int,
) -> None:
    if design.get("model_manifest_sha256") != sha256_file(
        model_manifest_path
    ):
        raise FactorialError("model manifest does not match frozen design")
    if design.get("authority_manifest_sha256") != sha256_file(
        authority_manifest_path
    ):
        raise FactorialError(
            "authority manifest does not match frozen design"
        )
    prompt_contract = design.get("prompt_contract") or {}
    if prompt_contract.get("base_system_prompt_sha256") != sha256_text(
        BASE_SYSTEM_PROMPT
    ):
        raise FactorialError("base system prompt diverges from frozen design")
    frozen_artifacts = prompt_contract.get("arm_artifacts") or {}
    for arm, artifact in ARM_PROMPTS.items():
        if (
            (frozen_artifacts.get(arm) or {}).get("artifact_sha256")
            != sha256_text(artifact)
        ):
            raise FactorialError(
                f"{arm}: procedure artifact diverges from frozen design"
            )
    tool_contract = design.get("tool_contract") or {}
    if tool_contract.get("tools_sha256") != hashlib.sha256(
        canonical_json_bytes(TOOLS)
    ).hexdigest():
        raise FactorialError("tool schema diverges from frozen design")
    frozen_limits = design.get("limits") or {}
    requested_limits = {
        "max_model_turns": max_model_turns,
        "max_sql_attempts": max_sql_attempts,
        "max_generated_tokens_per_call": max_tokens,
    }
    for name, value in requested_limits.items():
        if frozen_limits.get(name) != value:
            raise FactorialError(
                f"{name}={value} diverges from frozen design"
            )


def run_factorial(
    *,
    source_root: Path,
    cohort_manifest_path: Path,
    dataset_manifest_path: Path,
    design_manifest_path: Path,
    model_manifest_path: Path,
    authority_manifest_path: Path,
    fold_id: str,
    arms: list[str],
    dsn_template: str,
    endpoint: str,
    raw_audit_dir: Path,
    output_path: Path,
    max_model_turns: int,
    max_sql_attempts: int,
    max_tokens: int,
    request_timeout_seconds: int,
    task_limit: int | None = None,
) -> dict[str, Any]:
    _require_external_raw_audit_dir(raw_audit_dir)
    design = json.loads(design_manifest_path.read_text(encoding="utf-8"))
    model_manifest = json.loads(
        model_manifest_path.read_text(encoding="utf-8")
    )
    _validate_frozen_design_contract(
        design=design,
        model_manifest_path=model_manifest_path,
        authority_manifest_path=authority_manifest_path,
        max_model_turns=max_model_turns,
        max_sql_attempts=max_sql_attempts,
        max_tokens=max_tokens,
    )
    fold = next(
        (item for item in design["folds"] if item["fold_id"] == fold_id),
        None,
    )
    if fold is None:
        raise FactorialError(f"unknown fold: {fold_id}")
    unknown_arms = set(arms) - set(ARM_PROMPTS)
    if unknown_arms:
        raise FactorialError(f"unknown arms: {sorted(unknown_arms)}")
    declared_arms = design.get("arm_contracts", {})
    if set(arms) - set(declared_arms):
        raise FactorialError("requested arms are absent from frozen design")
    if len(set(arms)) != len(arms):
        raise FactorialError("requested arms must be unique")
    if task_limit is not None and task_limit <= 0:
        raise FactorialError("task_limit must be a positive integer")

    resolver = PinnedTaskResolver(
        source_root=source_root,
        manifest_path=cohort_manifest_path,
        dataset_manifest_path=dataset_manifest_path,
    )
    selected_task_ids = fold["mechanics_smoke_task_ids"]
    if task_limit is not None and task_limit > len(selected_task_ids):
        raise FactorialError(
            "task_limit exceeds the frozen pilot selection"
        )
    executed_task_ids = (
        selected_task_ids[:task_limit]
        if task_limit is not None
        else selected_task_ids
    )
    task_database = fold["visible_selection_database_family"]
    request_model_id = model_manifest.get("request_model_id")
    if not isinstance(request_model_id, str) or not request_model_id:
        raise FactorialError(
            "model manifest requires a non-empty request_model_id"
        )
    api = ChatAPI(
        endpoint=endpoint,
        request_model_id=request_model_id,
        timeout_seconds=request_timeout_seconds,
        max_tokens=max_tokens,
    )
    authority_store = StaticAuthorityEpochStore.from_path(
        authority_manifest_path
    )
    limits = AgentLimits(
        max_model_turns=max_model_turns,
        max_sql_attempts=max_sql_attempts,
    )
    receipts: list[RunReceipt] = []
    arm_order_receipts: dict[str, list[str]] = {}
    for task_id in executed_task_ids:
        task = resolver.resolve(task_id)
        if task.database != task_database:
            raise FactorialError(
                f"{task_id}: task database violates pilot selection role"
            )
        seed = _task_seed(task.task_id, int(design["seed"]))
        arm_order = _frozen_arm_order(
            fold=fold,
            task_id=task_id,
            arms=arms,
        )
        arm_order_receipts[sha256_text(task.task_id)] = arm_order
        for arm in arm_order:
            raw_path = (
                raw_audit_dir
                / fold_id
                / arm
                / f"{sha256_text(task.task_id)}.jsonl"
            )
            if raw_path.exists():
                raise FactorialError(
                    f"raw audit path already exists; refuse overwrite: {raw_path}"
                )
            authority = GovernanceAuthority(
                governance_scope=AUTHORITY_SCOPE,
                authorization_epoch_ref=AUTHORIZATION_EPOCH_REF,
                user_id=AUTHORITY_USER_ID,
                team_id=AUTHORITY_TEAM_ID,
                virtual_key_id=AUTHORITY_VIRTUAL_KEY_ID,
            )
            authority_receipt = authority_store.validate(
                database=task.database,
                governance_scope=authority.governance_scope,
                authorization_epoch_ref=(
                    authority.authorization_epoch_ref
                ),
                user_id=authority.user_id,
                team_id=authority.team_id,
                virtual_key_id=authority.virtual_key_id,
            )
            executor = GovernedPostgresExecutor(
                dsn=dsn_template.format(database=task.database),
                authority=authority,
                audit_path=raw_path,
            )
            receipt = run_agent(
                task=task,
                arm=arm,
                seed=seed,
                api=api,
                executor=executor,
                limits=limits,
                raw_audit_path=raw_path,
                authority_receipt=authority_receipt,
            )
            receipts.append(receipt)

    task_receipts = [asdict(receipt) for receipt in receipts]
    result = {
        "schema_version": SCHEMA_VERSION,
        "experiment_date": "2026-07-30",
        "classification": "mechanics_smoke",
        "fold_id": fold_id,
        "stage": "visible_selection_mechanics_smoke",
        "run_scope": (
            "one_task_smoke"
            if len(executed_task_ids) == 1
            else "four_task_pilot"
            if len(executed_task_ids) == 4
            else "limited_mechanics_smoke"
        ),
        "selected_task_count": len(selected_task_ids),
        "executed_task_count": len(executed_task_ids),
        "task_count": len(executed_task_ids),
        "trajectory_count": len(receipts),
        "arms": arms,
        "arm_order_by_task_sha256": arm_order_receipts,
        "arm_contracts": {
            arm: declared_arms[arm] for arm in arms
        },
        "prompt_receipts": {
            "base_system_sha256": sha256_text(BASE_SYSTEM_PROMPT),
            "arm_addition_sha256": {
                arm: sha256_text(ARM_PROMPTS[arm]) for arm in arms
            },
            "tool_schema_sha256": hashlib.sha256(
                canonical_json_bytes(TOOLS)
            ).hexdigest(),
        },
        "protocol_remediation": {
            "id": "explicit_terminal_state_and_terminal_only-v1",
            "applies_identically_across_arms": True,
            "transition": (
                "when accepted SQL attempt count reaches max_sql_attempts, "
                "the attempt observation declares zero remaining SQL "
                "attempts, an arm-independent protocol-controller message "
                "requires one terminal native call, and the next model "
                "request offers only submit_sql and abstain"
            ),
            "terminal_state_message_sha256": sha256_text(
                TERMINAL_STATE_CONTROL_MESSAGE
            ),
            "terminal_tools": sorted(TERMINAL_TOOL_NAMES),
            "base_prompt_changed": False,
            "arm_artifacts_changed": False,
            "tool_schemas_changed": False,
            "model_changed": False,
            "task_selection_changed": False,
            "authority_contract_changed": False,
        },
        "source_receipts": {
            "cohort_manifest_sha256": sha256_file(cohort_manifest_path),
            "dataset_manifest_sha256": sha256_file(dataset_manifest_path),
            "design_manifest_sha256": sha256_file(design_manifest_path),
            "model_manifest_sha256": sha256_file(model_manifest_path),
            "authority_manifest_sha256": sha256_file(
                authority_manifest_path
            ),
            "runner_sha256": sha256_file(Path(__file__).resolve()),
        },
        "model": {
            "model_id": model_manifest["model_id"],
            "request_model_id": request_model_id,
            "revision": model_manifest["revision"],
            "snapshot_identity_sha256": model_manifest[
                "snapshot_identity_sha256"
            ],
            "runtime": model_manifest["runtime"],
            "system_fingerprints": sorted(
                {
                    receipt.system_fingerprint
                    for receipt in receipts
                    if receipt.system_fingerprint
                }
            ),
        },
        "authority": {
            "governance_scope": AUTHORITY_SCOPE,
            "binding_sha256": sorted(
                {
                    receipt.authority_binding_sha256
                    for receipt in receipts
                    if receipt.authority_binding_sha256
                }
            ),
            "epoch_ref_sha256": sorted(
                {
                    receipt.authority_epoch_ref_sha256
                    for receipt in receipts
                    if receipt.authority_epoch_ref_sha256
                }
            ),
            "snapshot_sha256": authority_store.snapshot_sha256,
            "exact_current_epoch_match_enforced": True,
        },
        "limits": {
            "max_model_turns": max_model_turns,
            "max_sql_attempts": max_sql_attempts,
            "max_tokens_per_model_call": max_tokens,
            "request_timeout_seconds": request_timeout_seconds,
            "task_limit": task_limit,
        },
        "aggregate": _aggregate(receipts),
        "task_receipts": task_receipts,
        "claim_boundary": {
            "hidden_test_touched": False,
            "trace_mined_skill_tested": False,
            "causal_skill_benefit_estimated": False,
            "adequate_sample_for_quality_claim": False,
            "frontier_model_evaluated": False,
            "tool_loop_empirically_exercised": True,
        },
        "raw_data_committed": False,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--cohort-manifest", type=Path, required=True)
    parser.add_argument("--dataset-manifest", type=Path, required=True)
    parser.add_argument("--design-manifest", type=Path, required=True)
    parser.add_argument("--model-manifest", type=Path, required=True)
    parser.add_argument("--authority-manifest", type=Path, required=True)
    parser.add_argument("--fold-id", default="fold-0")
    parser.add_argument(
        "--arms",
        default="no_skill,unrelated_formatting_placebo,"
        "expert_schema_navigation_seed",
    )
    parser.add_argument("--dsn-template", required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:18080")
    parser.add_argument("--raw-audit-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--max-model-turns",
        type=int,
        default=FROZEN_LIMITS["max_model_turns"],
    )
    parser.add_argument(
        "--max-sql-attempts",
        type=int,
        default=FROZEN_LIMITS["max_sql_attempts"],
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=FROZEN_LIMITS["max_generated_tokens_per_call"],
    )
    parser.add_argument(
        "--request-timeout-seconds",
        type=int,
        default=FROZEN_LIMITS["model_wall_seconds"],
    )
    parser.add_argument("--task-limit", type=int)
    args = parser.parse_args()
    arms = [arm.strip() for arm in args.arms.split(",") if arm.strip()]
    result = run_factorial(
        source_root=args.source_root,
        cohort_manifest_path=args.cohort_manifest,
        dataset_manifest_path=args.dataset_manifest,
        design_manifest_path=args.design_manifest,
        model_manifest_path=args.model_manifest,
        authority_manifest_path=args.authority_manifest,
        fold_id=args.fold_id,
        arms=arms,
        dsn_template=args.dsn_template,
        endpoint=args.endpoint,
        raw_audit_dir=args.raw_audit_dir,
        output_path=args.output,
        max_model_turns=args.max_model_turns,
        max_sql_attempts=args.max_sql_attempts,
        max_tokens=args.max_tokens,
        request_timeout_seconds=args.request_timeout_seconds,
        task_limit=args.task_limit,
    )
    print(
        json.dumps(
            {
                "status": "ok",
                "output": str(args.output),
                "task_count": result["task_count"],
                "trajectory_count": result["trajectory_count"],
                "aggregate": result["aggregate"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
