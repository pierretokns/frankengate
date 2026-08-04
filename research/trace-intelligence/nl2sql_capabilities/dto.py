"""Strict DTO and canonical-encoding boundary for an NL2SQL solver.

This module intentionally supports a narrower value domain than general JSON
for objects that will be hashed or signed: null, booleans, strings, lists,
objects with string keys, and integers in the interoperable IEEE-754 exact
range. Floats are forbidden. Strings must be valid UTF-8 scalar sequences.

Object keys are ordered by UTF-16 code units, matching RFC 8785/JCS. Within
the restricted value domain, :func:`canonical_json_bytes` therefore supplies
one deterministic UTF-8 representation without accepting the ambiguous
numeric cases that a general-purpose JSON encoder would permit.
"""

from __future__ import annotations

from dataclasses import dataclass
import base64
import binascii
import hashlib
import hmac
import json
import re
import secrets
from typing import Any, Mapping


SOLVER_EPISODE_SCHEMA_VERSION = "fg-solver-episode-v1"
BROKER_PROTOCOL_VERSION = "fg-governed-sql-tool-v1"
STAGE_ROLES = frozenset({"evidence", "visible_selection", "hidden_test"})
MAX_SIGNED_INTEGER = (1 << 53) - 1
MAX_FRAME_BYTES = 16 * 1024 * 1024

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_BASE64URL_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_ARTIFACT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")

# These are trusted/evaluator concepts, not solver inputs. Test them before
# ordinary unknown-field handling so accidental leakage has an explicit error.
_FORBIDDEN_SOLVER_FIELDS = frozenset(
    {
        "task_id",
        "database",
        "database_name",
        "db_name",
        "query_category",
        "fold",
        "fold_id",
        "stage",
        "stage_role",
        "stage_episode_ref",
        "source",
        "source_file",
        "source_row",
        "source_task_id",
        "locator",
        "source_locator",
        "gold",
        "gold_sql",
        "gold_result",
        "answer",
        "adjudication",
        "outcome",
        "label",
    }
)


class DTOValidationError(ValueError):
    """An IPC value violates the closed capability schema."""


def _path(parent: str, child: str) -> str:
    return child if not parent else f"{parent}.{child}"


def _valid_unicode(value: str, *, path: str) -> str:
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise DTOValidationError(f"{path} is not valid Unicode") from exc
    return value


def _require_string(
    value: Any,
    *,
    path: str,
    allow_empty: bool = False,
    max_utf8_bytes: int,
) -> str:
    if type(value) is not str:
        raise DTOValidationError(f"{path} must be a string")
    _valid_unicode(value, path=path)
    encoded_length = len(value.encode("utf-8"))
    if not allow_empty and encoded_length == 0:
        raise DTOValidationError(f"{path} must not be empty")
    if encoded_length > max_utf8_bytes:
        raise DTOValidationError(
            f"{path} exceeds its {max_utf8_bytes}-byte limit"
        )
    return value


def _require_literal(value: Any, expected: str, *, path: str) -> str:
    parsed = _require_string(
        value, path=path, allow_empty=False, max_utf8_bytes=128
    )
    if parsed != expected:
        raise DTOValidationError(f"{path} must equal {expected!r}")
    return parsed


def _require_sha256(value: Any, *, path: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise DTOValidationError(
            f"{path} must be a lowercase 64-character SHA-256 hex digest"
        )
    return value


def _require_int(
    value: Any, *, path: str, minimum: int, maximum: int
) -> int:
    if type(value) is not int:
        raise DTOValidationError(f"{path} must be an integer")
    if value < minimum or value > maximum:
        raise DTOValidationError(
            f"{path} must be between {minimum} and {maximum}"
        )
    return value


def _scan_forbidden_fields(value: Any, *, path: str = "") -> None:
    if type(value) is dict:
        for key, child in value.items():
            if type(key) is not str:
                raise DTOValidationError(
                    f"{path or '$'} contains a non-string field name"
                )
            child_path = _path(path, key)
            if key.casefold() in _FORBIDDEN_SOLVER_FIELDS:
                raise DTOValidationError(
                    f"{child_path} is forbidden in a solver DTO"
                )
            _scan_forbidden_fields(child, path=child_path)
    elif type(value) is list:
        for index, child in enumerate(value):
            _scan_forbidden_fields(child, path=f"{path}[{index}]")


def _closed_object(
    value: Any, *, path: str, required: frozenset[str]
) -> dict[str, Any]:
    if type(value) is not dict:
        raise DTOValidationError(f"{path} must be an object")
    keys = set(value)
    unknown = keys - required
    missing = required - keys
    if unknown:
        rendered = ", ".join(sorted(repr(key) for key in unknown))
        raise DTOValidationError(f"{path} has unknown field(s): {rendered}")
    if missing:
        rendered = ", ".join(sorted(missing))
        raise DTOValidationError(f"{path} is missing required field(s): {rendered}")
    return value


def encode_base64url(value: bytes) -> str:
    """Encode non-empty bytes as canonical, unpadded base64url."""

    if type(value) is not bytes or not value:
        raise DTOValidationError("base64url input must be non-empty bytes")
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def decode_base64url(value: str, *, expected_nbytes: int | None = None) -> bytes:
    """Decode canonical unpadded base64url and optionally enforce its size."""

    if (
        type(value) is not str
        or _BASE64URL_RE.fullmatch(value) is None
        or len(value) % 4 == 1
    ):
        raise DTOValidationError("value is not canonical unpadded base64url")
    padding = "=" * ((4 - len(value) % 4) % 4)
    try:
        decoded = base64.b64decode(
            value + padding, altchars=b"-_", validate=True
        )
    except (binascii.Error, ValueError) as exc:
        raise DTOValidationError(
            "value is not canonical unpadded base64url"
        ) from exc
    if not decoded or encode_base64url(decoded) != value:
        raise DTOValidationError("value is not canonical unpadded base64url")
    if expected_nbytes is not None and len(decoded) != expected_nbytes:
        raise DTOValidationError(
            f"decoded capability must contain exactly {expected_nbytes} bytes"
        )
    return decoded


def generate_nonce(num_bytes: int = 16) -> str:
    """Generate an opaque nonce with at least 128 bits of entropy."""

    if type(num_bytes) is not int or num_bytes < 16 or num_bytes > 1024:
        raise DTOValidationError("nonce size must be an integer from 16 to 1024")
    return encode_base64url(secrets.token_bytes(num_bytes))


def generate_request_nonce() -> str:
    return generate_nonce(16)


def generate_attempt_id() -> str:
    return generate_nonce(24)


def generate_database_handle() -> str:
    return generate_nonce(32)


def derive_stage_episode_ref(
    *,
    key: bytes,
    experiment_id: str,
    fold_id: str,
    stage_role: str,
    source_task_id: str,
) -> str:
    """Derive the offline/resolver-only opaque HMAC episode reference."""

    if type(key) is not bytes or len(key) < 32:
        raise DTOValidationError(
            "stage episode reference key must contain at least 32 bytes"
        )
    components = {
        "experiment_id": experiment_id,
        "fold_id": fold_id,
        "stage_role": stage_role,
        "source_task_id": source_task_id,
    }
    for name, value in components.items():
        _require_string(
            value, path=name, allow_empty=False, max_utf8_bytes=4096
        )
        if "\0" in value:
            raise DTOValidationError(f"{name} must not contain NUL")
    if stage_role not in STAGE_ROLES:
        raise DTOValidationError(
            "stage_role must be evidence, visible_selection, or hidden_test"
        )
    message = "\0".join(
        (experiment_id, fold_id, stage_role, source_task_id)
    ).encode("utf-8")
    return encode_base64url(hmac.new(key, message, hashlib.sha256).digest())


def _canonicalize(value: Any, *, path: str) -> str:
    value_type = type(value)
    if value is None:
        return "null"
    if value_type is bool:
        return "true" if value else "false"
    if value_type is int:
        if value < -MAX_SIGNED_INTEGER or value > MAX_SIGNED_INTEGER:
            raise DTOValidationError(
                f"{path} integer is outside the interoperable signed range"
            )
        return str(value)
    if value_type is float:
        raise DTOValidationError(f"{path} floats are forbidden in signed values")
    if value_type is str:
        _valid_unicode(value, path=path)
        return json.dumps(
            value, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )
    if value_type is list:
        return "[" + ",".join(
            _canonicalize(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        ) + "]"
    if value_type is dict:
        for key in value:
            if type(key) is not str:
                raise DTOValidationError(
                    f"{path} objects may contain only string keys"
                )
            _valid_unicode(key, path=f"{path} key")
        ordered_keys = sorted(
            value, key=lambda key: key.encode("utf-16-be", errors="strict")
        )
        items = (
            _canonicalize(key, path=f"{path} key")
            + ":"
            + _canonicalize(value[key], path=_path(path, key))
            for key in ordered_keys
        )
        return "{" + ",".join(items) + "}"
    raise DTOValidationError(
        f"{path} has unsupported signed type {value_type.__name__}"
    )


def canonical_json_bytes(value: Any) -> bytes:
    """Encode a restricted signed value deterministically as UTF-8 JSON."""

    return _canonicalize(value, path="$").encode("utf-8")


def _reject_duplicate_json_members(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DTOValidationError(f"JSON object has duplicate field {key!r}")
        result[key] = value
    return result


@dataclass(frozen=True)
class AuthorizedDatabaseHandleDTO:
    handle: str
    broker_protocol_version: str
    authorization_epoch_ref_sha256: str
    authority_snapshot_sha256: str
    expires_at_unix_ms: int

    @classmethod
    def from_dict(
        cls, value: Mapping[str, Any]
    ) -> "AuthorizedDatabaseHandleDTO":
        item = _closed_object(
            value,
            path="authorized_database_handle",
            required=frozenset(
                {
                    "handle",
                    "broker_protocol_version",
                    "authorization_epoch_ref_sha256",
                    "authority_snapshot_sha256",
                    "expires_at_unix_ms",
                }
            ),
        )
        handle = _require_string(
            item["handle"],
            path="authorized_database_handle.handle",
            max_utf8_bytes=64,
        )
        decode_base64url(handle, expected_nbytes=32)
        return cls(
            handle=handle,
            broker_protocol_version=_require_literal(
                item["broker_protocol_version"],
                BROKER_PROTOCOL_VERSION,
                path="authorized_database_handle.broker_protocol_version",
            ),
            authorization_epoch_ref_sha256=_require_sha256(
                item["authorization_epoch_ref_sha256"],
                path=(
                    "authorized_database_handle."
                    "authorization_epoch_ref_sha256"
                ),
            ),
            authority_snapshot_sha256=_require_sha256(
                item["authority_snapshot_sha256"],
                path="authorized_database_handle.authority_snapshot_sha256",
            ),
            expires_at_unix_ms=_require_int(
                item["expires_at_unix_ms"],
                path="authorized_database_handle.expires_at_unix_ms",
                minimum=1,
                maximum=MAX_SIGNED_INTEGER,
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "handle": self.handle,
            "broker_protocol_version": self.broker_protocol_version,
            "authorization_epoch_ref_sha256": (
                self.authorization_epoch_ref_sha256
            ),
            "authority_snapshot_sha256": self.authority_snapshot_sha256,
            "expires_at_unix_ms": self.expires_at_unix_ms,
        }


@dataclass(frozen=True)
class ArtifactExposureDTO:
    artifact_id: str
    artifact_sha256: str
    content: str

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ArtifactExposureDTO":
        item = _closed_object(
            value,
            path="artifact_exposure",
            required=frozenset({"artifact_id", "artifact_sha256", "content"}),
        )
        artifact_id = _require_string(
            item["artifact_id"],
            path="artifact_exposure.artifact_id",
            max_utf8_bytes=128,
        )
        if _ARTIFACT_ID_RE.fullmatch(artifact_id) is None:
            raise DTOValidationError(
                "artifact_exposure.artifact_id must be an opaque safe label"
            )
        content = _require_string(
            item["content"],
            path="artifact_exposure.content",
            allow_empty=True,
            max_utf8_bytes=4 * 1024 * 1024,
        )
        artifact_sha256 = _require_sha256(
            item["artifact_sha256"],
            path="artifact_exposure.artifact_sha256",
        )
        actual_sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if not hmac.compare_digest(artifact_sha256, actual_sha256):
            raise DTOValidationError(
                "artifact_exposure.artifact_sha256 does not match content"
            )
        return cls(
            artifact_id=artifact_id,
            artifact_sha256=artifact_sha256,
            content=content,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_sha256": self.artifact_sha256,
            "content": self.content,
        }


@dataclass(frozen=True)
class SolverLimitsDTO:
    max_model_turns: int
    max_schema_calls: int
    max_sql_attempts: int
    max_generated_tokens_per_call: int
    max_generated_tokens_per_episode: int
    model_wall_ms: int
    model_result_max_rows: int
    model_result_max_bytes: int

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SolverLimitsDTO":
        fields = frozenset(
            {
                "max_model_turns",
                "max_schema_calls",
                "max_sql_attempts",
                "max_generated_tokens_per_call",
                "max_generated_tokens_per_episode",
                "model_wall_ms",
                "model_result_max_rows",
                "model_result_max_bytes",
            }
        )
        item = _closed_object(value, path="limits", required=fields)
        result = cls(
            max_model_turns=_require_int(
                item["max_model_turns"],
                path="limits.max_model_turns",
                minimum=1,
                maximum=64,
            ),
            max_schema_calls=_require_int(
                item["max_schema_calls"],
                path="limits.max_schema_calls",
                minimum=0,
                maximum=64,
            ),
            max_sql_attempts=_require_int(
                item["max_sql_attempts"],
                path="limits.max_sql_attempts",
                minimum=1,
                maximum=64,
            ),
            max_generated_tokens_per_call=_require_int(
                item["max_generated_tokens_per_call"],
                path="limits.max_generated_tokens_per_call",
                minimum=1,
                maximum=32_768,
            ),
            max_generated_tokens_per_episode=_require_int(
                item["max_generated_tokens_per_episode"],
                path="limits.max_generated_tokens_per_episode",
                minimum=1,
                maximum=262_144,
            ),
            model_wall_ms=_require_int(
                item["model_wall_ms"],
                path="limits.model_wall_ms",
                minimum=1,
                maximum=3_600_000,
            ),
            model_result_max_rows=_require_int(
                item["model_result_max_rows"],
                path="limits.model_result_max_rows",
                minimum=1,
                maximum=10_000,
            ),
            model_result_max_bytes=_require_int(
                item["model_result_max_bytes"],
                path="limits.model_result_max_bytes",
                minimum=1,
                maximum=MAX_FRAME_BYTES,
            ),
        )
        if (
            result.max_generated_tokens_per_episode
            < result.max_generated_tokens_per_call
        ):
            raise DTOValidationError(
                "limits.max_generated_tokens_per_episode must be at least "
                "limits.max_generated_tokens_per_call"
            )
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_model_turns": self.max_model_turns,
            "max_schema_calls": self.max_schema_calls,
            "max_sql_attempts": self.max_sql_attempts,
            "max_generated_tokens_per_call": (
                self.max_generated_tokens_per_call
            ),
            "max_generated_tokens_per_episode": (
                self.max_generated_tokens_per_episode
            ),
            "model_wall_ms": self.model_wall_ms,
            "model_result_max_rows": self.model_result_max_rows,
            "model_result_max_bytes": self.model_result_max_bytes,
        }


@dataclass(frozen=True)
class SolverEpisodeDTO:
    schema_version: str
    question: str
    official_instructions: str
    authorized_database_handle: AuthorizedDatabaseHandleDTO
    artifact_exposure: ArtifactExposureDTO
    limits: SolverLimitsDTO

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SolverEpisodeDTO":
        _scan_forbidden_fields(value)
        item = _closed_object(
            value,
            path="solver_episode",
            required=frozenset(
                {
                    "schema_version",
                    "question",
                    "official_instructions",
                    "authorized_database_handle",
                    "artifact_exposure",
                    "limits",
                }
            ),
        )
        result = cls(
            schema_version=_require_literal(
                item["schema_version"],
                SOLVER_EPISODE_SCHEMA_VERSION,
                path="schema_version",
            ),
            question=_require_string(
                item["question"],
                path="question",
                max_utf8_bytes=1024 * 1024,
            ),
            official_instructions=_require_string(
                item["official_instructions"],
                path="official_instructions",
                allow_empty=True,
                max_utf8_bytes=1024 * 1024,
            ),
            authorized_database_handle=AuthorizedDatabaseHandleDTO.from_dict(
                item["authorized_database_handle"]
            ),
            artifact_exposure=ArtifactExposureDTO.from_dict(
                item["artifact_exposure"]
            ),
            limits=SolverLimitsDTO.from_dict(item["limits"]),
        )
        if len(result.canonical_bytes()) > MAX_FRAME_BYTES:
            raise DTOValidationError(
                f"solver episode exceeds the {MAX_FRAME_BYTES}-byte frame limit"
            )
        return result

    @classmethod
    def from_json_bytes(cls, value: bytes) -> "SolverEpisodeDTO":
        if type(value) is not bytes:
            raise DTOValidationError("solver episode frame must be bytes")
        if not value or len(value) > MAX_FRAME_BYTES:
            raise DTOValidationError("solver episode frame size is invalid")
        try:
            payload = json.loads(
                value.decode("utf-8"),
                object_pairs_hook=_reject_duplicate_json_members,
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DTOValidationError(
                "solver episode frame is not valid UTF-8 JSON"
            ) from exc
        return cls.from_dict(payload)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "question": self.question,
            "official_instructions": self.official_instructions,
            "authorized_database_handle": (
                self.authorized_database_handle.to_dict()
            ),
            "artifact_exposure": self.artifact_exposure.to_dict(),
            "limits": self.limits.to_dict(),
        }

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.to_dict())
