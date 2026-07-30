"""Capability-bound, fail-closed SQL broker for isolated NL2SQL episodes.

The solver supplies only an opaque database handle and operation-specific
arguments.  The broker owns the principal/database binding, obtains a fresh
authority decision for every operation, enforces budgets and a read-only SQL
policy, and records every authorized SQL attempt in the append-only attempt
store.

This is a research runtime slice, not a production database driver.  The
``DatabaseAdapter`` boundary must provide a genuinely read-only, least-
privilege transaction in production.  The broker's parser policy is an
independent first layer and is not a substitute for database permissions,
statement timeouts, or row/byte limits enforced by that adapter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from decimal import Decimal
import hashlib
import hmac
import math
import threading
from typing import Any, Callable, FrozenSet, Mapping, Protocol, Sequence
import uuid

from .attempt_store import (
    AttemptStore,
    AttemptStoreError,
    CrossEpisodeAttemptError,
    EpisodeStateError,
    IntegrityError,
    UnknownAttemptError,
    UnsubmittableAttemptError,
    canonical_json_bytes,
    sha256_bytes,
)
from .broker_protocol import (
    ERROR_STATUSES,
    MAX_COLUMNS,
    MAX_FRAME_BYTES,
    MAX_TABLES,
    OPERATIONS,
    TOOL_RESPONSE_SCHEMA_VERSION,
    ToolRequestDTO,
    ToolResponseDTO,
)
from .dto import (
    AuthorizedDatabaseHandleDTO,
    SolverLimitsDTO,
    encode_base64url,
)
from .sql_read_policy import (
    SQLPolicy,
    SQLPolicyError,
    ValidatedSQL,
    validate_candidate_sql,
)


AUTHORITY_RECEIPT_SCHEMA_VERSION = "fg-current-authority-receipt-v1"
POLICY_RECEIPT_SCHEMA_VERSION = "fg-sql-policy-receipt-v1"
QUERY_RESULT_SCHEMA_VERSION = "fg-query-result-v1"
ABSTENTION_RECEIPT_SCHEMA_VERSION = "fg-abstention-receipt-v1"

_SHA256_LENGTH = 64


class BrokerConfigurationError(ValueError):
    """A trusted episode binding is incomplete, ambiguous, or duplicated."""


class UnknownBrokerEpisodeError(LookupError):
    """No trusted broker state exists for the requested episode."""


class DatabaseAdapterError(RuntimeError):
    """The read-only database adapter could not satisfy an operation."""


class DatabaseResourceLimitError(DatabaseAdapterError):
    """A full result exceeded its sealed per-episode row or byte limit."""


@dataclass(frozen=True)
class AuthorityCheck:
    """Exact operation context sent to the current authority provider."""

    episode_ref: str
    principal_id: str
    database_handle: str
    operation: str
    expected_authorization_epoch_ref_sha256: str
    expected_authority_snapshot_sha256: str


@dataclass(frozen=True)
class AuthorityDecision:
    """Current authoritative binding returned for one operation."""

    allowed: bool
    principal_id: str
    database_id: str
    authorization_epoch_ref_sha256: str
    authority_snapshot_sha256: str
    expires_at_unix_ms: int
    allowed_operations: FrozenSet[str]


class AuthorityProvider(Protocol):
    def revalidate(self, check: AuthorityCheck) -> AuthorityDecision:
        """Return current authority; cached episode authority is insufficient."""


@dataclass(frozen=True)
class DatabaseColumn:
    name: str
    pg_type_oid: int
    format: str = "text"


@dataclass(frozen=True)
class DatabaseResult:
    """Full result returned by a bounded, read-only adapter execution."""

    columns: tuple[DatabaseColumn, ...]
    rows: tuple[tuple[Any, ...], ...]


class DatabaseAdapter(Protocol):
    def describe_schema(
        self, database_id: str
    ) -> Mapping[str, Sequence[str]]:
        """Return the complete authorized schema for the bound database."""

    def execute_read_only(
        self,
        database_id: str,
        sql: str,
        *,
        max_rows: int,
        max_bytes: int,
    ) -> DatabaseResult:
        """Execute exactly one validated query in a read-only transaction."""


@dataclass(frozen=True)
class BrokerEpisodeBinding:
    """Trusted supervisor input; none of these identities enter solver IPC."""

    episode_ref: str
    principal_id: str
    database_id: str
    authorized_database_handle: AuthorizedDatabaseHandleDTO
    limits: SolverLimitsDTO
    catalog: Mapping[str, Sequence[str]]
    allowed_schemas: FrozenSet[str] = frozenset({"public", "main"})
    allowed_functions: FrozenSet[str] | None = None


@dataclass
class _EpisodeState:
    binding: BrokerEpisodeBinding
    catalog: dict[str, tuple[str, ...]]
    catalog_sha256: str
    used_nonces: set[str] = field(default_factory=set)
    model_turns_used: int = 0
    schema_calls_used: int = 0
    sql_attempts_used: int = 0
    terminal: bool = False
    terminal_receipt_sha256: str | None = None


class _BrokerFailure(RuntimeError):
    def __init__(self, status: str, code: str) -> None:
        super().__init__(code)
        if status not in ERROR_STATUSES:
            raise AssertionError(f"invalid broker error status: {status}")
        self.status = status
        self.code = code


def _is_sha256(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == _SHA256_LENGTH
        and all(character in "0123456789abcdef" for character in value)
    )


def _exact(left: str, right: str) -> bool:
    return isinstance(left, str) and isinstance(right, str) and hmac.compare_digest(
        left, right
    )


def _normalize_catalog(
    catalog: Mapping[str, Sequence[str]],
) -> dict[str, tuple[str, ...]]:
    if not isinstance(catalog, Mapping):
        raise BrokerConfigurationError("catalog must be a mapping")
    normalized: dict[str, tuple[str, ...]] = {}
    if len(catalog) > MAX_TABLES:
        raise BrokerConfigurationError("catalog exceeds table limit")
    for table, columns in catalog.items():
        if type(table) is not str or not table or len(table.encode("utf-8")) > 512:
            raise BrokerConfigurationError("catalog table name is invalid")
        if table in normalized:
            raise BrokerConfigurationError(f"duplicate catalog table {table!r}")
        if isinstance(columns, (str, bytes)) or not isinstance(columns, Sequence):
            raise BrokerConfigurationError(
                f"catalog columns for {table!r} must be a sequence"
            )
        rendered: list[str] = []
        if len(columns) > MAX_COLUMNS:
            raise BrokerConfigurationError(
                f"catalog table {table!r} exceeds column limit"
            )
        seen: set[str] = set()
        for column in columns:
            if (
                type(column) is not str
                or not column
                or len(column.encode("utf-8")) > 512
            ):
                raise BrokerConfigurationError(
                    f"catalog column in {table!r} is invalid"
                )
            if column in seen:
                raise BrokerConfigurationError(
                    f"duplicate catalog column {table!r}.{column!r}"
                )
            seen.add(column)
            rendered.append(column)
        normalized[table] = tuple(rendered)
    return dict(sorted(normalized.items()))


def _catalog_payload(catalog: Mapping[str, Sequence[str]]) -> dict[str, list[str]]:
    return {
        table: list(columns)
        for table, columns in sorted(catalog.items())
    }


def _normalize_decimal(value: Decimal) -> str:
    if not value.is_finite():
        raise DatabaseAdapterError("non-finite decimals are not supported")
    if value == 0:
        return "0"
    rendered = format(value.normalize(), "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered


def _normalize_float(value: float) -> str:
    if math.isnan(value):
        return "nan"
    if math.isinf(value):
        return "inf" if value > 0 else "-inf"
    mantissa, exponent = value.hex().split("p", 1)
    if "." in mantissa:
        mantissa = mantissa.rstrip("0").rstrip(".")
    return f"{mantissa}p{exponent}"


def _typed_cell(value: Any, *, depth: int = 0) -> dict[str, Any]:
    if depth > 16:
        raise DatabaseAdapterError("database value exceeds typed-array depth")
    if value is None:
        return {"kind": "null", "value": None}
    if type(value) is bool:
        return {"kind": "bool", "value": value}
    if type(value) is int:
        return {"kind": "int", "value": str(value)}
    if isinstance(value, Decimal):
        return {"kind": "decimal", "value": _normalize_decimal(value)}
    if type(value) is float:
        return {"kind": "float", "value": _normalize_float(value)}
    if isinstance(value, datetime):
        kind = "timestamptz" if value.tzinfo is not None else "timestamp"
        return {"kind": kind, "value": value.isoformat()}
    if isinstance(value, date):
        return {"kind": "date", "value": value.isoformat()}
    if isinstance(value, time):
        return {"kind": "time", "value": value.isoformat()}
    if isinstance(value, uuid.UUID):
        return {"kind": "uuid", "value": str(value)}
    if isinstance(value, bytes):
        return {
            "kind": "bytes",
            "value": encode_base64url(value) if value else "",
        }
    if isinstance(value, str):
        return {"kind": "text", "value": value}
    if isinstance(value, (list, tuple)):
        return {
            "kind": "array",
            "value": [
                _typed_cell(child, depth=depth + 1) for child in value
            ],
        }
    if isinstance(value, Mapping):
        return {
            "kind": "json",
            "value": canonical_json_bytes(value).decode("utf-8"),
        }
    raise DatabaseAdapterError(
        f"unsupported database value type {type(value).__name__}"
    )


def _validate_result_shape(result: DatabaseResult) -> None:
    if type(result) is not DatabaseResult:
        raise DatabaseAdapterError("adapter returned an invalid result object")
    if len(result.columns) > 2048:
        raise DatabaseResourceLimitError("result has too many columns")
    for column in result.columns:
        if (
            type(column) is not DatabaseColumn
            or len(column.name.encode("utf-8")) > 512
            or type(column.pg_type_oid) is not int
            or column.pg_type_oid < 0
            or column.pg_type_oid > (1 << 32) - 1
            or column.format not in {"text", "binary"}
        ):
            raise DatabaseAdapterError("adapter returned invalid column metadata")
    for row in result.rows:
        if not isinstance(row, tuple) or len(row) != len(result.columns):
            raise DatabaseAdapterError("adapter returned a row with invalid width")


def _full_query_result(
    result: DatabaseResult,
    *,
    max_rows: int,
    max_bytes: int,
) -> dict[str, Any]:
    _validate_result_shape(result)
    if len(result.rows) > max_rows:
        raise DatabaseResourceLimitError("full result exceeds row limit")
    typed_rows = [
        [_typed_cell(value) for value in row] for row in result.rows
    ]
    semantic_content = {
        "columns": [
            {
                "name": column.name,
                "pg_type_oid": column.pg_type_oid,
                "format": column.format,
            }
            for column in result.columns
        ],
        "rows": typed_rows,
    }
    semantic_bytes = canonical_json_bytes(semantic_content)
    content = {
        "schema_version": QUERY_RESULT_SCHEMA_VERSION,
        **semantic_content,
        "row_count": len(typed_rows),
        "result_bytes": len(semantic_bytes),
        "result_content_sha256": sha256_bytes(semantic_bytes),
    }
    if len(canonical_json_bytes(content)) > max_bytes:
        raise DatabaseResourceLimitError("full result exceeds byte limit")
    return content


class GovernedSQLBroker:
    """One-process broker with explicit authority, database, and store ports."""

    def __init__(
        self,
        *,
        authority: AuthorityProvider,
        database: DatabaseAdapter,
        attempt_store: AttemptStore,
        now_unix_ms: Callable[[], int],
        preview_max_rows: int = 100,
        preview_max_bytes: int = 256 * 1024,
    ) -> None:
        if (
            type(preview_max_rows) is not int
            or preview_max_rows < 0
            or preview_max_rows > 10_000
        ):
            raise BrokerConfigurationError(
                "preview_max_rows must be from 0 to 10000"
            )
        if (
            type(preview_max_bytes) is not int
            or preview_max_bytes < 1
            or preview_max_bytes > 16 * 1024 * 1024
        ):
            raise BrokerConfigurationError(
                "preview_max_bytes must be from 1 byte to 16 MiB"
            )
        self._authority = authority
        self._database = database
        self._attempt_store = attempt_store
        self._now_unix_ms = now_unix_ms
        self._preview_max_rows = preview_max_rows
        self._preview_max_bytes = preview_max_bytes
        self._episodes: dict[str, _EpisodeState] = {}
        self._handle_owners: dict[str, str] = {}
        self._lock = threading.RLock()
        self._handlers = {
            "describe_schema": self._describe_schema,
            "execute_sql": self._execute_sql,
            "submit_sql": self._submit_sql,
            "abstain": self._abstain,
        }
        if frozenset(self._handlers) != OPERATIONS:
            raise AssertionError("broker dispatch table does not match protocol")

    def open_episode(self, binding: BrokerEpisodeBinding) -> None:
        """Install one trusted binding and create its append-only ledger."""

        if type(binding) is not BrokerEpisodeBinding:
            raise BrokerConfigurationError(
                "episode binding must be a BrokerEpisodeBinding"
            )
        if (
            not binding.episode_ref
            or not binding.principal_id
            or not binding.database_id
        ):
            raise BrokerConfigurationError(
                "episode, principal, and database identities are required"
            )
        if type(binding.authorized_database_handle) is not AuthorizedDatabaseHandleDTO:
            raise BrokerConfigurationError(
                "authorized database handle DTO is required"
            )
        if type(binding.limits) is not SolverLimitsDTO:
            raise BrokerConfigurationError("solver limits DTO is required")
        # Dataclass constructors are public; re-enter through the strict DTO
        # validators so trusted setup cannot accidentally bypass field bounds.
        try:
            AuthorizedDatabaseHandleDTO.from_dict(
                binding.authorized_database_handle.to_dict()
            )
            SolverLimitsDTO.from_dict(binding.limits.to_dict())
        except ValueError as exc:
            raise BrokerConfigurationError(
                "episode capability or limits are invalid"
            ) from exc
        if (
            not isinstance(binding.allowed_schemas, frozenset)
            or not binding.allowed_schemas
            or not all(
                type(schema) is str and schema
                for schema in binding.allowed_schemas
            )
        ):
            raise BrokerConfigurationError("allowed_schemas is invalid")
        if (
            binding.allowed_functions is not None
            and (
                not isinstance(binding.allowed_functions, frozenset)
                or not all(
                    type(function) is str and function
                    for function in binding.allowed_functions
                )
            )
        ):
            raise BrokerConfigurationError("allowed_functions is invalid")
        catalog = _normalize_catalog(binding.catalog)
        catalog_sha256 = sha256_bytes(
            canonical_json_bytes(_catalog_payload(catalog))
        )
        if (
            len(canonical_json_bytes(_catalog_payload(catalog)))
            > MAX_FRAME_BYTES
        ):
            raise BrokerConfigurationError("catalog exceeds frame limit")
        handle = binding.authorized_database_handle.handle
        with self._lock:
            if binding.episode_ref in self._episodes:
                raise BrokerConfigurationError("duplicate broker episode")
            if handle in self._handle_owners:
                raise BrokerConfigurationError(
                    "database handle is already bound to another episode"
                )
            self._attempt_store.create_episode(binding.episode_ref)
            self._episodes[binding.episode_ref] = _EpisodeState(
                binding=binding,
                catalog=catalog,
                catalog_sha256=catalog_sha256,
            )
            self._handle_owners[handle] = binding.episode_ref

    def dispatch_frame(
        self,
        *,
        episode_ref: str,
        principal_id: str,
        frame: bytes,
    ) -> bytes:
        request = ToolRequestDTO.from_frame(frame)
        return self.dispatch(
            episode_ref=episode_ref,
            principal_id=principal_id,
            request=request,
        ).to_frame()

    def dispatch(
        self,
        *,
        episode_ref: str,
        principal_id: str,
        request: ToolRequestDTO,
    ) -> ToolResponseDTO:
        """Authorize and execute one closed-protocol operation."""

        if type(request) is not ToolRequestDTO:
            raise TypeError("dispatch requires an exact ToolRequestDTO")
        with self._lock:
            try:
                state = self._episodes[episode_ref]
            except KeyError as exc:
                raise UnknownBrokerEpisodeError(episode_ref) from exc

            try:
                authority_receipt = self._revalidate(
                    state=state,
                    principal_id=principal_id,
                    request=request,
                )
                self._reserve_request(state, request)
                if state.terminal:
                    raise _BrokerFailure(
                        "invalid_arguments", "episode_already_terminal"
                    )
                handler = self._handlers.get(request.operation)
                if handler is None:
                    raise _BrokerFailure(
                        "invalid_arguments", "operation_not_allowlisted"
                    )
                payload = handler(state, request, authority_receipt)
            except _BrokerFailure as failure:
                payload = self._error_payload(
                    state=state,
                    request=request,
                    failure=failure,
                )
            return ToolResponseDTO.from_dict(payload, request=request)

    def _revalidate(
        self,
        *,
        state: _EpisodeState,
        principal_id: str,
        request: ToolRequestDTO,
    ) -> str:
        binding = state.binding
        expected = binding.authorized_database_handle
        check = AuthorityCheck(
            episode_ref=binding.episode_ref,
            principal_id=principal_id,
            database_handle=request.database_handle,
            operation=request.operation,
            expected_authorization_epoch_ref_sha256=(
                expected.authorization_epoch_ref_sha256
            ),
            expected_authority_snapshot_sha256=(
                expected.authority_snapshot_sha256
            ),
        )
        try:
            decision = self._authority.revalidate(check)
        except Exception as exc:
            raise _BrokerFailure(
                "authority_denied", "authority_unavailable"
            ) from exc
        now = self._now_unix_ms()
        valid_shape = (
            type(decision) is AuthorityDecision
            and type(decision.allowed) is bool
            and type(decision.expires_at_unix_ms) is int
            and isinstance(decision.allowed_operations, frozenset)
            and all(operation in OPERATIONS for operation in decision.allowed_operations)
            and _is_sha256(decision.authorization_epoch_ref_sha256)
            and _is_sha256(decision.authority_snapshot_sha256)
        )
        exact_binding = (
            valid_shape
            and decision.allowed
            and _exact(principal_id, binding.principal_id)
            and _exact(decision.principal_id, binding.principal_id)
            and _exact(decision.database_id, binding.database_id)
            and _exact(request.database_handle, expected.handle)
            and _exact(
                decision.authorization_epoch_ref_sha256,
                expected.authorization_epoch_ref_sha256,
            )
            and _exact(
                decision.authority_snapshot_sha256,
                expected.authority_snapshot_sha256,
            )
            and now < expected.expires_at_unix_ms
            and now < decision.expires_at_unix_ms
            and request.operation in decision.allowed_operations
        )
        if not exact_binding:
            raise _BrokerFailure(
                "authority_denied", "current_authority_mismatch"
            )
        receipt = {
            "schema_version": AUTHORITY_RECEIPT_SCHEMA_VERSION,
            "episode_ref": binding.episode_ref,
            "principal_id_sha256": hashlib.sha256(
                binding.principal_id.encode("utf-8")
            ).hexdigest(),
            "database_id_sha256": hashlib.sha256(
                binding.database_id.encode("utf-8")
            ).hexdigest(),
            "database_handle_sha256": hashlib.sha256(
                expected.handle.encode("ascii")
            ).hexdigest(),
            "operation": request.operation,
            "authorization_epoch_ref_sha256": (
                decision.authorization_epoch_ref_sha256
            ),
            "authority_snapshot_sha256": (
                decision.authority_snapshot_sha256
            ),
            "expires_at_unix_ms": decision.expires_at_unix_ms,
        }
        return sha256_bytes(canonical_json_bytes(receipt))

    def _reserve_request(
        self, state: _EpisodeState, request: ToolRequestDTO
    ) -> None:
        if request.request_nonce in state.used_nonces:
            raise _BrokerFailure(
                "invalid_arguments", "request_nonce_replayed"
            )
        state.used_nonces.add(request.request_nonce)
        if state.model_turns_used >= state.binding.limits.max_model_turns:
            raise _BrokerFailure(
                "resource_limit", "model_turn_budget_exhausted"
            )
        state.model_turns_used += 1

    def _remaining(self, state: _EpisodeState) -> dict[str, int]:
        limits = state.binding.limits
        return {
            "schema_calls": max(
                0, limits.max_schema_calls - state.schema_calls_used
            ),
            "sql_attempts": max(
                0, limits.max_sql_attempts - state.sql_attempts_used
            ),
            "model_turns": max(
                0, limits.max_model_turns - state.model_turns_used
            ),
        }

    def _error_payload(
        self,
        *,
        state: _EpisodeState,
        request: ToolRequestDTO,
        failure: _BrokerFailure,
    ) -> dict[str, Any]:
        return {
            "schema_version": TOOL_RESPONSE_SCHEMA_VERSION,
            "request_nonce": request.request_nonce,
            "status": failure.status,
            "code": failure.code,
            "message_sha256": hashlib.sha256(
                f"{failure.status}:{failure.code}".encode("ascii")
            ).hexdigest(),
            "remaining": self._remaining(state),
        }

    def _describe_schema(
        self,
        state: _EpisodeState,
        request: ToolRequestDTO,
        authority_receipt: str,
    ) -> dict[str, Any]:
        if (
            state.schema_calls_used
            >= state.binding.limits.max_schema_calls
        ):
            raise _BrokerFailure(
                "resource_limit", "schema_call_budget_exhausted"
            )
        state.schema_calls_used += 1
        try:
            observed = _normalize_catalog(
                self._database.describe_schema(
                    state.binding.database_id
                )
            )
        except Exception as exc:
            raise _BrokerFailure(
                "database_error", "schema_introspection_failed"
            ) from exc
        observed_sha = sha256_bytes(
            canonical_json_bytes(_catalog_payload(observed))
        )
        if not hmac.compare_digest(observed_sha, state.catalog_sha256):
            raise _BrokerFailure(
                "database_error", "database_catalog_drift"
            )
        return {
            "schema_version": TOOL_RESPONSE_SCHEMA_VERSION,
            "request_nonce": request.request_nonce,
            "status": "ok",
            "observation": {
                "tables": _catalog_payload(observed),
                "catalog_sha256": observed_sha,
            },
            "authority_receipt_sha256": authority_receipt,
            "remaining": self._remaining(state),
        }

    def _policy(
        self, state: _EpisodeState, sql: str
    ) -> tuple[ValidatedSQL, str]:
        policy_kwargs: dict[str, Any] = {
            "catalog": {
                table: frozenset(columns)
                for table, columns in state.catalog.items()
            },
            "allowed_schemas": state.binding.allowed_schemas,
        }
        if state.binding.allowed_functions is not None:
            policy_kwargs["allowed_functions"] = (
                state.binding.allowed_functions
            )
        try:
            validated = validate_candidate_sql(
                sql, SQLPolicy(**policy_kwargs)
            )
        except SQLPolicyError as exc:
            raise _BrokerFailure(
                "policy_denied", exc.code
            ) from exc
        receipt = {
            "schema_version": POLICY_RECEIPT_SCHEMA_VERSION,
            "candidate_sql_sha256": hashlib.sha256(
                sql.encode("utf-8")
            ).hexdigest(),
            "catalog_sha256": state.catalog_sha256,
            "referenced_tables": list(validated.referenced_tables),
            "referenced_columns": list(validated.referenced_columns),
            "referenced_functions": list(validated.referenced_functions),
        }
        return validated, sha256_bytes(canonical_json_bytes(receipt))

    def _record_denied_or_failed(
        self,
        *,
        state: _EpisodeState,
        sql_sha256: str,
        status: str,
        error_code: str,
        authority_receipt: str,
        policy_accepted: bool | None,
        policy_receipt: str | None = None,
    ) -> None:
        bindings = {
            "authorization_epoch_ref_sha256": (
                state.binding.authorized_database_handle
                .authorization_epoch_ref_sha256
            ),
            "authority_snapshot_sha256": (
                state.binding.authorized_database_handle
                .authority_snapshot_sha256
            ),
            "authority_receipt_sha256": authority_receipt,
            "catalog_sha256": state.catalog_sha256,
        }
        if policy_receipt is not None:
            bindings["policy_receipt_sha256"] = policy_receipt
        try:
            self._attempt_store.record_attempt(
                episode_ref=state.binding.episode_ref,
                candidate_sql_sha256=sql_sha256,
                status=status,
                authority_valid=True,
                policy_accepted=policy_accepted,
                error_code=error_code,
                bindings=bindings,
            )
        except AttemptStoreError as exc:
            raise _BrokerFailure(
                "database_error", "attempt_evidence_write_failed"
            ) from exc

    def _execute_sql(
        self,
        state: _EpisodeState,
        request: ToolRequestDTO,
        authority_receipt: str,
    ) -> dict[str, Any]:
        if (
            state.sql_attempts_used
            >= state.binding.limits.max_sql_attempts
        ):
            raise _BrokerFailure(
                "resource_limit", "sql_attempt_budget_exhausted"
            )
        state.sql_attempts_used += 1
        assert request.sql is not None
        sql_sha256 = hashlib.sha256(request.sql.encode("utf-8")).hexdigest()
        try:
            _, policy_receipt = self._policy(state, request.sql)
        except _BrokerFailure as failure:
            self._record_denied_or_failed(
                state=state,
                sql_sha256=sql_sha256,
                status="denied",
                error_code=failure.code,
                authority_receipt=authority_receipt,
                policy_accepted=False,
            )
            raise

        try:
            database_result = self._database.execute_read_only(
                state.binding.database_id,
                request.sql,
                max_rows=state.binding.limits.model_result_max_rows,
                max_bytes=state.binding.limits.model_result_max_bytes,
            )
            full_result = _full_query_result(
                database_result,
                max_rows=state.binding.limits.model_result_max_rows,
                max_bytes=state.binding.limits.model_result_max_bytes,
            )
        except DatabaseResourceLimitError as exc:
            self._record_denied_or_failed(
                state=state,
                sql_sha256=sql_sha256,
                status="failed",
                error_code="database_result_limit",
                authority_receipt=authority_receipt,
                policy_accepted=True,
                policy_receipt=policy_receipt,
            )
            raise _BrokerFailure(
                "resource_limit", "database_result_limit"
            ) from exc
        except Exception as exc:
            self._record_denied_or_failed(
                state=state,
                sql_sha256=sql_sha256,
                status="failed",
                error_code="read_only_execution_failed",
                authority_receipt=authority_receipt,
                policy_accepted=True,
                policy_receipt=policy_receipt,
            )
            raise _BrokerFailure(
                "database_error", "read_only_execution_failed"
            ) from exc

        bindings = {
            "authorization_epoch_ref_sha256": (
                state.binding.authorized_database_handle
                .authorization_epoch_ref_sha256
            ),
            "authority_snapshot_sha256": (
                state.binding.authorized_database_handle
                .authority_snapshot_sha256
            ),
            "authority_receipt_sha256": authority_receipt,
            "policy_receipt_sha256": policy_receipt,
            "catalog_sha256": state.catalog_sha256,
        }
        try:
            receipt = self._attempt_store.record_attempt(
                episode_ref=state.binding.episode_ref,
                candidate_sql_sha256=sql_sha256,
                status="executed",
                authority_valid=True,
                policy_accepted=True,
                query_result=full_result,
                bindings=bindings,
            )
        except AttemptStoreError as exc:
            raise _BrokerFailure(
                "database_error", "attempt_evidence_write_failed"
            ) from exc
        assert receipt.result_content_sha256 is not None

        preview_rows: list[list[dict[str, Any]]] = []
        all_rows = full_result["rows"]
        for row in all_rows[: self._preview_max_rows]:
            candidate = preview_rows + [row]
            preview_probe = {
                "columns": [
                    column.name for column in database_result.columns
                ],
                "rows": candidate,
                "row_count": len(all_rows),
                "preview_truncated": len(candidate) < len(all_rows),
                "result_sha256": receipt.result_content_sha256,
            }
            if len(canonical_json_bytes(preview_probe)) > self._preview_max_bytes:
                break
            preview_rows = candidate
        return {
            "schema_version": TOOL_RESPONSE_SCHEMA_VERSION,
            "request_nonce": request.request_nonce,
            "status": "ok",
            "attempt_id": receipt.attempt_id,
            "observation": {
                "columns": [
                    column.name for column in database_result.columns
                ],
                "rows": preview_rows,
                "row_count": len(all_rows),
                "preview_truncated": len(preview_rows) < len(all_rows),
                "result_sha256": receipt.result_content_sha256,
            },
            "authority_receipt_sha256": authority_receipt,
            "policy_receipt_sha256": policy_receipt,
            "remaining": self._remaining(state),
        }

    def _submit_sql(
        self,
        state: _EpisodeState,
        request: ToolRequestDTO,
        authority_receipt: str,
    ) -> dict[str, Any]:
        del authority_receipt
        assert request.attempt_id is not None
        try:
            receipt = self._attempt_store.submit(
                episode_ref=state.binding.episode_ref,
                attempt_id=request.attempt_id,
            )
        except (
            UnknownAttemptError,
            CrossEpisodeAttemptError,
            UnsubmittableAttemptError,
            EpisodeStateError,
        ) as exc:
            raise _BrokerFailure(
                "invalid_arguments", "attempt_capability_invalid"
            ) from exc
        except (AttemptStoreError, IntegrityError) as exc:
            raise _BrokerFailure(
                "database_error", "submission_integrity_failed"
            ) from exc
        state.terminal = True
        state.terminal_receipt_sha256 = receipt.ledger_root_sha256
        return {
            "schema_version": TOOL_RESPONSE_SCHEMA_VERSION,
            "request_nonce": request.request_nonce,
            "status": "accepted",
            "terminal": True,
            "submission_receipt_sha256": receipt.ledger_root_sha256,
        }

    def _abstain(
        self,
        state: _EpisodeState,
        request: ToolRequestDTO,
        authority_receipt: str,
    ) -> dict[str, Any]:
        assert request.reason_code is not None
        receipt_payload = {
            "schema_version": ABSTENTION_RECEIPT_SCHEMA_VERSION,
            "episode_ref": state.binding.episode_ref,
            "database_handle_sha256": hashlib.sha256(
                state.binding.authorized_database_handle.handle.encode(
                    "ascii"
                )
            ).hexdigest(),
            "reason_code": request.reason_code,
            "authority_receipt_sha256": authority_receipt,
            "request_nonce": request.request_nonce,
        }
        receipt = sha256_bytes(canonical_json_bytes(receipt_payload))
        state.terminal = True
        state.terminal_receipt_sha256 = receipt
        return {
            "schema_version": TOOL_RESPONSE_SCHEMA_VERSION,
            "request_nonce": request.request_nonce,
            "status": "accepted",
            "terminal": True,
            "abstention_receipt_sha256": receipt,
        }
