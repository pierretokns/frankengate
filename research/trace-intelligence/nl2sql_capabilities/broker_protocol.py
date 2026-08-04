"""Closed, content-bounded IPC DTOs for governed NL2SQL broker tools.

The module defines bytes-on-the-wire behavior only. It has no socket, database,
authority-service, policy, attempt-store, or evaluator access.
"""

from __future__ import annotations

from dataclasses import dataclass
import hmac
import json
import re
import struct
from typing import Any, Mapping

from .dto import (
    DTOValidationError,
    MAX_FRAME_BYTES,
    MAX_SIGNED_INTEGER,
    canonical_json_bytes,
    decode_base64url,
)


TOOL_REQUEST_SCHEMA_VERSION = "fg-tool-request-v1"
TOOL_RESPONSE_SCHEMA_VERSION = "fg-tool-response-v1"
OPERATIONS = frozenset(
    {"describe_schema", "execute_sql", "submit_sql", "abstain"}
)
ABSTAIN_REASON_CODES = frozenset(
    {
        "cannot_answer_with_authorized_data",
        "insufficient_schema",
        "tool_budget_exhausted",
        "unsafe_request",
        "other",
    }
)
ERROR_STATUSES = frozenset(
    {
        "authority_denied",
        "policy_denied",
        "database_error",
        "resource_limit",
        "invalid_arguments",
    }
)
STATUSES = frozenset({"ok", "accepted", *ERROR_STATUSES})

MAX_SQL_BYTES = 1024 * 1024
MAX_TABLES = 1024
MAX_COLUMNS = 2048
MAX_PREVIEW_ROWS = 10_000
MAX_ARRAY_DEPTH = 16
MAX_TEXT_BYTES = 4 * 1024 * 1024

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_CODE_RE = re.compile(r"^[a-z][a-z0-9_]{0,127}$")
_INTEGER_TEXT_RE = re.compile(r"^(?:0|-[1-9][0-9]*|[1-9][0-9]*)$")
_DECIMAL_TEXT_RE = re.compile(
    r"^(?:0|-[1-9][0-9]*|[1-9][0-9]*)(?:\.[0-9]*[1-9])?$"
)
_FLOAT_HEX_RE = re.compile(
    r"^-?0x(?:0|[1-9a-f][0-9a-f]*)(?:\.[0-9a-f]*[1-9a-f])?p[+-][0-9]+$"
)
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
_BASE64URL_OR_EMPTY_RE = re.compile(r"^[A-Za-z0-9_-]*$")


class BrokerProtocolError(ValueError):
    """A broker IPC frame or DTO violates the closed protocol."""


def _wrap_validation(callable_value: Any, *args: Any, **kwargs: Any) -> Any:
    try:
        return callable_value(*args, **kwargs)
    except DTOValidationError as exc:
        raise BrokerProtocolError(str(exc)) from exc


def _reject_duplicate_members(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise BrokerProtocolError(f"JSON object has duplicate field {key!r}")
        result[key] = value
    return result


def _reject_float(raw: str) -> Any:
    raise BrokerProtocolError(f"JSON float is forbidden: {raw}")


def _reject_constant(raw: str) -> Any:
    raise BrokerProtocolError(f"JSON constant is forbidden: {raw}")


def _decode_json_bytes(value: bytes) -> Any:
    try:
        decoded = json.loads(
            value.decode("utf-8"),
            object_pairs_hook=_reject_duplicate_members,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except UnicodeDecodeError as exc:
        raise BrokerProtocolError("frame body is not valid UTF-8") from exc
    except json.JSONDecodeError as exc:
        raise BrokerProtocolError("frame body is not valid JSON") from exc
    _wrap_validation(canonical_json_bytes, decoded)
    return decoded


def encode_frame(value: Any) -> bytes:
    """Encode one value as a four-byte big-endian length plus canonical JSON."""

    if hasattr(value, "to_dict") and callable(value.to_dict):
        value = value.to_dict()
    body = _wrap_validation(canonical_json_bytes, value)
    if not body or len(body) > MAX_FRAME_BYTES:
        raise BrokerProtocolError(
            f"frame body must contain 1 to {MAX_FRAME_BYTES} bytes"
        )
    return struct.pack(">I", len(body)) + body


def decode_frame(frame: bytes) -> Any:
    """Decode exactly one complete frame; short/trailing bytes are rejected."""

    if type(frame) is not bytes or len(frame) < 4:
        raise BrokerProtocolError("frame must contain a four-byte length prefix")
    declared_size = struct.unpack(">I", frame[:4])[0]
    if declared_size < 1 or declared_size > MAX_FRAME_BYTES:
        raise BrokerProtocolError(
            f"declared frame size must be from 1 to {MAX_FRAME_BYTES}"
        )
    actual_size = len(frame) - 4
    if actual_size != declared_size:
        raise BrokerProtocolError(
            "frame body length does not match its declared size"
        )
    return _decode_json_bytes(frame[4:])


def _closed_object(
    value: Any, *, path: str, required: frozenset[str]
) -> dict[str, Any]:
    if type(value) is not dict:
        raise BrokerProtocolError(f"{path} must be an object")
    keys = set(value)
    unknown = keys - required
    missing = required - keys
    if unknown:
        rendered = ", ".join(sorted(repr(key) for key in unknown))
        raise BrokerProtocolError(f"{path} has unknown field(s): {rendered}")
    if missing:
        rendered = ", ".join(sorted(missing))
        raise BrokerProtocolError(f"{path} is missing field(s): {rendered}")
    return value


def _string(
    value: Any,
    *,
    path: str,
    maximum_bytes: int,
    allow_empty: bool = False,
) -> str:
    if type(value) is not str:
        raise BrokerProtocolError(f"{path} must be a string")
    try:
        encoded = value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise BrokerProtocolError(f"{path} is not valid Unicode") from exc
    if not allow_empty and not encoded:
        raise BrokerProtocolError(f"{path} must not be empty")
    if len(encoded) > maximum_bytes:
        raise BrokerProtocolError(
            f"{path} exceeds its {maximum_bytes}-byte limit"
        )
    return value


def _literal(value: Any, expected: str, *, path: str) -> str:
    parsed = _string(value, path=path, maximum_bytes=128)
    if parsed != expected:
        raise BrokerProtocolError(f"{path} must equal {expected!r}")
    return parsed


def _integer(
    value: Any, *, path: str, minimum: int, maximum: int
) -> int:
    if type(value) is not int:
        raise BrokerProtocolError(f"{path} must be an integer")
    if value < minimum or value > maximum:
        raise BrokerProtocolError(
            f"{path} must be between {minimum} and {maximum}"
        )
    return value


def _sha256(value: Any, *, path: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise BrokerProtocolError(
            f"{path} must be a lowercase 64-character SHA-256 digest"
        )
    return value


def _opaque_token(value: Any, *, path: str, byte_count: int) -> str:
    parsed = _string(value, path=path, maximum_bytes=2048)
    _wrap_validation(
        decode_base64url, parsed, expected_nbytes=byte_count
    )
    return parsed


@dataclass(frozen=True)
class ToolRequestDTO:
    schema_version: str
    request_nonce: str
    database_handle: str
    operation: str
    sql: str | None = None
    attempt_id: str | None = None
    reason_code: str | None = None

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ToolRequestDTO":
        item = _closed_object(
            value,
            path="tool_request",
            required=frozenset(
                {
                    "schema_version",
                    "request_nonce",
                    "database_handle",
                    "operation",
                    "arguments",
                }
            ),
        )
        operation = _string(
            item["operation"], path="operation", maximum_bytes=64
        )
        if operation not in OPERATIONS:
            raise BrokerProtocolError(f"unsupported operation {operation!r}")

        arguments: dict[str, Any]
        sql = None
        attempt_id = None
        reason_code = None
        if operation == "describe_schema":
            arguments = _closed_object(
                item["arguments"],
                path="arguments",
                required=frozenset(),
            )
        elif operation == "execute_sql":
            arguments = _closed_object(
                item["arguments"],
                path="arguments",
                required=frozenset({"sql"}),
            )
            sql = _string(
                arguments["sql"],
                path="arguments.sql",
                maximum_bytes=MAX_SQL_BYTES,
            )
            if not sql.strip():
                raise BrokerProtocolError(
                    "arguments.sql must contain a non-whitespace query"
                )
            if "\0" in sql:
                raise BrokerProtocolError("arguments.sql must not contain NUL")
        elif operation == "submit_sql":
            arguments = _closed_object(
                item["arguments"],
                path="arguments",
                required=frozenset({"attempt_id"}),
            )
            attempt_id = _opaque_token(
                arguments["attempt_id"],
                path="arguments.attempt_id",
                byte_count=24,
            )
        else:
            arguments = _closed_object(
                item["arguments"],
                path="arguments",
                required=frozenset({"reason_code"}),
            )
            reason_code = _string(
                arguments["reason_code"],
                path="arguments.reason_code",
                maximum_bytes=64,
            )
            if reason_code not in ABSTAIN_REASON_CODES:
                raise BrokerProtocolError(
                    "arguments.reason_code is not an allowed abstention code"
                )

        return cls(
            schema_version=_literal(
                item["schema_version"],
                TOOL_REQUEST_SCHEMA_VERSION,
                path="schema_version",
            ),
            request_nonce=_opaque_token(
                item["request_nonce"],
                path="request_nonce",
                byte_count=16,
            ),
            database_handle=_opaque_token(
                item["database_handle"],
                path="database_handle",
                byte_count=32,
            ),
            operation=operation,
            sql=sql,
            attempt_id=attempt_id,
            reason_code=reason_code,
        )

    @classmethod
    def from_frame(cls, frame: bytes) -> "ToolRequestDTO":
        return cls.from_dict(decode_frame(frame))

    def to_dict(self) -> dict[str, Any]:
        if self.operation == "describe_schema":
            arguments: dict[str, Any] = {}
        elif self.operation == "execute_sql":
            arguments = {"sql": self.sql}
        elif self.operation == "submit_sql":
            arguments = {"attempt_id": self.attempt_id}
        else:
            arguments = {"reason_code": self.reason_code}
        return {
            "schema_version": self.schema_version,
            "request_nonce": self.request_nonce,
            "database_handle": self.database_handle,
            "operation": self.operation,
            "arguments": arguments,
        }

    def to_frame(self) -> bytes:
        return encode_frame(self.to_dict())


def _remaining(value: Any) -> dict[str, int]:
    item = _closed_object(
        value,
        path="remaining",
        required=frozenset({"schema_calls", "sql_attempts", "model_turns"}),
    )
    return {
        name: _integer(
            item[name], path=f"remaining.{name}", minimum=0, maximum=64
        )
        for name in ("schema_calls", "sql_attempts", "model_turns")
    }


def _describe_observation(value: Any) -> dict[str, Any]:
    item = _closed_object(
        value,
        path="observation",
        required=frozenset({"tables", "catalog_sha256"}),
    )
    tables = item["tables"]
    if type(tables) is not dict:
        raise BrokerProtocolError("observation.tables must be an object")
    if len(tables) > MAX_TABLES:
        raise BrokerProtocolError(
            f"observation.tables exceeds {MAX_TABLES} entries"
        )
    normalized_tables: dict[str, list[str]] = {}
    total_columns = 0
    for table_name, columns in tables.items():
        table = _string(
            table_name,
            path="observation.tables key",
            maximum_bytes=512,
        )
        if type(columns) is not list:
            raise BrokerProtocolError(
                f"observation.tables.{table} must be an array"
            )
        if len(columns) > MAX_COLUMNS:
            raise BrokerProtocolError(
                f"observation.tables.{table} exceeds {MAX_COLUMNS} columns"
            )
        total_columns += len(columns)
        if total_columns > MAX_TABLES * MAX_COLUMNS:
            raise BrokerProtocolError(
                "observation.tables contains too many total columns"
            )
        normalized_tables[table] = [
            _string(
                column,
                path=f"observation.tables.{table}[{index}]",
                maximum_bytes=512,
            )
            for index, column in enumerate(columns)
        ]
    return {
        "tables": normalized_tables,
        "catalog_sha256": _sha256(
            item["catalog_sha256"],
            path="observation.catalog_sha256",
        ),
    }


def _base64url_or_empty(value: Any, *, path: str) -> str:
    parsed = _string(
        value, path=path, maximum_bytes=MAX_TEXT_BYTES, allow_empty=True
    )
    if _BASE64URL_OR_EMPTY_RE.fullmatch(parsed) is None or len(parsed) % 4 == 1:
        raise BrokerProtocolError(f"{path} must be unpadded base64url")
    if parsed:
        _wrap_validation(decode_base64url, parsed)
    return parsed


def _typed_cell(value: Any, *, path: str, depth: int = 0) -> dict[str, Any]:
    if depth > MAX_ARRAY_DEPTH:
        raise BrokerProtocolError(f"{path} exceeds typed-array depth limit")
    item = _closed_object(
        value, path=path, required=frozenset({"kind", "value"})
    )
    kind = _string(
        item["kind"], path=f"{path}.kind", maximum_bytes=32
    )
    cell_value = item["value"]

    if kind == "null":
        if cell_value is not None:
            raise BrokerProtocolError(f"{path}.value must be null")
    elif kind == "bool":
        if type(cell_value) is not bool:
            raise BrokerProtocolError(f"{path}.value must be a boolean")
    elif kind == "int":
        text = _string(
            cell_value, path=f"{path}.value", maximum_bytes=128
        )
        if _INTEGER_TEXT_RE.fullmatch(text) is None:
            raise BrokerProtocolError(
                f"{path}.value must be a canonical base-10 integer"
            )
    elif kind == "decimal":
        text = _string(
            cell_value, path=f"{path}.value", maximum_bytes=1024
        )
        if _DECIMAL_TEXT_RE.fullmatch(text) is None:
            raise BrokerProtocolError(
                f"{path}.value must be a canonical decimal"
            )
    elif kind == "float":
        text = _string(
            cell_value, path=f"{path}.value", maximum_bytes=256
        )
        if text not in {"nan", "inf", "-inf"} and _FLOAT_HEX_RE.fullmatch(
            text
        ) is None:
            raise BrokerProtocolError(
                f"{path}.value must be an IEEE-754 hexadecimal string"
            )
    elif kind in {
        "text",
        "date",
        "time",
        "timestamp",
        "timestamptz",
    }:
        _string(
            cell_value,
            path=f"{path}.value",
            maximum_bytes=MAX_TEXT_BYTES,
            allow_empty=True,
        )
    elif kind == "bytes":
        _base64url_or_empty(cell_value, path=f"{path}.value")
    elif kind == "uuid":
        text = _string(
            cell_value, path=f"{path}.value", maximum_bytes=36
        )
        if _UUID_RE.fullmatch(text) is None:
            raise BrokerProtocolError(
                f"{path}.value must be a lowercase canonical UUID"
            )
    elif kind == "json":
        text = _string(
            cell_value, path=f"{path}.value", maximum_bytes=MAX_TEXT_BYTES
        )
        decoded = _decode_json_bytes(text.encode("utf-8"))
        canonical = _wrap_validation(canonical_json_bytes, decoded)
        if not hmac.compare_digest(canonical, text.encode("utf-8")):
            raise BrokerProtocolError(
                f"{path}.value must contain canonical JSON"
            )
    elif kind == "array":
        if type(cell_value) is not list:
            raise BrokerProtocolError(f"{path}.value must be an array")
        if len(cell_value) > MAX_PREVIEW_ROWS:
            raise BrokerProtocolError(
                f"{path}.value exceeds the array element limit"
            )
        cell_value = [
            _typed_cell(
                child,
                path=f"{path}.value[{index}]",
                depth=depth + 1,
            )
            for index, child in enumerate(cell_value)
        ]
    else:
        raise BrokerProtocolError(f"{path}.kind is not supported")
    return {"kind": kind, "value": cell_value}


def _execute_observation(value: Any) -> dict[str, Any]:
    item = _closed_object(
        value,
        path="observation",
        required=frozenset(
            {
                "columns",
                "rows",
                "row_count",
                "preview_truncated",
                "result_sha256",
            }
        ),
    )
    columns = item["columns"]
    if type(columns) is not list or len(columns) > MAX_COLUMNS:
        raise BrokerProtocolError(
            f"observation.columns must contain at most {MAX_COLUMNS} entries"
        )
    normalized_columns = [
        _string(
            column,
            path=f"observation.columns[{index}]",
            maximum_bytes=512,
            allow_empty=True,
        )
        for index, column in enumerate(columns)
    ]
    rows = item["rows"]
    if type(rows) is not list:
        raise BrokerProtocolError("observation.rows must be an array")
    if len(rows) > MAX_PREVIEW_ROWS:
        raise BrokerProtocolError(
            f"observation.rows exceeds {MAX_PREVIEW_ROWS} entries"
        )
    normalized_rows: list[list[dict[str, Any]]] = []
    for row_index, row in enumerate(rows):
        if type(row) is not list:
            raise BrokerProtocolError(
                f"observation.rows[{row_index}] must be an array"
            )
        if len(row) != len(normalized_columns):
            raise BrokerProtocolError(
                f"observation.rows[{row_index}] width does not match columns"
            )
        normalized_rows.append(
            [
                _typed_cell(
                    cell,
                    path=f"observation.rows[{row_index}][{column_index}]",
                )
                for column_index, cell in enumerate(row)
            ]
        )
    row_count = _integer(
        item["row_count"],
        path="observation.row_count",
        minimum=0,
        maximum=MAX_SIGNED_INTEGER,
    )
    if type(item["preview_truncated"]) is not bool:
        raise BrokerProtocolError(
            "observation.preview_truncated must be a boolean"
        )
    preview_truncated = item["preview_truncated"]
    if (
        not preview_truncated
        and row_count != len(normalized_rows)
        or preview_truncated
        and row_count < len(normalized_rows)
    ):
        raise BrokerProtocolError(
            "observation.row_count is inconsistent with the preview"
        )
    return {
        "columns": normalized_columns,
        "rows": normalized_rows,
        "row_count": row_count,
        "preview_truncated": preview_truncated,
        "result_sha256": _sha256(
            item["result_sha256"], path="observation.result_sha256"
        ),
    }


def _validate_response(
    value: Any, *, request: ToolRequestDTO
) -> dict[str, Any]:
    if type(value) is not dict:
        raise BrokerProtocolError("tool_response must be an object")
    status = value.get("status")
    if type(status) is not str or status not in STATUSES:
        raise BrokerProtocolError("tool_response.status is not allowed")

    if status in ERROR_STATUSES:
        item = _closed_object(
            value,
            path="tool_response",
            required=frozenset(
                {
                    "schema_version",
                    "request_nonce",
                    "status",
                    "code",
                    "message_sha256",
                    "remaining",
                }
            ),
        )
        code = _string(
            item["code"], path="tool_response.code", maximum_bytes=128
        )
        if _CODE_RE.fullmatch(code) is None:
            raise BrokerProtocolError(
                "tool_response.code must be a stable lowercase code"
            )
        normalized: dict[str, Any] = {
            "schema_version": _literal(
                item["schema_version"],
                TOOL_RESPONSE_SCHEMA_VERSION,
                path="tool_response.schema_version",
            ),
            "request_nonce": _opaque_token(
                item["request_nonce"],
                path="tool_response.request_nonce",
                byte_count=16,
            ),
            "status": status,
            "code": code,
            "message_sha256": _sha256(
                item["message_sha256"],
                path="tool_response.message_sha256",
            ),
            "remaining": _remaining(item["remaining"]),
        }
    elif request.operation == "describe_schema" and status == "ok":
        item = _closed_object(
            value,
            path="tool_response",
            required=frozenset(
                {
                    "schema_version",
                    "request_nonce",
                    "status",
                    "observation",
                    "authority_receipt_sha256",
                    "remaining",
                }
            ),
        )
        normalized = {
            "schema_version": _literal(
                item["schema_version"],
                TOOL_RESPONSE_SCHEMA_VERSION,
                path="tool_response.schema_version",
            ),
            "request_nonce": _opaque_token(
                item["request_nonce"],
                path="tool_response.request_nonce",
                byte_count=16,
            ),
            "status": status,
            "observation": _describe_observation(item["observation"]),
            "authority_receipt_sha256": _sha256(
                item["authority_receipt_sha256"],
                path="tool_response.authority_receipt_sha256",
            ),
            "remaining": _remaining(item["remaining"]),
        }
    elif request.operation == "execute_sql" and status == "ok":
        item = _closed_object(
            value,
            path="tool_response",
            required=frozenset(
                {
                    "schema_version",
                    "request_nonce",
                    "status",
                    "attempt_id",
                    "observation",
                    "authority_receipt_sha256",
                    "policy_receipt_sha256",
                    "remaining",
                }
            ),
        )
        normalized = {
            "schema_version": _literal(
                item["schema_version"],
                TOOL_RESPONSE_SCHEMA_VERSION,
                path="tool_response.schema_version",
            ),
            "request_nonce": _opaque_token(
                item["request_nonce"],
                path="tool_response.request_nonce",
                byte_count=16,
            ),
            "status": status,
            "attempt_id": _opaque_token(
                item["attempt_id"],
                path="tool_response.attempt_id",
                byte_count=24,
            ),
            "observation": _execute_observation(item["observation"]),
            "authority_receipt_sha256": _sha256(
                item["authority_receipt_sha256"],
                path="tool_response.authority_receipt_sha256",
            ),
            "policy_receipt_sha256": _sha256(
                item["policy_receipt_sha256"],
                path="tool_response.policy_receipt_sha256",
            ),
            "remaining": _remaining(item["remaining"]),
        }
    elif request.operation == "submit_sql" and status == "accepted":
        item = _closed_object(
            value,
            path="tool_response",
            required=frozenset(
                {
                    "schema_version",
                    "request_nonce",
                    "status",
                    "terminal",
                    "submission_receipt_sha256",
                }
            ),
        )
        if item["terminal"] is not True:
            raise BrokerProtocolError("tool_response.terminal must be true")
        normalized = {
            "schema_version": _literal(
                item["schema_version"],
                TOOL_RESPONSE_SCHEMA_VERSION,
                path="tool_response.schema_version",
            ),
            "request_nonce": _opaque_token(
                item["request_nonce"],
                path="tool_response.request_nonce",
                byte_count=16,
            ),
            "status": status,
            "terminal": True,
            "submission_receipt_sha256": _sha256(
                item["submission_receipt_sha256"],
                path="tool_response.submission_receipt_sha256",
            ),
        }
    elif request.operation == "abstain" and status == "accepted":
        item = _closed_object(
            value,
            path="tool_response",
            required=frozenset(
                {
                    "schema_version",
                    "request_nonce",
                    "status",
                    "terminal",
                    "abstention_receipt_sha256",
                }
            ),
        )
        if item["terminal"] is not True:
            raise BrokerProtocolError("tool_response.terminal must be true")
        normalized = {
            "schema_version": _literal(
                item["schema_version"],
                TOOL_RESPONSE_SCHEMA_VERSION,
                path="tool_response.schema_version",
            ),
            "request_nonce": _opaque_token(
                item["request_nonce"],
                path="tool_response.request_nonce",
                byte_count=16,
            ),
            "status": status,
            "terminal": True,
            "abstention_receipt_sha256": _sha256(
                item["abstention_receipt_sha256"],
                path="tool_response.abstention_receipt_sha256",
            ),
        }
    else:
        raise BrokerProtocolError(
            f"status {status!r} is invalid for {request.operation!r}"
        )

    if not hmac.compare_digest(
        normalized["request_nonce"], request.request_nonce
    ):
        raise BrokerProtocolError(
            "response request nonce does not match the request"
        )
    return normalized


@dataclass(frozen=True)
class ToolResponseDTO:
    operation: str
    status: str
    request_nonce: str
    _canonical_payload: bytes

    @classmethod
    def from_dict(
        cls, value: Mapping[str, Any], *, request: ToolRequestDTO
    ) -> "ToolResponseDTO":
        if type(request) is not ToolRequestDTO:
            raise BrokerProtocolError(
                "response validation requires its exact ToolRequestDTO"
            )
        normalized = _validate_response(value, request=request)
        canonical = _wrap_validation(canonical_json_bytes, normalized)
        if len(canonical) > MAX_FRAME_BYTES:
            raise BrokerProtocolError("tool response exceeds frame limit")
        return cls(
            operation=request.operation,
            status=normalized["status"],
            request_nonce=normalized["request_nonce"],
            _canonical_payload=canonical,
        )

    @classmethod
    def from_frame(
        cls, frame: bytes, *, request: ToolRequestDTO
    ) -> "ToolResponseDTO":
        return cls.from_dict(decode_frame(frame), request=request)

    def to_dict(self) -> dict[str, Any]:
        decoded = _decode_json_bytes(self._canonical_payload)
        if type(decoded) is not dict:
            raise BrokerProtocolError("stored response payload is not an object")
        return decoded

    def to_frame(self) -> bytes:
        return encode_frame(self.to_dict())
