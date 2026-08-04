"""Deterministic NL2SQL evaluation over sealed, already-executed evidence.

This module is deliberately incapable of executing SQL.  It accepts verified
candidate and gold result evidence, compares their canonical typed rows, and
emits a content-minimized receipt.  Signature verification and the read-only
candidate-execution counter are injected capabilities; neither exposes a
database or candidate-query API.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
import hashlib
import hmac
import json
import math
import re
from typing import Any, Callable, Mapping, Protocol, Sequence

from .dto import canonical_json_bytes, decode_base64url


QUERY_RESULT_SCHEMA_VERSION = "fg-query-result-v1"
GOLD_EVIDENCE_SCHEMA_VERSION = "fg-gold-result-evidence-v1"
EVALUATION_RECEIPT_SCHEMA_VERSION = "fg-evaluation-receipt-v1"
COMPARATOR_NAME = "frankengate-typed-result-equivalence"

MAX_COLUMNS = 2_048
MAX_ROWS = 1_000_000
MAX_CELL_BYTES = 4 * 1024 * 1024
MAX_ARRAY_DEPTH = 16
MAX_SAFE_INTEGER = (1 << 53) - 1

REASON_CODES = frozenset(
    {
        "correct",
        "result_mismatch",
        "strict_shape_mismatch",
        "adjudication_ineligible",
        "security_not_authorized",
        "authority_not_current",
        "candidate_execution_count_invalid",
    }
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_OPAQUE_REF_RE = re.compile(r"^[A-Za-z0-9_-]{8,256}$")
_INTEGER_RE = re.compile(r"^(?:0|-[1-9][0-9]*|[1-9][0-9]*)$")
_DECIMAL_RE = re.compile(
    r"^(?:0|-[1-9][0-9]*|[1-9][0-9]*)(?:\.[0-9]*[1-9])?$"
)
_FLOAT_HEX_RE = re.compile(
    r"^-?0x(?:0|[1-9a-f][0-9a-f]*)(?:\.[0-9a-f]*[1-9a-f])?p[+-][0-9]+$"
)
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
_BASE64URL_RE = re.compile(r"^[A-Za-z0-9_-]*$")


class EvaluationError(ValueError):
    """Evaluation evidence is malformed, unverified, or cross-boundary."""


class EvidenceVerifier(Protocol):
    """Narrow signature/integrity boundary; it cannot execute SQL."""

    def verify(
        self, *, purpose: str, envelope: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        """Return the authenticated payload or raise."""


@dataclass(frozen=True)
class ComparatorConfig:
    version_sha256: str
    numeric_relative_tolerance: str = "0.000000001"
    numeric_absolute_tolerance: str = "0.000000000001"

    def __post_init__(self) -> None:
        _sha256(self.version_sha256, "comparator.version_sha256")
        relative = _decimal(
            self.numeric_relative_tolerance,
            "comparator.numeric_relative_tolerance",
        )
        absolute = _decimal(
            self.numeric_absolute_tolerance,
            "comparator.numeric_absolute_tolerance",
        )
        if relative < 0 or absolute < 0:
            raise EvaluationError("numeric tolerances must be non-negative")


@dataclass(frozen=True)
class EvaluationBindings:
    stage_episode_ref: str
    submission_receipt_sha256: str
    attempt_blob_sha256: str
    model_manifest_sha256: str
    prompt_contract_sha256: str
    artifact_sha256: str
    tool_contract_sha256: str
    evaluator_build_sha256: str
    broker_build_sha256: str
    database_snapshot_sha256: str
    policy_version_sha256: str
    authority_snapshot_sha256: str
    stage_manifest_sha256: str
    raw_audit_chain_sha256: str

    def __post_init__(self) -> None:
        _opaque_ref(self.stage_episode_ref, "stage_episode_ref")
        for field, value in self.__dict__.items():
            if field != "stage_episode_ref":
                _sha256(value, field)


@dataclass(frozen=True)
class EvaluationReceipt:
    payload: Mapping[str, Any]

    @property
    def sha256(self) -> str:
        return hashlib.sha256(canonical_json_bytes(self.payload)).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return dict(self.payload)


def _closed(
    value: Any, *, path: str, required: frozenset[str]
) -> Mapping[str, Any]:
    if type(value) is not dict:
        raise EvaluationError(f"{path} must be an object")
    actual = set(value)
    missing = required - actual
    unknown = actual - required
    if missing:
        raise EvaluationError(
            f"{path} missing fields: {', '.join(sorted(missing))}"
        )
    if unknown:
        raise EvaluationError(
            f"{path} unknown fields: {', '.join(sorted(unknown))}"
        )
    return value


def _string(
    value: Any, path: str, *, allow_empty: bool = False, limit: int = 4096
) -> str:
    if type(value) is not str:
        raise EvaluationError(f"{path} must be a string")
    try:
        byte_count = len(value.encode("utf-8", errors="strict"))
    except UnicodeEncodeError as exc:
        raise EvaluationError(f"{path} must be valid Unicode") from exc
    if not allow_empty and byte_count == 0:
        raise EvaluationError(f"{path} must not be empty")
    if byte_count > limit:
        raise EvaluationError(f"{path} exceeds {limit} bytes")
    return value


def _integer(
    value: Any, path: str, *, minimum: int = 0, maximum: int = MAX_SAFE_INTEGER
) -> int:
    if type(value) is not int or value < minimum or value > maximum:
        raise EvaluationError(
            f"{path} must be an integer from {minimum} to {maximum}"
        )
    return value


def _sha256(value: Any, path: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise EvaluationError(f"{path} must be a lowercase SHA-256 digest")
    return value


def _opaque_ref(value: Any, path: str) -> str:
    if type(value) is not str or _OPAQUE_REF_RE.fullmatch(value) is None:
        raise EvaluationError(f"{path} must be an opaque reference")
    return value


def _decimal(value: Any, path: str) -> Decimal:
    text = _string(value, path, limit=1024)
    try:
        parsed = Decimal(text)
    except InvalidOperation as exc:
        raise EvaluationError(f"{path} must be a decimal string") from exc
    if not parsed.is_finite():
        raise EvaluationError(f"{path} must be finite")
    return parsed


def _typed_cell(
    value: Any, *, path: str, depth: int = 0
) -> dict[str, Any]:
    if depth > MAX_ARRAY_DEPTH:
        raise EvaluationError(f"{path} exceeds array depth limit")
    item = _closed(
        value, path=path, required=frozenset({"kind", "value"})
    )
    kind = _string(item["kind"], f"{path}.kind", limit=32)
    cell_value = item["value"]
    if kind == "null":
        if cell_value is not None:
            raise EvaluationError(f"{path}.value must be null")
    elif kind == "bool":
        if type(cell_value) is not bool:
            raise EvaluationError(f"{path}.value must be boolean")
    elif kind == "int":
        text = _string(cell_value, f"{path}.value", limit=128)
        if _INTEGER_RE.fullmatch(text) is None:
            raise EvaluationError(f"{path}.value is not canonical int")
    elif kind == "decimal":
        text = _string(cell_value, f"{path}.value", limit=1024)
        if _DECIMAL_RE.fullmatch(text) is None:
            raise EvaluationError(f"{path}.value is not canonical decimal")
    elif kind == "float":
        text = _string(cell_value, f"{path}.value", limit=256)
        if text not in {"nan", "inf", "-inf"} and _FLOAT_HEX_RE.fullmatch(
            text
        ) is None:
            raise EvaluationError(f"{path}.value is not canonical float")
    elif kind == "text":
        _string(
            cell_value,
            f"{path}.value",
            allow_empty=True,
            limit=MAX_CELL_BYTES,
        )
    elif kind in {"date", "time", "timestamp", "timestamptz"}:
        text = _string(
            cell_value,
            f"{path}.value",
            limit=128,
        )
        try:
            if kind == "date":
                parsed_temporal = date.fromisoformat(text)
            elif kind == "time":
                parsed_temporal = time.fromisoformat(text)
            else:
                parsed_temporal = datetime.fromisoformat(text)
        except ValueError as exc:
            raise EvaluationError(
                f"{path}.value is not canonical ISO-8601 {kind}"
            ) from exc
        if kind == "timestamptz" and parsed_temporal.tzinfo is None:
            raise EvaluationError(
                f"{path}.value requires a timezone offset"
            )
        if kind == "timestamp" and parsed_temporal.tzinfo is not None:
            raise EvaluationError(
                f"{path}.value must not contain a timezone offset"
            )
        if parsed_temporal.isoformat() != text:
            raise EvaluationError(
                f"{path}.value is not canonical ISO-8601 {kind}"
            )
    elif kind == "bytes":
        text = _string(
            cell_value,
            f"{path}.value",
            allow_empty=True,
            limit=MAX_CELL_BYTES,
        )
        if _BASE64URL_RE.fullmatch(text) is None or len(text) % 4 == 1:
            raise EvaluationError(f"{path}.value is not unpadded base64url")
        if text:
            try:
                decode_base64url(text)
            except Exception as exc:
                raise EvaluationError(
                    f"{path}.value is not unpadded base64url"
                ) from exc
    elif kind == "uuid":
        text = _string(cell_value, f"{path}.value", limit=36)
        if _UUID_RE.fullmatch(text) is None:
            raise EvaluationError(f"{path}.value is not canonical UUID")
    elif kind == "json":
        text = _string(
            cell_value,
            f"{path}.value",
            limit=MAX_CELL_BYTES,
        )

        def reject_duplicates(
            pairs: list[tuple[str, Any]],
        ) -> dict[str, Any]:
            decoded: dict[str, Any] = {}
            for key, item_value in pairs:
                if key in decoded:
                    raise EvaluationError(
                        f"{path}.value contains duplicate JSON key"
                    )
                decoded[key] = item_value
            return decoded

        try:
            decoded_json = json.loads(
                text,
                object_pairs_hook=reject_duplicates,
                parse_float=lambda raw: (_ for _ in ()).throw(
                    EvaluationError(
                        f"{path}.value contains forbidden JSON float {raw}"
                    )
                ),
                parse_constant=lambda raw: (_ for _ in ()).throw(
                    EvaluationError(
                        f"{path}.value contains forbidden JSON constant {raw}"
                    )
                ),
            )
        except json.JSONDecodeError as exc:
            raise EvaluationError(
                f"{path}.value is not valid JSON"
            ) from exc
        if canonical_json_bytes(decoded_json).decode("utf-8") != text:
            raise EvaluationError(
                f"{path}.value is not canonical JSON"
            )
    elif kind == "array":
        if type(cell_value) is not list or len(cell_value) > MAX_ROWS:
            raise EvaluationError(f"{path}.value must be a bounded array")
        cell_value = [
            _typed_cell(child, path=f"{path}.value[{index}]", depth=depth + 1)
            for index, child in enumerate(cell_value)
        ]
    else:
        raise EvaluationError(f"{path}.kind is unsupported")
    return {"kind": kind, "value": cell_value}


def query_result_content_sha256(
    columns: Sequence[Mapping[str, Any]],
    rows: Sequence[Sequence[Mapping[str, Any]]],
) -> str:
    return hashlib.sha256(
        canonical_json_bytes({"columns": list(columns), "rows": list(rows)})
    ).hexdigest()


def validate_query_result(
    value: Mapping[str, Any], *, path: str
) -> dict[str, Any]:
    item = _closed(
        value,
        path=path,
        required=frozenset(
            {
                "schema_version",
                "columns",
                "rows",
                "row_count",
                "result_bytes",
                "result_content_sha256",
            }
        ),
    )
    if item["schema_version"] != QUERY_RESULT_SCHEMA_VERSION:
        raise EvaluationError(f"{path}.schema_version is unsupported")
    columns_raw = item["columns"]
    if type(columns_raw) is not list or len(columns_raw) > MAX_COLUMNS:
        raise EvaluationError(f"{path}.columns must be a bounded array")
    columns: list[dict[str, Any]] = []
    for index, raw in enumerate(columns_raw):
        column = _closed(
            raw,
            path=f"{path}.columns[{index}]",
            required=frozenset({"name", "pg_type_oid", "format"}),
        )
        format_value = _string(
            column["format"], f"{path}.columns[{index}].format", limit=16
        )
        if format_value not in {"text", "binary"}:
            raise EvaluationError("column format must be text or binary")
        columns.append(
            {
                "name": _string(
                    column["name"],
                    f"{path}.columns[{index}].name",
                    allow_empty=True,
                    limit=512,
                ),
                "pg_type_oid": _integer(
                    column["pg_type_oid"],
                    f"{path}.columns[{index}].pg_type_oid",
                    maximum=(1 << 32) - 1,
                ),
                "format": format_value,
            }
        )
    rows_raw = item["rows"]
    if type(rows_raw) is not list or len(rows_raw) > MAX_ROWS:
        raise EvaluationError(f"{path}.rows must be a bounded array")
    rows: list[list[dict[str, Any]]] = []
    for row_index, raw_row in enumerate(rows_raw):
        if type(raw_row) is not list or len(raw_row) != len(columns):
            raise EvaluationError(
                f"{path}.rows[{row_index}] must match column count"
            )
        rows.append(
            [
                _typed_cell(
                    cell,
                    path=f"{path}.rows[{row_index}][{column_index}]",
                )
                for column_index, cell in enumerate(raw_row)
            ]
        )
    row_count = _integer(
        item["row_count"], f"{path}.row_count", maximum=MAX_ROWS
    )
    if row_count != len(rows):
        raise EvaluationError(f"{path}.row_count does not match rows")
    result_bytes = _integer(
        item["result_bytes"],
        f"{path}.result_bytes",
        maximum=MAX_SAFE_INTEGER,
    )
    expected_sha = query_result_content_sha256(columns, rows)
    supplied_sha = _sha256(
        item["result_content_sha256"], f"{path}.result_content_sha256"
    )
    if not hmac.compare_digest(expected_sha, supplied_sha):
        raise EvaluationError(f"{path}.result_content_sha256 mismatch")
    return {
        "schema_version": QUERY_RESULT_SCHEMA_VERSION,
        "columns": columns,
        "rows": rows,
        "row_count": row_count,
        "result_bytes": result_bytes,
        "result_content_sha256": supplied_sha,
    }


def _cell_equal(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
    *,
    relative: Decimal,
    absolute: Decimal,
) -> bool:
    if left["kind"] != right["kind"]:
        return False
    kind = left["kind"]
    left_value = left["value"]
    right_value = right["value"]
    if kind in {"int", "decimal"}:
        a = Decimal(left_value)
        b = Decimal(right_value)
        return abs(a - b) <= max(absolute, relative * max(abs(a), abs(b)))
    if kind == "float":
        if left_value == "nan" or right_value == "nan":
            return left_value == right_value
        a = (
            float(left_value)
            if left_value in {"inf", "-inf"}
            else float.fromhex(left_value)
        )
        b = (
            float(right_value)
            if right_value in {"inf", "-inf"}
            else float.fromhex(right_value)
        )
        return a == b if math.isinf(a) or math.isinf(b) else math.isclose(
            a, b, rel_tol=float(relative), abs_tol=float(absolute)
        )
    if kind == "array":
        return len(left_value) == len(right_value) and all(
            _cell_equal(a, b, relative=relative, absolute=absolute)
            for a, b in zip(left_value, right_value)
        )
    return left_value == right_value


def _row_equal(
    left: Sequence[Mapping[str, Any]],
    right: Sequence[Mapping[str, Any]],
    *,
    relative: Decimal,
    absolute: Decimal,
) -> bool:
    return len(left) == len(right) and all(
        _cell_equal(a, b, relative=relative, absolute=absolute)
        for a, b in zip(left, right)
    )


def _rows_equal(
    candidate: Sequence[Sequence[Mapping[str, Any]]],
    gold: Sequence[Sequence[Mapping[str, Any]]],
    *,
    order_sensitive: bool,
    relative: Decimal,
    absolute: Decimal,
) -> bool:
    if len(candidate) != len(gold):
        return False
    if order_sensitive:
        return all(
            _row_equal(a, b, relative=relative, absolute=absolute)
            for a, b in zip(candidate, gold)
        )
    candidate_ordered = sorted(candidate, key=_row_sort_key)
    gold_ordered = sorted(gold, key=_row_sort_key)
    return all(
        _row_equal(a, b, relative=relative, absolute=absolute)
        for a, b in zip(candidate_ordered, gold_ordered)
    )


def _cell_sort_key(cell: Mapping[str, Any]) -> tuple[Any, ...]:
    kind = cell["kind"]
    value = cell["value"]
    if kind in {"int", "decimal"}:
        return kind, Decimal(value)
    if kind == "float":
        if value == "-inf":
            return kind, 0, 0.0
        if value == "inf":
            return kind, 2, 0.0
        if value == "nan":
            return kind, 3, 0.0
        return kind, 1, float.fromhex(value)
    if kind == "array":
        return kind, tuple(_cell_sort_key(child) for child in value)
    return kind, canonical_json_bytes(value)


def _row_sort_key(row: Sequence[Mapping[str, Any]]) -> tuple[Any, ...]:
    return tuple(_cell_sort_key(cell) for cell in row)


def _strict_shape_equal(
    candidate: Mapping[str, Any], gold: Mapping[str, Any]
) -> bool:
    if len(candidate["columns"]) != len(gold["columns"]):
        return False
    return all(
        left["pg_type_oid"] == right["pg_type_oid"]
        and left["format"] == right["format"]
        for left, right in zip(candidate["columns"], gold["columns"])
    )


def _verified_payload(
    verifier: EvidenceVerifier,
    *,
    purpose: str,
    envelope: Mapping[str, Any],
) -> Mapping[str, Any]:
    payload = verifier.verify(purpose=purpose, envelope=envelope)
    if type(payload) is not dict:
        raise EvaluationError(f"{purpose} verifier returned a non-object")
    canonical_json_bytes(payload)
    return payload


def evaluate_stored_results(
    *,
    candidate_envelope: Mapping[str, Any],
    gold_envelope: Mapping[str, Any],
    bindings: EvaluationBindings,
    comparator: ComparatorConfig,
    verifier: EvidenceVerifier,
    candidate_execution_count: Callable[[str], int],
    authority_is_current: Callable[[str, str], bool],
) -> EvaluationReceipt:
    """Compare sealed results without accepting SQL or an executor capability."""

    candidate = _verified_payload(
        verifier, purpose="candidate_submission", envelope=candidate_envelope
    )
    gold = _verified_payload(
        verifier, purpose="gold_result", envelope=gold_envelope
    )
    candidate_fields = _closed(
        candidate,
        path="candidate",
        required=frozenset(
            {
                "schema_version",
                "stage_episode_ref",
                "submission_receipt_sha256",
                "attempt_blob_sha256",
                "candidate_execution_count",
                "authority_valid",
                "policy_accepted",
                "authority_snapshot_sha256",
                "database_snapshot_sha256",
                "stage_manifest_sha256",
                "query_result",
            }
        ),
    )
    if candidate_fields["schema_version"] != "fg-candidate-submission-v1":
        raise EvaluationError("candidate.schema_version is unsupported")
    gold_fields = _closed(
        gold,
        path="gold",
        required=frozenset(
            {
                "schema_version",
                "stage_episode_ref",
                "database_snapshot_sha256",
                "stage_manifest_sha256",
                "adjudication",
                "gold_execution_count",
                "alternatives",
            }
        ),
    )
    if gold_fields["schema_version"] != GOLD_EVIDENCE_SCHEMA_VERSION:
        raise EvaluationError("gold.schema_version is unsupported")

    candidate_episode = _opaque_ref(
        candidate_fields["stage_episode_ref"], "candidate.stage_episode_ref"
    )
    gold_episode = _opaque_ref(
        gold_fields["stage_episode_ref"], "gold.stage_episode_ref"
    )
    if not (
        hmac.compare_digest(candidate_episode, bindings.stage_episode_ref)
        and hmac.compare_digest(gold_episode, bindings.stage_episode_ref)
    ):
        raise EvaluationError("cross-episode evidence is forbidden")

    bound_hashes = {
        "submission_receipt_sha256": bindings.submission_receipt_sha256,
        "attempt_blob_sha256": bindings.attempt_blob_sha256,
        "authority_snapshot_sha256": bindings.authority_snapshot_sha256,
        "database_snapshot_sha256": bindings.database_snapshot_sha256,
        "stage_manifest_sha256": bindings.stage_manifest_sha256,
    }
    for field, expected in bound_hashes.items():
        actual = (
            candidate_fields[field]
            if field in candidate_fields
            else gold_fields[field]
        )
        actual = _sha256(actual, f"evidence.{field}")
        if not hmac.compare_digest(actual, expected):
            raise EvaluationError(f"{field} binding mismatch")
    for field in {"database_snapshot_sha256", "stage_manifest_sha256"}:
        candidate_value = _sha256(candidate_fields[field], f"candidate.{field}")
        gold_value = _sha256(gold_fields[field], f"gold.{field}")
        if not hmac.compare_digest(candidate_value, gold_value):
            raise EvaluationError(f"candidate/gold {field} mismatch")

    recorded_count = _integer(
        candidate_fields["candidate_execution_count"],
        "candidate.candidate_execution_count",
        maximum=MAX_SAFE_INTEGER,
    )
    if type(candidate_fields["authority_valid"]) is not bool:
        raise EvaluationError("candidate.authority_valid must be boolean")
    if type(candidate_fields["policy_accepted"]) is not bool:
        raise EvaluationError("candidate.policy_accepted must be boolean")
    security_authorized = (
        candidate_fields["authority_valid"]
        and candidate_fields["policy_accepted"]
    )
    count_before = candidate_execution_count(bindings.stage_episode_ref)
    if type(count_before) is not int or count_before < 0:
        raise EvaluationError("candidate execution counter is invalid")

    candidate_result = validate_query_result(
        candidate_fields["query_result"], path="candidate.query_result"
    )
    adjudication = _closed(
        gold_fields["adjudication"],
        path="gold.adjudication",
        required=frozenset(
            {"classification", "primary_quality_eligible"}
        ),
    )
    classification = _string(
        adjudication["classification"],
        "gold.adjudication.classification",
        limit=128,
    )
    if type(adjudication["primary_quality_eligible"]) is not bool:
        raise EvaluationError(
            "gold.adjudication.primary_quality_eligible must be boolean"
        )
    alternatives_raw = gold_fields["alternatives"]
    if type(alternatives_raw) is not list or not alternatives_raw:
        raise EvaluationError("gold.alternatives must be a non-empty array")
    if len(alternatives_raw) > 128:
        raise EvaluationError("gold.alternatives exceeds 128 entries")
    gold_execution_count = _integer(
        gold_fields["gold_execution_count"],
        "gold.gold_execution_count",
        minimum=1,
        maximum=128,
    )
    if gold_execution_count != len(alternatives_raw):
        raise EvaluationError(
            "gold.gold_execution_count must match alternatives"
        )

    relative = _decimal(
        comparator.numeric_relative_tolerance,
        "comparator.numeric_relative_tolerance",
    )
    absolute = _decimal(
        comparator.numeric_absolute_tolerance,
        "comparator.numeric_absolute_tolerance",
    )
    gold_hashes: list[str] = []
    matched: int | None = None
    shape_match = False
    order_rule = "none"
    for index, raw in enumerate(alternatives_raw):
        alternative = _closed(
            raw,
            path=f"gold.alternatives[{index}]",
            required=frozenset({"order_sensitive", "query_result"}),
        )
        if type(alternative["order_sensitive"]) is not bool:
            raise EvaluationError("gold order_sensitive must be boolean")
        gold_result = validate_query_result(
            alternative["query_result"],
            path=f"gold.alternatives[{index}].query_result",
        )
        gold_hashes.append(gold_result["result_content_sha256"])
        this_shape = _strict_shape_equal(candidate_result, gold_result)
        shape_match = shape_match or this_shape
        if matched is None and this_shape and _rows_equal(
            candidate_result["rows"],
            gold_result["rows"],
            order_sensitive=alternative["order_sensitive"],
            relative=relative,
            absolute=absolute,
        ):
            matched = index
            order_rule = (
                "gold-order-sensitive"
                if alternative["order_sensitive"]
                else "gold-order-insensitive"
            )

    authority_current = authority_is_current(
        bindings.stage_episode_ref, bindings.authority_snapshot_sha256
    )
    if type(authority_current) is not bool:
        raise EvaluationError("authority currentness result must be boolean")
    count_after = candidate_execution_count(bindings.stage_episode_ref)
    if type(count_after) is not int or count_after < 0:
        raise EvaluationError("candidate execution counter is invalid")

    eligible = adjudication["primary_quality_eligible"]
    execution_count_valid = recorded_count == count_before == count_after == 1
    semantic_correct = (
        matched is not None
        and eligible
        and security_authorized
        and authority_current
        and execution_count_valid
    )
    if not eligible:
        reason = "adjudication_ineligible"
    elif not security_authorized:
        reason = "security_not_authorized"
    elif not authority_current:
        reason = "authority_not_current"
    elif not execution_count_valid:
        reason = "candidate_execution_count_invalid"
    elif not shape_match:
        reason = "strict_shape_mismatch"
    elif matched is None:
        reason = "result_mismatch"
    else:
        reason = "correct"
    if reason not in REASON_CODES:
        raise AssertionError("closed reason code invariant failed")

    payload = {
        "schema_version": EVALUATION_RECEIPT_SCHEMA_VERSION,
        "stage_episode_ref": bindings.stage_episode_ref,
        "submission_receipt_sha256": bindings.submission_receipt_sha256,
        "attempt_blob_sha256": bindings.attempt_blob_sha256,
        "candidate_result_sha256": candidate_result[
            "result_content_sha256"
        ],
        "gold_result_sha256": gold_hashes,
        "matched_gold_alternative": matched,
        "semantic_correct": semantic_correct,
        "strict_answer_shape_correct": shape_match,
        "security_authorized": security_authorized,
        "authority_current_at_evaluation": authority_current,
        "candidate_execution_count_before_evaluation": count_before,
        "candidate_execution_count_after_evaluation": count_after,
        "gold_execution_count": gold_execution_count,
        "reason_code": reason,
        "adjudication_classification": classification,
        "comparator": {
            "name": COMPARATOR_NAME,
            "version_sha256": comparator.version_sha256,
            "numeric_relative_tolerance": (
                comparator.numeric_relative_tolerance
            ),
            "numeric_absolute_tolerance": (
                comparator.numeric_absolute_tolerance
            ),
            "order_rule": order_rule,
        },
        "model_manifest_sha256": bindings.model_manifest_sha256,
        "prompt_contract_sha256": bindings.prompt_contract_sha256,
        "artifact_sha256": bindings.artifact_sha256,
        "tool_contract_sha256": bindings.tool_contract_sha256,
        "evaluator_build_sha256": bindings.evaluator_build_sha256,
        "broker_build_sha256": bindings.broker_build_sha256,
        "database_snapshot_sha256": bindings.database_snapshot_sha256,
        "policy_version_sha256": bindings.policy_version_sha256,
        "authority_snapshot_sha256": bindings.authority_snapshot_sha256,
        "stage_manifest_sha256": bindings.stage_manifest_sha256,
        "raw_audit_chain_sha256": bindings.raw_audit_chain_sha256,
    }
    canonical_json_bytes(payload)
    return EvaluationReceipt(payload=payload)


def aggregate_receipts(
    receipts: Sequence[EvaluationReceipt],
) -> dict[str, Any]:
    """Produce an audit-safe aggregate without questions, SQL, or row data."""

    reason_counts = Counter()
    correct = 0
    receipt_hashes: list[str] = []
    for receipt in receipts:
        if type(receipt) is not EvaluationReceipt:
            raise EvaluationError("aggregate accepts EvaluationReceipt only")
        reason = receipt.payload.get("reason_code")
        if reason not in REASON_CODES:
            raise EvaluationError("receipt has an unknown reason code")
        reason_counts[reason] += 1
        correct += int(receipt.payload.get("semantic_correct") is True)
        receipt_hashes.append(receipt.sha256)
    aggregate = {
        "schema_version": "fg-evaluation-aggregate-v1",
        "episode_count": len(receipts),
        "semantic_correct_count": correct,
        "reason_counts": {
            reason: reason_counts[reason]
            for reason in sorted(reason_counts)
        },
        "ordered_receipt_sha256": receipt_hashes,
    }
    canonical_json_bytes(aggregate)
    return aggregate
