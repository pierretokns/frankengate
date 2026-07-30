"""Method-capability core for the isolated NL2SQL resolver.

This module intentionally exposes two public methods rather than a generic
method dispatcher.  ``issue_solver_episode`` can materialize only a strict
``SolverEpisodeDTO``.  ``resolve_gold`` can materialize only a signed,
evaluator-only gold envelope.  Capability lookup and peer-role checks happen
before either protected-content factory is invoked.

The transport is abstract.  ``peer_role`` is a trusted transport assertion in
this prototype; it is not evidence that Unix ``SO_PEERCRED`` has been checked.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import re
import secrets
import threading
from typing import Any, Callable, Mapping, Protocol

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from .dto import (
    DTOValidationError,
    STAGE_ROLES,
    SolverEpisodeDTO,
    canonical_json_bytes,
    decode_base64url,
    encode_base64url,
)


SUPERVISOR_REQUEST_SCHEMA_VERSION = "fg-resolver-solver-request-v1"
EVALUATOR_REQUEST_SCHEMA_VERSION = "fg-resolver-gold-request-v1"
EVALUATOR_GOLD_SCHEMA_VERSION = "fg-evaluator-gold-v1"
SIGNATURE_ALGORITHM = "Ed25519"
GOLD_SIGNATURE_DOMAIN = b"FG-EVALUATOR-GOLD-V1\0"

TRANSPORT_LIMITATION = (
    "peer_role is an abstract trusted transport assertion. This core does not "
    "open sockets, inspect SO_PEERCRED, create process identities, or prove "
    "filesystem/socket permissions."
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")
_CLASSIFICATION_RE = re.compile(r"^[a-z][a-z0-9_]{0,127}$")


class ResolverError(ValueError):
    """Resolver input, authority, state, or signed content is invalid."""


class ResolverAuthorizationError(ResolverError):
    """Peer role or method capability is not authorized."""


class ResolverReplayError(ResolverError):
    """A request nonce was already consumed."""


class GoldSigner(Protocol):
    """Narrow injected signing capability used only by ``resolve_gold``."""

    def sign(self, payload: Mapping[str, Any]) -> Mapping[str, str]:
        """Sign the canonical evaluator-gold payload."""


def _closed(
    value: Any, *, path: str, fields: frozenset[str]
) -> dict[str, Any]:
    if type(value) is not dict:
        raise ResolverError(f"{path} must be an object")
    unknown = set(value) - fields
    missing = fields - set(value)
    if unknown:
        raise ResolverError(
            f"{path} has unknown field(s): "
            + ", ".join(sorted(repr(item) for item in unknown))
        )
    if missing:
        raise ResolverError(
            f"{path} is missing field(s): " + ", ".join(sorted(missing))
        )
    return value


def _string(
    value: Any,
    *,
    path: str,
    max_bytes: int = 4096,
    allow_empty: bool = False,
) -> str:
    if type(value) is not str:
        raise ResolverError(f"{path} must be a string")
    try:
        encoded = value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise ResolverError(f"{path} is not valid Unicode") from exc
    if not allow_empty and not encoded:
        raise ResolverError(f"{path} must not be empty")
    if len(encoded) > max_bytes:
        raise ResolverError(f"{path} exceeds its {max_bytes}-byte limit")
    return value


def _identifier(value: Any, *, path: str) -> str:
    value = _string(value, path=path, max_bytes=256)
    if _ID_RE.fullmatch(value) is None or "\0" in value:
        raise ResolverError(f"{path} is not a valid identifier")
    return value


def _sha256(value: Any, *, path: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise ResolverError(f"{path} must be lowercase SHA-256 hex")
    return value


def _integer(
    value: Any, *, path: str, minimum: int = 0
) -> int:
    if type(value) is not int or not minimum <= value <= (1 << 53) - 1:
        raise ResolverError(
            f"{path} must be an integer from {minimum} through 2^53-1"
        )
    return value


def _opaque(
    value: Any, *, path: str, expected_nbytes: int
) -> str:
    value = _string(value, path=path, max_bytes=2048)
    try:
        decode_base64url(value, expected_nbytes=expected_nbytes)
    except DTOValidationError as exc:
        raise ResolverError(
            f"{path} must be canonical {expected_nbytes * 8}-bit base64url"
        ) from exc
    return value


@dataclass(frozen=True)
class _ResolverRequest:
    schema_version: str
    request_nonce: str
    experiment_id: str
    fold_id: str
    stage_role: str
    stage_manifest_sha256: str
    stage_episode_ref: str
    database_snapshot_sha256: str

    @classmethod
    def _from_dict(
        cls, value: Mapping[str, Any], *, schema_version: str
    ) -> "_ResolverRequest":
        item = _closed(
            dict(value),
            path="request",
            fields=frozenset(
                {
                    "schema_version",
                    "request_nonce",
                    "experiment_id",
                    "fold_id",
                    "stage_role",
                    "stage_manifest_sha256",
                    "stage_episode_ref",
                    "database_snapshot_sha256",
                }
            ),
        )
        if item["schema_version"] != schema_version:
            raise ResolverError(
                f"request.schema_version must equal {schema_version}"
            )
        stage_role = item["stage_role"]
        if type(stage_role) is not str or stage_role not in STAGE_ROLES:
            raise ResolverError("request.stage_role is invalid")
        return cls(
            schema_version=schema_version,
            request_nonce=_opaque(
                item["request_nonce"],
                path="request.request_nonce",
                expected_nbytes=16,
            ),
            experiment_id=_identifier(
                item["experiment_id"], path="request.experiment_id"
            ),
            fold_id=_identifier(item["fold_id"], path="request.fold_id"),
            stage_role=stage_role,
            stage_manifest_sha256=_sha256(
                item["stage_manifest_sha256"],
                path="request.stage_manifest_sha256",
            ),
            stage_episode_ref=_opaque(
                item["stage_episode_ref"],
                path="request.stage_episode_ref",
                expected_nbytes=32,
            ),
            database_snapshot_sha256=_sha256(
                item["database_snapshot_sha256"],
                path="request.database_snapshot_sha256",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "request_nonce": self.request_nonce,
            "experiment_id": self.experiment_id,
            "fold_id": self.fold_id,
            "stage_role": self.stage_role,
            "stage_manifest_sha256": self.stage_manifest_sha256,
            "stage_episode_ref": self.stage_episode_ref,
            "database_snapshot_sha256": self.database_snapshot_sha256,
        }


@dataclass(frozen=True)
class SupervisorEpisodeRequestDTO(_ResolverRequest):
    @classmethod
    def from_dict(
        cls, value: Mapping[str, Any]
    ) -> "SupervisorEpisodeRequestDTO":
        parsed = cls._from_dict(
            value, schema_version=SUPERVISOR_REQUEST_SCHEMA_VERSION
        )
        return cls(**parsed.__dict__)


@dataclass(frozen=True)
class EvaluatorGoldRequestDTO(_ResolverRequest):
    @classmethod
    def from_dict(
        cls, value: Mapping[str, Any]
    ) -> "EvaluatorGoldRequestDTO":
        parsed = cls._from_dict(
            value, schema_version=EVALUATOR_REQUEST_SCHEMA_VERSION
        )
        return cls(**parsed.__dict__)


@dataclass(frozen=True)
class ResolverEpisodeBinding:
    experiment_id: str
    fold_id: str
    stage_role: str
    stage_manifest_sha256: str
    stage_episode_ref: str
    database_snapshot_sha256: str
    question_sha256: str
    official_instructions_sha256: str
    expires_at_unix_ms: int
    solver_episode_factory: Callable[[], SolverEpisodeDTO]
    evaluator_gold_factory: Callable[[], Mapping[str, Any]]

    def __post_init__(self) -> None:
        _identifier(self.experiment_id, path="binding.experiment_id")
        _identifier(self.fold_id, path="binding.fold_id")
        if (
            type(self.stage_role) is not str
            or self.stage_role not in STAGE_ROLES
        ):
            raise ResolverError("binding.stage_role is invalid")
        _sha256(
            self.stage_manifest_sha256,
            path="binding.stage_manifest_sha256",
        )
        _opaque(
            self.stage_episode_ref,
            path="binding.stage_episode_ref",
            expected_nbytes=32,
        )
        _sha256(
            self.database_snapshot_sha256,
            path="binding.database_snapshot_sha256",
        )
        _sha256(self.question_sha256, path="binding.question_sha256")
        _sha256(
            self.official_instructions_sha256,
            path="binding.official_instructions_sha256",
        )
        _integer(
            self.expires_at_unix_ms,
            path="binding.expires_at_unix_ms",
            minimum=1,
        )
        if not callable(self.solver_episode_factory):
            raise ResolverError("binding.solver_episode_factory is not callable")
        if not callable(self.evaluator_gold_factory):
            raise ResolverError("binding.evaluator_gold_factory is not callable")


@dataclass(frozen=True)
class ResolverMethodCapabilities:
    supervisor_token: str
    evaluator_token: str


class Ed25519GoldSigner:
    """Domain-separated Ed25519 implementation of :class:`GoldSigner`."""

    def __init__(
        self, *, private_key: Ed25519PrivateKey, key_id: str
    ) -> None:
        self._private_key = private_key
        self.key_id = _identifier(key_id, path="resolver signer key_id")

    def sign(self, payload: Mapping[str, Any]) -> Mapping[str, str]:
        payload_bytes = canonical_json_bytes(dict(payload))
        return {
            "algorithm": SIGNATURE_ALGORITHM,
            "key_id": self.key_id,
            "payload_sha256": hashlib.sha256(payload_bytes).hexdigest(),
            "signature_base64url": encode_base64url(
                self._private_key.sign(GOLD_SIGNATURE_DOMAIN + payload_bytes)
            ),
        }


class ResolverCore:
    """In-memory method-capability resolver core with lazy protected content."""

    def __init__(
        self,
        *,
        gold_signer: GoldSigner,
        clock_unix_ms: Callable[[], int],
    ) -> None:
        if not callable(getattr(gold_signer, "sign", None)):
            raise ResolverError("gold_signer must implement sign(payload)")
        if not callable(clock_unix_ms):
            raise ResolverError("clock_unix_ms must be callable")
        self._gold_signer = gold_signer
        self._clock_unix_ms = clock_unix_ms
        self._supervisor_capabilities: dict[
            str, ResolverEpisodeBinding
        ] = {}
        self._evaluator_capabilities: dict[str, ResolverEpisodeBinding] = {}
        self._episode_keys: set[tuple[str, str, str, str]] = set()
        self._used_nonces: set[str] = set()
        self._lock = threading.Lock()

    def register_episode(
        self, binding: ResolverEpisodeBinding
    ) -> ResolverMethodCapabilities:
        if type(binding) is not ResolverEpisodeBinding:
            raise ResolverError("binding must be a ResolverEpisodeBinding")
        key = (
            binding.experiment_id,
            binding.fold_id,
            binding.stage_role,
            binding.stage_episode_ref,
        )
        supervisor_token = encode_base64url(secrets.token_bytes(32))
        evaluator_token = encode_base64url(secrets.token_bytes(32))
        with self._lock:
            if key in self._episode_keys:
                raise ResolverError("episode binding is already registered")
            self._episode_keys.add(key)
            self._supervisor_capabilities[
                self._token_digest(supervisor_token)
            ] = binding
            self._evaluator_capabilities[
                self._token_digest(evaluator_token)
            ] = binding
        return ResolverMethodCapabilities(
            supervisor_token=supervisor_token,
            evaluator_token=evaluator_token,
        )

    def issue_solver_episode(
        self,
        *,
        peer_role: str,
        capability_token: str,
        request: SupervisorEpisodeRequestDTO,
    ) -> SolverEpisodeDTO:
        """Authorize the supervisor surface and return only a solver DTO."""

        binding = self._authorize_supervisor(
            peer_role=peer_role,
            capability_token=capability_token,
            request=request,
        )
        try:
            episode = binding.solver_episode_factory()
        except Exception:
            raise ResolverError("solver episode materialization failed") from None
        if type(episode) is not SolverEpisodeDTO:
            raise ResolverError(
                "solver episode factory must return a SolverEpisodeDTO"
            )
        # Re-parse the public representation to defend against constructed
        # subclasses or post-init bypasses.
        episode = SolverEpisodeDTO.from_dict(episode.to_dict())
        episode_hashes = (
            (
                "question_sha256",
                hashlib.sha256(episode.question.encode("utf-8")).hexdigest(),
                binding.question_sha256,
            ),
            (
                "official_instructions_sha256",
                hashlib.sha256(
                    episode.official_instructions.encode("utf-8")
                ).hexdigest(),
                binding.official_instructions_sha256,
            ),
        )
        for field, actual, expected in episode_hashes:
            if not hmac.compare_digest(actual, expected):
                raise ResolverError(
                    f"solver {field} is outside the episode binding"
                )
        if (
            episode.authorized_database_handle.expires_at_unix_ms
            > binding.expires_at_unix_ms
        ):
            raise ResolverError(
                "solver database handle outlives resolver capability"
            )
        self._ensure_current(binding)
        return episode

    def resolve_gold(
        self,
        *,
        peer_role: str,
        capability_token: str,
        request: EvaluatorGoldRequestDTO,
    ) -> dict[str, Any]:
        """Authorize the evaluator surface and return one signed gold DTO."""

        binding = self._authorize_evaluator(
            peer_role=peer_role,
            capability_token=capability_token,
            request=request,
        )
        try:
            raw_material = binding.evaluator_gold_factory()
        except Exception:
            raise ResolverError("evaluator gold materialization failed") from None
        material = _validate_gold_material(raw_material)
        for field in (
            "question_sha256",
            "official_instructions_sha256",
        ):
            if not hmac.compare_digest(
                material[field], getattr(binding, field)
            ):
                raise ResolverError(
                    f"gold {field} is outside the episode binding"
                )
        payload = {
            "schema_version": EVALUATOR_GOLD_SCHEMA_VERSION,
            "request_nonce": request.request_nonce,
            "experiment_id": binding.experiment_id,
            "fold_id": binding.fold_id,
            "stage_role": binding.stage_role,
            "stage_episode_ref": binding.stage_episode_ref,
            "source_task_id": material["source_task_id"],
            "source_locator": material["source_locator"],
            "question_sha256": material["question_sha256"],
            "official_instructions_sha256": material[
                "official_instructions_sha256"
            ],
            "gold_sql_alternatives": material["gold_sql_alternatives"],
            "gold_sql_sha256": material["gold_sql_sha256"],
            "database_snapshot_sha256": binding.database_snapshot_sha256,
            "evaluator_database_handle": material[
                "evaluator_database_handle"
            ],
            "adjudication": material["adjudication"],
            "cohort_manifest_sha256": material[
                "cohort_manifest_sha256"
            ],
            "dataset_manifest_sha256": material[
                "dataset_manifest_sha256"
            ],
            "stage_manifest_sha256": binding.stage_manifest_sha256,
            "resolver_capability_expires_at_unix_ms": (
                binding.expires_at_unix_ms
            ),
        }
        payload = _validate_gold_payload(payload)
        self._ensure_current(binding)
        try:
            signature = dict(self._gold_signer.sign(payload))
        except Exception:
            raise ResolverError("evaluator gold signing failed") from None
        self._ensure_current(binding)
        envelope = {
            "payload": payload,
            "resolver_signature": signature,
        }
        _validate_gold_envelope_shape(envelope)
        return envelope

    def _authorize_supervisor(
        self,
        *,
        peer_role: str,
        capability_token: str,
        request: SupervisorEpisodeRequestDTO,
    ) -> ResolverEpisodeBinding:
        if peer_role != "supervisor":
            raise ResolverAuthorizationError(
                "peer role cannot issue solver episodes"
            )
        if type(request) is not SupervisorEpisodeRequestDTO:
            raise ResolverAuthorizationError(
                "supervisor method requires its exact request DTO"
            )
        return self._authorize_binding(
            capability_token=capability_token,
            request=request,
            capability_map=self._supervisor_capabilities,
        )

    def _authorize_evaluator(
        self,
        *,
        peer_role: str,
        capability_token: str,
        request: EvaluatorGoldRequestDTO,
    ) -> ResolverEpisodeBinding:
        if peer_role != "evaluator":
            raise ResolverAuthorizationError("peer role cannot resolve gold")
        if type(request) is not EvaluatorGoldRequestDTO:
            raise ResolverAuthorizationError(
                "evaluator method requires its exact request DTO"
            )
        return self._authorize_binding(
            capability_token=capability_token,
            request=request,
            capability_map=self._evaluator_capabilities,
        )

    def _authorize_binding(
        self,
        *,
        capability_token: str,
        request: _ResolverRequest,
        capability_map: Mapping[str, ResolverEpisodeBinding],
    ) -> ResolverEpisodeBinding:
        token = _opaque(
            capability_token,
            path="capability_token",
            expected_nbytes=32,
        )
        binding = capability_map.get(self._token_digest(token))
        if binding is None:
            raise ResolverAuthorizationError(
                "method capability is unknown or belongs to another method"
            )
        expected = (
            ("experiment_id", binding.experiment_id),
            ("fold_id", binding.fold_id),
            ("stage_role", binding.stage_role),
            ("stage_manifest_sha256", binding.stage_manifest_sha256),
            ("stage_episode_ref", binding.stage_episode_ref),
            (
                "database_snapshot_sha256",
                binding.database_snapshot_sha256,
            ),
        )
        for field, value in expected:
            if not hmac.compare_digest(getattr(request, field), value):
                raise ResolverAuthorizationError(
                    f"request {field} is outside the method capability"
                )
        self._ensure_current(binding)
        with self._lock:
            if request.request_nonce in self._used_nonces:
                raise ResolverReplayError("request nonce has already been used")
            self._used_nonces.add(request.request_nonce)
        return binding

    def _ensure_current(self, binding: ResolverEpisodeBinding) -> None:
        now_unix_ms = self._clock_unix_ms()
        _integer(now_unix_ms, path="clock_unix_ms", minimum=1)
        if now_unix_ms >= binding.expires_at_unix_ms:
            raise ResolverAuthorizationError("method capability has expired")

    @staticmethod
    def _token_digest(token: str) -> str:
        return hashlib.sha256(token.encode("ascii")).hexdigest()


_GOLD_MATERIAL_FIELDS = frozenset(
    {
        "source_task_id",
        "source_locator",
        "question_sha256",
        "official_instructions_sha256",
        "gold_sql_alternatives",
        "gold_sql_sha256",
        "evaluator_database_handle",
        "adjudication",
        "cohort_manifest_sha256",
        "dataset_manifest_sha256",
    }
)


def _validate_gold_material(value: Any) -> dict[str, Any]:
    material = _closed(
        dict(value), path="gold_material", fields=_GOLD_MATERIAL_FIELDS
    )
    _string(
        material["source_task_id"],
        path="gold_material.source_task_id",
        max_bytes=4096,
    )
    locator = _closed(
        material["source_locator"],
        path="gold_material.source_locator",
        fields=frozenset({"source_file_sha256", "source_row_0based"}),
    )
    _sha256(
        locator["source_file_sha256"],
        path="gold_material.source_locator.source_file_sha256",
    )
    _integer(
        locator["source_row_0based"],
        path="gold_material.source_locator.source_row_0based",
    )
    _sha256(
        material["question_sha256"],
        path="gold_material.question_sha256",
    )
    _sha256(
        material["official_instructions_sha256"],
        path="gold_material.official_instructions_sha256",
    )
    alternatives = material["gold_sql_alternatives"]
    if (
        type(alternatives) is not list
        or not alternatives
        or len(alternatives) > 64
    ):
        raise ResolverError(
            "gold_material.gold_sql_alternatives must contain 1 to 64 items"
        )
    for index, sql in enumerate(alternatives):
        _string(
            sql,
            path=f"gold_material.gold_sql_alternatives[{index}]",
            max_bytes=4 * 1024 * 1024,
        )
    gold_sql_sha256 = _sha256(
        material["gold_sql_sha256"],
        path="gold_material.gold_sql_sha256",
    )
    expected_gold_sha256 = hashlib.sha256(
        canonical_json_bytes(alternatives)
    ).hexdigest()
    if not hmac.compare_digest(gold_sql_sha256, expected_gold_sha256):
        raise ResolverError(
            "gold_material.gold_sql_sha256 does not match alternatives"
        )
    _opaque(
        material["evaluator_database_handle"],
        path="gold_material.evaluator_database_handle",
        expected_nbytes=32,
    )
    adjudication = _closed(
        material["adjudication"],
        path="gold_material.adjudication",
        fields=frozenset(
            {
                "classification",
                "primary_quality_eligible",
                "required_sensitive_entitlements",
            }
        ),
    )
    classification = _string(
        adjudication["classification"],
        path="gold_material.adjudication.classification",
        max_bytes=128,
    )
    if _CLASSIFICATION_RE.fullmatch(classification) is None:
        raise ResolverError("gold material classification is invalid")
    if type(adjudication["primary_quality_eligible"]) is not bool:
        raise ResolverError(
            "gold material primary_quality_eligible must be boolean"
        )
    entitlements = adjudication["required_sensitive_entitlements"]
    if type(entitlements) is not list or len(entitlements) > 1024:
        raise ResolverError(
            "required_sensitive_entitlements must be a bounded list"
        )
    for index, entitlement in enumerate(entitlements):
        _identifier(
            entitlement,
            path=(
                "gold_material.adjudication."
                f"required_sensitive_entitlements[{index}]"
            ),
        )
    if len(entitlements) != len(set(entitlements)):
        raise ResolverError("sensitive entitlements must be unique")
    for field in ("cohort_manifest_sha256", "dataset_manifest_sha256"):
        _sha256(material[field], path=f"gold_material.{field}")
    return material


_GOLD_PAYLOAD_FIELDS = frozenset(
    {
        "schema_version",
        "request_nonce",
        "experiment_id",
        "fold_id",
        "stage_role",
        "stage_episode_ref",
        "source_task_id",
        "source_locator",
        "question_sha256",
        "official_instructions_sha256",
        "gold_sql_alternatives",
        "gold_sql_sha256",
        "database_snapshot_sha256",
        "evaluator_database_handle",
        "adjudication",
        "cohort_manifest_sha256",
        "dataset_manifest_sha256",
        "stage_manifest_sha256",
        "resolver_capability_expires_at_unix_ms",
    }
)


def _validate_gold_payload(value: Any) -> dict[str, Any]:
    payload = _closed(
        dict(value), path="gold payload", fields=_GOLD_PAYLOAD_FIELDS
    )
    if payload["schema_version"] != EVALUATOR_GOLD_SCHEMA_VERSION:
        raise ResolverError("invalid evaluator-gold schema version")
    _opaque(
        payload["request_nonce"],
        path="gold payload.request_nonce",
        expected_nbytes=16,
    )
    _identifier(
        payload["experiment_id"],
        path="gold payload.experiment_id",
    )
    _identifier(payload["fold_id"], path="gold payload.fold_id")
    if payload["stage_role"] not in STAGE_ROLES:
        raise ResolverError("gold payload.stage_role is invalid")
    _opaque(
        payload["stage_episode_ref"],
        path="gold payload.stage_episode_ref",
        expected_nbytes=32,
    )
    material = {
        field: payload[field] for field in _GOLD_MATERIAL_FIELDS
    }
    _validate_gold_material(material)
    _sha256(
        payload["database_snapshot_sha256"],
        path="gold payload.database_snapshot_sha256",
    )
    _sha256(
        payload["stage_manifest_sha256"],
        path="gold payload.stage_manifest_sha256",
    )
    _integer(
        payload["resolver_capability_expires_at_unix_ms"],
        path="gold payload.resolver_capability_expires_at_unix_ms",
        minimum=1,
    )
    return payload


def _validate_gold_envelope_shape(value: Any) -> dict[str, Any]:
    envelope = _closed(
        value,
        path="$",
        fields=frozenset({"payload", "resolver_signature"}),
    )
    _validate_gold_payload(envelope["payload"])
    signature = _closed(
        envelope["resolver_signature"],
        path="resolver_signature",
        fields=frozenset(
            {
                "algorithm",
                "key_id",
                "payload_sha256",
                "signature_base64url",
            }
        ),
    )
    if signature["algorithm"] != SIGNATURE_ALGORITHM:
        raise ResolverError("resolver signature algorithm must be Ed25519")
    _identifier(signature["key_id"], path="resolver_signature.key_id")
    _sha256(
        signature["payload_sha256"],
        path="resolver_signature.payload_sha256",
    )
    _opaque(
        signature["signature_base64url"],
        path="resolver_signature.signature_base64url",
        expected_nbytes=64,
    )
    return envelope


def verify_evaluator_gold_envelope(
    envelope: Any,
    *,
    public_key: Ed25519PublicKey,
    expected_key_id: str,
) -> dict[str, Any]:
    """Validate and verify a resolver-signed evaluator-gold envelope."""

    envelope = _validate_gold_envelope_shape(envelope)
    payload = envelope["payload"]
    signature = envelope["resolver_signature"]
    expected_key_id = _identifier(
        expected_key_id, path="expected resolver key_id"
    )
    if not hmac.compare_digest(signature["key_id"], expected_key_id):
        raise ResolverError("resolver signature key ID does not match")
    payload_bytes = canonical_json_bytes(payload)
    payload_sha256 = hashlib.sha256(payload_bytes).hexdigest()
    if not hmac.compare_digest(
        signature["payload_sha256"], payload_sha256
    ):
        raise ResolverError("resolver signature payload hash does not match")
    try:
        public_key.verify(
            decode_base64url(
                signature["signature_base64url"], expected_nbytes=64
            ),
            GOLD_SIGNATURE_DOMAIN + payload_bytes,
        )
    except (DTOValidationError, InvalidSignature) as exc:
        raise ResolverError("resolver signature verification failed") from exc
    return payload
