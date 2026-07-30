"""Offline signing and hidden-stage encryption for NL2SQL stage manifests.

The public artifact is a content-free commitment.  A signed stage manifest is
trusted resolver/evaluator input and is not a public or solver-facing DTO.
Hidden-stage manifests are signed before encryption and encrypted to exactly
one X25519 recipient using an ephemeral key, HKDF-SHA256, and ChaCha20-Poly1305.
Opening also requires a separately signed pass-only authorization that binds
the exact envelope, selection receipt, independently signed fold artifacts,
and frozen runtime/evaluator hashes.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import threading
from typing import Any, Mapping, MutableSet, Sequence

from cryptography.exceptions import InvalidSignature, InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from .dto import (
    DTOValidationError,
    STAGE_ROLES,
    canonical_json_bytes,
    decode_base64url,
    derive_stage_episode_ref,
    encode_base64url,
)


STAGE_MANIFEST_SCHEMA_VERSION = "fg-stage-manifest-v1"
STAGE_COMMITMENT_SCHEMA_VERSION = "fg-stage-commitment-v1"
HIDDEN_ENVELOPE_SCHEMA_VERSION = "fg-hidden-stage-envelope-v1"
HIDDEN_UNSEAL_AUTHORIZATION_SCHEMA_VERSION = (
    "fg-hidden-unseal-authorization-v1"
)
SELECTION_GATE_RECEIPT_SCHEMA_VERSION = "fg-selection-gate-receipt-v1"
CANDIDATE_ARTIFACT_RECEIPT_SCHEMA_VERSION = (
    "fg-candidate-artifact-receipt-v1"
)
SIGNATURE_ALGORITHM = "Ed25519"
HIDDEN_ENCRYPTION_ALGORITHM = (
    "X25519-HKDF-SHA256-ChaCha20Poly1305"
)

_STAGE_SIGNATURE_DOMAIN = b"FG-STAGE-MANIFEST-V1\0"
_COMMITMENT_SIGNATURE_DOMAIN = b"FG-STAGE-COMMITMENT-V1\0"
_HIDDEN_ENVELOPE_SIGNATURE_DOMAIN = b"FG-HIDDEN-STAGE-ENVELOPE-V1\0"
_HIDDEN_UNSEAL_SIGNATURE_DOMAIN = b"FG-HIDDEN-UNSEAL-AUTHORIZATION-V1\0"
_CANDIDATE_ARTIFACT_SIGNATURE_DOMAIN = (
    b"FG-CANDIDATE-ARTIFACT-RECEIPT-V1\0"
)
_HIDDEN_ENCRYPTION_INFO = b"FG-HIDDEN-STAGE-ENVELOPE-V1\0content-key"
_ORDERED_EPISODE_DOMAIN = b"FG-STAGE-EPISODE-COMMITMENT-V1\0"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}$")
_DATABASE_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_QUERY_CATEGORY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_ALLOWED_ARMS = frozenset({"baseline", "placebo", "expert"})
_ALLOWED_RUNTIME_ROLES = frozenset({"resolver", "evaluator"})
_UNSEAL_BINDING_FIELDS = (
    "model_manifest_sha256",
    "prompt_contract_sha256",
    "tool_contract_sha256",
    "policy_version_sha256",
    "comparator_version_sha256",
    "database_snapshots_sha256",
    "authority_snapshot_sha256",
)

REPLAY_GUARD_LIMITATION = (
    "HiddenEnvelopeReplayGuard is process-local and not crash-durable. "
    "Production one-time unseal requires an atomic durable receipt ledger "
    "or equivalent transactional store keyed by the stable hidden-stage "
    "identity."
)
ENVELOPE_FORMAT_LIMITATION = (
    "The research envelope uses audited cryptography primitives but is not "
    "the age wire format. Production should use age or a managed KMS envelope "
    "when interoperability, centralized key lifecycle, or independent format "
    "review is required."
)


class StageSealError(ValueError):
    """A stage artifact is malformed or fails cryptographic verification."""


class StageReplayError(StageSealError):
    """A successfully opened hidden envelope is being reused."""


def _closed(
    value: Any, *, path: str, fields: frozenset[str]
) -> dict[str, Any]:
    if type(value) is not dict:
        raise StageSealError(f"{path} must be an object")
    unknown = set(value) - fields
    missing = fields - set(value)
    if unknown:
        raise StageSealError(
            f"{path} has unknown field(s): "
            + ", ".join(sorted(repr(item) for item in unknown))
        )
    if missing:
        raise StageSealError(
            f"{path} is missing required field(s): "
            + ", ".join(sorted(missing))
        )
    return value


def _string(
    value: Any, *, path: str, max_bytes: int = 4096
) -> str:
    if type(value) is not str or not value:
        raise StageSealError(f"{path} must be a non-empty string")
    try:
        encoded = value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as exc:
        raise StageSealError(f"{path} must be valid Unicode") from exc
    if len(encoded) > max_bytes:
        raise StageSealError(f"{path} exceeds its {max_bytes}-byte limit")
    return value


def _identifier(value: Any, *, path: str) -> str:
    parsed = _string(value, path=path, max_bytes=256)
    if _ID_RE.fullmatch(parsed) is None or "\0" in parsed:
        raise StageSealError(f"{path} is not a valid identifier")
    return parsed


def _sha256(value: Any, *, path: str) -> str:
    if type(value) is not str or _SHA256_RE.fullmatch(value) is None:
        raise StageSealError(f"{path} must be lowercase SHA-256 hex")
    return value


def _integer(
    value: Any, *, path: str, minimum: int = 0
) -> int:
    if type(value) is not int or value < minimum or value > (1 << 53) - 1:
        raise StageSealError(
            f"{path} must be an integer from {minimum} to 2^53-1"
        )
    return value


def _hash_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _public_key_bytes(
    key: Ed25519PublicKey | X25519PublicKey,
) -> bytes:
    return key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def _signature(
    *,
    private_key: Ed25519PrivateKey,
    key_id: str,
    payload: Mapping[str, Any],
    domain: bytes,
) -> dict[str, str]:
    key_id = _identifier(key_id, path="key_id")
    payload_bytes = canonical_json_bytes(dict(payload))
    return {
        "algorithm": SIGNATURE_ALGORITHM,
        "key_id": key_id,
        "payload_sha256": _hash_bytes(payload_bytes),
        "signature_base64url": encode_base64url(
            private_key.sign(domain + payload_bytes)
        ),
    }


def _verify_signature(
    *,
    payload: Mapping[str, Any],
    signature: Any,
    public_key: Ed25519PublicKey,
    expected_key_id: str,
    domain: bytes,
) -> None:
    signature = _closed(
        signature,
        path="signature",
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
        raise StageSealError("signature.algorithm must equal Ed25519")
    if not hmac.compare_digest(
        _identifier(signature["key_id"], path="signature.key_id"),
        _identifier(expected_key_id, path="expected_key_id"),
    ):
        raise StageSealError("signature key ID does not match")
    payload_bytes = canonical_json_bytes(dict(payload))
    payload_sha256 = _sha256(
        signature["payload_sha256"], path="signature.payload_sha256"
    )
    if not hmac.compare_digest(payload_sha256, _hash_bytes(payload_bytes)):
        raise StageSealError("signature payload hash does not match")
    try:
        raw_signature = decode_base64url(
            signature["signature_base64url"], expected_nbytes=64
        )
        public_key.verify(raw_signature, domain + payload_bytes)
    except (DTOValidationError, InvalidSignature) as exc:
        raise StageSealError("signature verification failed") from exc


def _validate_episode(
    value: Any,
    *,
    index: int,
    experiment_id: str,
    fold_id: str,
    stage_role: str,
    stage_id_key: bytes | None,
) -> dict[str, Any]:
    path = f"payload.episodes[{index}]"
    episode = _closed(
        value,
        path=path,
        fields=frozenset(
            {
                "stage_episode_ref",
                "source_task_id",
                "source_file_sha256",
                "source_row_0based",
                "question_sha256",
                "official_instructions_sha256",
                "gold_sql_sha256",
                "database_ref",
                "query_category",
                "primary_quality_eligible",
                "adjudication_ref",
                "paired_seed",
                "arm_order",
            }
        ),
    )
    source_task_id = _string(
        episode["source_task_id"],
        path=f"{path}.source_task_id",
        max_bytes=4096,
    )
    stage_episode_ref = _string(
        episode["stage_episode_ref"],
        path=f"{path}.stage_episode_ref",
        max_bytes=128,
    )
    try:
        decode_base64url(stage_episode_ref, expected_nbytes=32)
    except DTOValidationError as exc:
        raise StageSealError(
            f"{path}.stage_episode_ref must be a 256-bit base64url value"
        ) from exc
    if stage_id_key is not None:
        try:
            expected_ref = derive_stage_episode_ref(
                key=stage_id_key,
                experiment_id=experiment_id,
                fold_id=fold_id,
                stage_role=stage_role,
                source_task_id=source_task_id,
            )
        except DTOValidationError as exc:
            raise StageSealError(str(exc)) from exc
        if not hmac.compare_digest(stage_episode_ref, expected_ref):
            raise StageSealError(
                f"{path}.stage_episode_ref is not bound to its "
                "experiment/fold/stage/source"
            )
    _sha256(episode["source_file_sha256"], path=f"{path}.source_file_sha256")
    _integer(episode["source_row_0based"], path=f"{path}.source_row_0based")
    _sha256(episode["question_sha256"], path=f"{path}.question_sha256")
    _sha256(
        episode["official_instructions_sha256"],
        path=f"{path}.official_instructions_sha256",
    )
    _sha256(episode["gold_sql_sha256"], path=f"{path}.gold_sql_sha256")
    database_ref = _string(
        episode["database_ref"], path=f"{path}.database_ref", max_bytes=128
    )
    if _DATABASE_REF_RE.fullmatch(database_ref) is None:
        raise StageSealError(f"{path}.database_ref is invalid")
    query_category = _string(
        episode["query_category"],
        path=f"{path}.query_category",
        max_bytes=128,
    )
    if _QUERY_CATEGORY_RE.fullmatch(query_category) is None:
        raise StageSealError(f"{path}.query_category is invalid")
    if type(episode["primary_quality_eligible"]) is not bool:
        raise StageSealError(
            f"{path}.primary_quality_eligible must be a boolean"
        )
    adjudication_ref = episode["adjudication_ref"]
    if adjudication_ref is not None:
        _identifier(adjudication_ref, path=f"{path}.adjudication_ref")
    _integer(episode["paired_seed"], path=f"{path}.paired_seed")
    arm_order = episode["arm_order"]
    if (
        type(arm_order) is not list
        or len(arm_order) != len(_ALLOWED_ARMS)
        or set(arm_order) != _ALLOWED_ARMS
        or any(type(arm) is not str for arm in arm_order)
    ):
        raise StageSealError(
            f"{path}.arm_order must be a permutation of "
            "baseline, placebo, and expert"
        )
    return episode


def ordered_episode_commitment_sha256(episodes: Any) -> str:
    """Commit to the exact ordered closed episode objects."""

    if type(episodes) is not list:
        raise StageSealError("episodes must be a list")
    try:
        encoded = canonical_json_bytes(episodes)
    except DTOValidationError as exc:
        raise StageSealError(str(exc)) from exc
    return _hash_bytes(_ORDERED_EPISODE_DOMAIN + encoded)


def _validate_manifest_payload(
    value: Any, *, stage_id_key: bytes | None
) -> dict[str, Any]:
    payload = _closed(
        value,
        path="payload",
        fields=frozenset(
            {
                "schema_version",
                "experiment_id",
                "fold_id",
                "stage_role",
                "manifest_sequence",
                "created_at_unix_ms",
                "parent_design_sha256",
                "cohort_manifest_sha256",
                "dataset_manifest_sha256",
                "prompt_contract_sha256",
                "tool_contract_sha256",
                "model_manifest_sha256",
                "authority_snapshot_sha256",
                "policy_version_sha256",
                "comparator_version_sha256",
                "database_snapshots",
                "artifact_set_sha256",
                "selection_gate_contract_sha256",
                "episode_count",
                "ordered_episode_commitment_sha256",
                "episodes",
                "allowed_runtime_roles",
            }
        ),
    )
    if payload["schema_version"] != STAGE_MANIFEST_SCHEMA_VERSION:
        raise StageSealError(
            "payload.schema_version must equal fg-stage-manifest-v1"
        )
    experiment_id = _identifier(
        payload["experiment_id"], path="payload.experiment_id"
    )
    fold_id = _identifier(payload["fold_id"], path="payload.fold_id")
    stage_role = payload["stage_role"]
    if stage_role not in STAGE_ROLES:
        raise StageSealError(
            "payload.stage_role must be evidence, visible_selection, or "
            "hidden_test"
        )
    _integer(
        payload["manifest_sequence"],
        path="payload.manifest_sequence",
        minimum=1,
    )
    _integer(
        payload["created_at_unix_ms"],
        path="payload.created_at_unix_ms",
        minimum=1,
    )
    for field in (
        "parent_design_sha256",
        "cohort_manifest_sha256",
        "dataset_manifest_sha256",
        "prompt_contract_sha256",
        "tool_contract_sha256",
        "model_manifest_sha256",
        "authority_snapshot_sha256",
        "policy_version_sha256",
        "comparator_version_sha256",
        "artifact_set_sha256",
        "selection_gate_contract_sha256",
        "ordered_episode_commitment_sha256",
    ):
        _sha256(payload[field], path=f"payload.{field}")
    snapshots = payload["database_snapshots"]
    if type(snapshots) is not list or not snapshots:
        raise StageSealError("payload.database_snapshots must be non-empty")
    database_refs: set[str] = set()
    for index, value in enumerate(snapshots):
        snapshot = _closed(
            value,
            path=f"payload.database_snapshots[{index}]",
            fields=frozenset({"database_ref", "snapshot_sha256"}),
        )
        database_ref = _string(
            snapshot["database_ref"],
            path=f"payload.database_snapshots[{index}].database_ref",
            max_bytes=128,
        )
        if (
            _DATABASE_REF_RE.fullmatch(database_ref) is None
            or database_ref in database_refs
        ):
            raise StageSealError(
                "payload.database_snapshots database_ref values must be "
                "valid and unique"
            )
        database_refs.add(database_ref)
        _sha256(
            snapshot["snapshot_sha256"],
            path=f"payload.database_snapshots[{index}].snapshot_sha256",
        )
    episodes = payload["episodes"]
    if type(episodes) is not list:
        raise StageSealError("payload.episodes must be a list")
    episode_count = _integer(
        payload["episode_count"], path="payload.episode_count"
    )
    if episode_count != len(episodes):
        raise StageSealError("payload.episode_count does not match episodes")
    seen_refs: set[str] = set()
    for index, episode_value in enumerate(episodes):
        episode = _validate_episode(
            episode_value,
            index=index,
            experiment_id=experiment_id,
            fold_id=fold_id,
            stage_role=stage_role,
            stage_id_key=stage_id_key,
        )
        if episode["database_ref"] not in database_refs:
            raise StageSealError(
                f"payload.episodes[{index}].database_ref is not declared"
            )
        if episode["stage_episode_ref"] in seen_refs:
            raise StageSealError("stage_episode_ref values must be unique")
        seen_refs.add(episode["stage_episode_ref"])
    expected_commitment = ordered_episode_commitment_sha256(episodes)
    if not hmac.compare_digest(
        payload["ordered_episode_commitment_sha256"],
        expected_commitment,
    ):
        raise StageSealError(
            "payload.ordered_episode_commitment_sha256 does not match episodes"
        )
    roles = payload["allowed_runtime_roles"]
    if (
        type(roles) is not list
        or not roles
        or any(type(role) is not str for role in roles)
        or len(roles) != len(set(roles))
        or not set(roles).issubset(_ALLOWED_RUNTIME_ROLES)
    ):
        raise StageSealError(
            "payload.allowed_runtime_roles must be unique resolver/evaluator "
            "roles"
        )
    return payload


def sign_stage_manifest(
    payload: Mapping[str, Any],
    *,
    private_key: Ed25519PrivateKey,
    key_id: str,
    stage_id_key: bytes,
) -> dict[str, Any]:
    """Validate and sign an access-controlled stage manifest."""

    validated = _validate_manifest_payload(
        dict(payload), stage_id_key=stage_id_key
    )
    return {
        "payload": validated,
        "signature": _signature(
            private_key=private_key,
            key_id=key_id,
            payload=validated,
            domain=_STAGE_SIGNATURE_DOMAIN,
        ),
    }


def verify_stage_manifest(
    signed_manifest: Any,
    *,
    public_key: Ed25519PublicKey,
    expected_key_id: str,
    stage_id_key: bytes | None = None,
    expected_experiment_id: str | None = None,
    expected_fold_id: str | None = None,
    expected_stage_role: str | None = None,
) -> dict[str, Any]:
    """Verify signature, schema, optional source binding, and context."""

    document = _closed(
        signed_manifest,
        path="$",
        fields=frozenset({"payload", "signature"}),
    )
    payload = _validate_manifest_payload(
        document["payload"], stage_id_key=stage_id_key
    )
    _verify_signature(
        payload=payload,
        signature=document["signature"],
        public_key=public_key,
        expected_key_id=expected_key_id,
        domain=_STAGE_SIGNATURE_DOMAIN,
    )
    expected = {
        "experiment_id": expected_experiment_id,
        "fold_id": expected_fold_id,
        "stage_role": expected_stage_role,
    }
    for field, expected_value in expected.items():
        if expected_value is not None and not hmac.compare_digest(
            payload[field], expected_value
        ):
            raise StageSealError(
                f"manifest {field} does not match the expected context"
            )
    return payload


_COMMITMENT_INPUT_FIELDS = (
    "parent_design_sha256",
    "cohort_manifest_sha256",
    "dataset_manifest_sha256",
    "prompt_contract_sha256",
    "tool_contract_sha256",
    "model_manifest_sha256",
    "authority_snapshot_sha256",
    "policy_version_sha256",
    "comparator_version_sha256",
    "artifact_set_sha256",
    "selection_gate_contract_sha256",
)


def build_stage_commitment(
    signed_manifest: Mapping[str, Any],
    *,
    manifest_public_key: Ed25519PublicKey,
    manifest_key_id: str,
    commitment_private_key: Ed25519PrivateKey,
    commitment_key_id: str,
) -> dict[str, Any]:
    """Build a separately signed, public, content-free stage commitment."""

    manifest_payload = verify_stage_manifest(
        signed_manifest,
        public_key=manifest_public_key,
        expected_key_id=manifest_key_id,
    )
    manifest_payload_bytes = canonical_json_bytes(manifest_payload)
    payload = {
        "schema_version": STAGE_COMMITMENT_SCHEMA_VERSION,
        "experiment_id": manifest_payload["experiment_id"],
        "fold_id": manifest_payload["fold_id"],
        "stage_role": manifest_payload["stage_role"],
        "manifest_sequence": manifest_payload["manifest_sequence"],
        "created_at_unix_ms": manifest_payload["created_at_unix_ms"],
        "episode_count": manifest_payload["episode_count"],
        "input_hashes": {
            field: manifest_payload[field] for field in _COMMITMENT_INPUT_FIELDS
        },
        "stage_manifest_payload_sha256": _hash_bytes(manifest_payload_bytes),
        "ordered_episode_commitment_sha256": manifest_payload[
            "ordered_episode_commitment_sha256"
        ],
        "manifest_signer_key_id": manifest_key_id,
    }
    return {
        "payload": payload,
        "signature": _signature(
            private_key=commitment_private_key,
            key_id=commitment_key_id,
            payload=payload,
            domain=_COMMITMENT_SIGNATURE_DOMAIN,
        ),
    }


def _validate_commitment_payload(value: Any) -> dict[str, Any]:
    payload = _closed(
        value,
        path="payload",
        fields=frozenset(
            {
                "schema_version",
                "experiment_id",
                "fold_id",
                "stage_role",
                "manifest_sequence",
                "created_at_unix_ms",
                "episode_count",
                "input_hashes",
                "stage_manifest_payload_sha256",
                "ordered_episode_commitment_sha256",
                "manifest_signer_key_id",
            }
        ),
    )
    if payload["schema_version"] != STAGE_COMMITMENT_SCHEMA_VERSION:
        raise StageSealError("invalid stage commitment schema version")
    _identifier(payload["experiment_id"], path="payload.experiment_id")
    _identifier(payload["fold_id"], path="payload.fold_id")
    if payload["stage_role"] not in STAGE_ROLES:
        raise StageSealError("invalid commitment stage role")
    _integer(payload["manifest_sequence"], path="payload.manifest_sequence", minimum=1)
    _integer(
        payload["created_at_unix_ms"],
        path="payload.created_at_unix_ms",
        minimum=1,
    )
    _integer(payload["episode_count"], path="payload.episode_count")
    input_hashes = _closed(
        payload["input_hashes"],
        path="payload.input_hashes",
        fields=frozenset(_COMMITMENT_INPUT_FIELDS),
    )
    for field in _COMMITMENT_INPUT_FIELDS:
        _sha256(input_hashes[field], path=f"payload.input_hashes.{field}")
    _sha256(
        payload["stage_manifest_payload_sha256"],
        path="payload.stage_manifest_payload_sha256",
    )
    _sha256(
        payload["ordered_episode_commitment_sha256"],
        path="payload.ordered_episode_commitment_sha256",
    )
    _identifier(
        payload["manifest_signer_key_id"],
        path="payload.manifest_signer_key_id",
    )
    return payload


def verify_stage_commitment(
    commitment: Any,
    *,
    public_key: Ed25519PublicKey,
    expected_key_id: str,
    expected_experiment_id: str | None = None,
    expected_fold_id: str | None = None,
    expected_stage_role: str | None = None,
) -> dict[str, Any]:
    document = _closed(
        commitment,
        path="$",
        fields=frozenset({"payload", "signature"}),
    )
    payload = _validate_commitment_payload(document["payload"])
    _verify_signature(
        payload=payload,
        signature=document["signature"],
        public_key=public_key,
        expected_key_id=expected_key_id,
        domain=_COMMITMENT_SIGNATURE_DOMAIN,
    )
    for field, expected in (
        ("experiment_id", expected_experiment_id),
        ("fold_id", expected_fold_id),
        ("stage_role", expected_stage_role),
    ):
        if expected is not None and not hmac.compare_digest(
            payload[field], expected
        ):
            raise StageSealError(
                f"commitment {field} does not match expected context"
            )
    return payload


class HiddenEnvelopeReplayGuard:
    """Process-local single-open guard; see :data:`REPLAY_GUARD_LIMITATION`."""

    def __init__(self) -> None:
        self._opened: MutableSet[str] = set()
        self._lock = threading.Lock()

    def claim(self, stage_open_identity_sha256: str) -> None:
        with self._lock:
            if stage_open_identity_sha256 in self._opened:
                raise StageReplayError("hidden stage has already been opened")
            self._opened.add(stage_open_identity_sha256)


def _hidden_header(value: Any) -> dict[str, Any]:
    header = _closed(
        value,
        path="payload.header",
        fields=frozenset(
            {
                "encryption_algorithm",
                "experiment_id",
                "fold_id",
                "stage_role",
                "manifest_sequence",
                "recipient_key_id",
                "recipient_public_key_sha256",
                "ephemeral_public_key_base64url",
                "hkdf_salt_base64url",
                "nonce_base64url",
                "signed_manifest_sha256",
                "manifest_signer_key_id",
            }
        ),
    )
    if header["encryption_algorithm"] != HIDDEN_ENCRYPTION_ALGORITHM:
        raise StageSealError("unsupported hidden-envelope encryption algorithm")
    _identifier(header["experiment_id"], path="payload.header.experiment_id")
    _identifier(header["fold_id"], path="payload.header.fold_id")
    if header["stage_role"] != "hidden_test":
        raise StageSealError(
            "payload.header.stage_role must equal hidden_test"
        )
    _integer(
        header["manifest_sequence"],
        path="payload.header.manifest_sequence",
        minimum=1,
    )
    _identifier(
        header["recipient_key_id"], path="payload.header.recipient_key_id"
    )
    _sha256(
        header["recipient_public_key_sha256"],
        path="payload.header.recipient_public_key_sha256",
    )
    for field, length in (
        ("ephemeral_public_key_base64url", 32),
        ("hkdf_salt_base64url", 32),
        ("nonce_base64url", 12),
    ):
        try:
            decode_base64url(header[field], expected_nbytes=length)
        except DTOValidationError as exc:
            raise StageSealError(
                f"payload.header.{field} has the wrong encoding or length"
            ) from exc
    _sha256(
        header["signed_manifest_sha256"],
        path="payload.header.signed_manifest_sha256",
    )
    _identifier(
        header["manifest_signer_key_id"],
        path="payload.header.manifest_signer_key_id",
    )
    return header


def _hidden_envelope_payload(value: Any) -> dict[str, Any]:
    payload = _closed(
        value,
        path="payload",
        fields=frozenset(
            {
                "schema_version",
                "header",
                "ciphertext_base64url",
                "ciphertext_sha256",
            }
        ),
    )
    if payload["schema_version"] != HIDDEN_ENVELOPE_SCHEMA_VERSION:
        raise StageSealError("invalid hidden-envelope schema version")
    _hidden_header(payload["header"])
    try:
        ciphertext = decode_base64url(payload["ciphertext_base64url"])
    except DTOValidationError as exc:
        raise StageSealError("payload.ciphertext_base64url is invalid") from exc
    if len(ciphertext) < 17:
        raise StageSealError("hidden-envelope ciphertext is too short")
    ciphertext_sha256 = _sha256(
        payload["ciphertext_sha256"], path="payload.ciphertext_sha256"
    )
    if not hmac.compare_digest(ciphertext_sha256, _hash_bytes(ciphertext)):
        raise StageSealError("hidden-envelope ciphertext hash does not match")
    return payload


def _derive_hidden_content_key(
    *,
    shared_secret: bytes,
    salt: bytes,
    header: Mapping[str, Any],
) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=_HIDDEN_ENCRYPTION_INFO + canonical_json_bytes(dict(header)),
    ).derive(shared_secret)


def seal_hidden_stage_manifest(
    signed_manifest: Mapping[str, Any],
    *,
    manifest_public_key: Ed25519PublicKey,
    manifest_key_id: str,
    recipient_public_key: X25519PublicKey,
    recipient_key_id: str,
    envelope_private_key: Ed25519PrivateKey,
    envelope_key_id: str,
) -> dict[str, Any]:
    """Encrypt an already signed hidden manifest to exactly one recipient."""

    manifest_payload = verify_stage_manifest(
        signed_manifest,
        public_key=manifest_public_key,
        expected_key_id=manifest_key_id,
        expected_stage_role="hidden_test",
    )
    plaintext = canonical_json_bytes(dict(signed_manifest))
    recipient_public_bytes = _public_key_bytes(recipient_public_key)
    ephemeral_private_key = X25519PrivateKey.generate()
    ephemeral_public_bytes = _public_key_bytes(
        ephemeral_private_key.public_key()
    )
    salt = secrets.token_bytes(32)
    nonce = secrets.token_bytes(12)
    header = {
        "encryption_algorithm": HIDDEN_ENCRYPTION_ALGORITHM,
        "experiment_id": manifest_payload["experiment_id"],
        "fold_id": manifest_payload["fold_id"],
        "stage_role": "hidden_test",
        "manifest_sequence": manifest_payload["manifest_sequence"],
        "recipient_key_id": _identifier(
            recipient_key_id, path="recipient_key_id"
        ),
        "recipient_public_key_sha256": _hash_bytes(recipient_public_bytes),
        "ephemeral_public_key_base64url": encode_base64url(
            ephemeral_public_bytes
        ),
        "hkdf_salt_base64url": encode_base64url(salt),
        "nonce_base64url": encode_base64url(nonce),
        "signed_manifest_sha256": _hash_bytes(plaintext),
        "manifest_signer_key_id": _identifier(
            manifest_key_id, path="manifest_key_id"
        ),
    }
    shared_secret = ephemeral_private_key.exchange(recipient_public_key)
    content_key = _derive_hidden_content_key(
        shared_secret=shared_secret, salt=salt, header=header
    )
    aad = _HIDDEN_ENVELOPE_SIGNATURE_DOMAIN + canonical_json_bytes(header)
    ciphertext = ChaCha20Poly1305(content_key).encrypt(
        nonce, plaintext, aad
    )
    payload = {
        "schema_version": HIDDEN_ENVELOPE_SCHEMA_VERSION,
        "header": header,
        "ciphertext_base64url": encode_base64url(ciphertext),
        "ciphertext_sha256": _hash_bytes(ciphertext),
    }
    return {
        "payload": payload,
        "signature": _signature(
            private_key=envelope_private_key,
            key_id=envelope_key_id,
            payload=payload,
            domain=_HIDDEN_ENVELOPE_SIGNATURE_DOMAIN,
        ),
    }


def _validate_candidate_artifact_receipt(
    value: Any,
    *,
    index: int,
    proposer_public_keys: Mapping[str, Ed25519PublicKey] | None = None,
    expected_experiment_id: str | None = None,
) -> dict[str, Any]:
    path = f"payload.candidate_artifacts[{index}]"
    document = _closed(
        value,
        path=path,
        fields=frozenset({"payload", "signature"}),
    )
    payload = _closed(
        document["payload"],
        path=f"{path}.payload",
        fields=frozenset(
            {
                "schema_version",
                "experiment_id",
                "fold_id",
                "artifact_sha256",
                "evidence_manifest_sha256",
            }
        ),
    )
    if (
        payload["schema_version"]
        != CANDIDATE_ARTIFACT_RECEIPT_SCHEMA_VERSION
    ):
        raise StageSealError("invalid candidate-artifact receipt version")
    experiment_id = _identifier(
        payload["experiment_id"], path=f"{path}.payload.experiment_id"
    )
    _identifier(payload["fold_id"], path=f"{path}.payload.fold_id")
    _sha256(
        payload["artifact_sha256"], path=f"{path}.payload.artifact_sha256"
    )
    _sha256(
        payload["evidence_manifest_sha256"],
        path=f"{path}.payload.evidence_manifest_sha256",
    )
    signature = _closed(
        document["signature"],
        path=f"{path}.signature",
        fields=frozenset(
            {
                "algorithm",
                "key_id",
                "payload_sha256",
                "signature_base64url",
            }
        ),
    )
    key_id = _identifier(
        signature["key_id"], path=f"{path}.signature.key_id"
    )
    if expected_experiment_id is not None and not hmac.compare_digest(
        experiment_id, expected_experiment_id
    ):
        raise StageSealError(
            f"{path} experiment_id does not match the unseal authorization"
        )
    if proposer_public_keys is not None:
        public_key = proposer_public_keys.get(key_id)
        if public_key is None:
            raise StageSealError(
                f"{path} has no trusted candidate-artifact signer key"
            )
        try:
            _verify_signature(
                payload=payload,
                signature=signature,
                public_key=public_key,
                expected_key_id=key_id,
                domain=_CANDIDATE_ARTIFACT_SIGNATURE_DOMAIN,
            )
        except StageSealError as exc:
            raise StageSealError(
                f"{path} candidate artifact signer verification failed"
            ) from exc
    return document


def sign_candidate_artifact_receipt(
    payload: Mapping[str, Any],
    *,
    private_key: Ed25519PrivateKey,
    key_id: str,
) -> dict[str, Any]:
    """Sign one frozen fold artifact and its evidence-manifest binding."""

    unsigned = {"payload": dict(payload), "signature": {
        "algorithm": SIGNATURE_ALGORITHM,
        "key_id": key_id,
        "payload_sha256": "0" * 64,
        "signature_base64url": encode_base64url(bytes(64)),
    }}
    validated = _validate_candidate_artifact_receipt(unsigned, index=0)[
        "payload"
    ]
    return {
        "payload": validated,
        "signature": _signature(
            private_key=private_key,
            key_id=key_id,
            payload=validated,
            domain=_CANDIDATE_ARTIFACT_SIGNATURE_DOMAIN,
        ),
    }


def _validate_candidate_artifacts(
    value: Any,
    *,
    proposer_public_keys: Mapping[str, Ed25519PublicKey] | None = None,
    expected_experiment_id: str | None = None,
) -> list[dict[str, Any]]:
    if type(value) is not list or not value:
        raise StageSealError(
            "payload.candidate_artifacts must be a non-empty list"
        )
    normalized: list[dict[str, Any]] = []
    seen_folds: set[str] = set()
    for index, item in enumerate(value):
        receipt = _validate_candidate_artifact_receipt(
            item,
            index=index,
            proposer_public_keys=proposer_public_keys,
            expected_experiment_id=expected_experiment_id,
        )
        fold_id = receipt["payload"]["fold_id"]
        if fold_id in seen_folds:
            raise StageSealError(
                "payload.candidate_artifacts fold_id values must be unique"
            )
        seen_folds.add(fold_id)
        normalized.append(receipt)
    if [item["payload"]["fold_id"] for item in normalized] != sorted(seen_folds):
        raise StageSealError(
            "payload.candidate_artifacts must be ordered by fold_id"
        )
    return normalized


def _validate_selection_gate_receipt(value: Any) -> dict[str, Any]:
    receipt = _closed(
        value,
        path="payload.selection_gate_receipt",
        fields=frozenset(
            {
                "schema_version",
                "passed",
                "selection_manifest_sha256",
                "selection_result_sha256",
                "preregistered_gate_decision",
            }
        ),
    )
    if receipt["schema_version"] != SELECTION_GATE_RECEIPT_SCHEMA_VERSION:
        raise StageSealError("invalid selection-gate receipt schema version")
    if type(receipt["passed"]) is not bool:
        raise StageSealError(
            "payload.selection_gate_receipt.passed must be a boolean"
        )
    _sha256(
        receipt["selection_manifest_sha256"],
        path="payload.selection_gate_receipt.selection_manifest_sha256",
    )
    _sha256(
        receipt["selection_result_sha256"],
        path="payload.selection_gate_receipt.selection_result_sha256",
    )
    if receipt["preregistered_gate_decision"] not in (
        "unseal",
        "do_not_unseal",
    ):
        raise StageSealError(
            "payload.selection_gate_receipt.preregistered_gate_decision "
            "is invalid"
        )
    return receipt


def _validate_unseal_authorization_payload(value: Any) -> dict[str, Any]:
    payload = _closed(
        value,
        path="payload",
        fields=frozenset(
            {
                "schema_version",
                "experiment_id",
                "fold_id",
                "authorization_sequence",
                "authorization_nonce",
                "authorized_at_unix_ms",
                "hidden_envelope_sha256",
                "hidden_stage_commitment_sha256",
                "selection_gate_receipt",
                "candidate_artifacts",
                "bindings",
                "prior_hidden_unseal_receipt_sha256",
            }
        ),
    )
    if (
        payload["schema_version"]
        != HIDDEN_UNSEAL_AUTHORIZATION_SCHEMA_VERSION
    ):
        raise StageSealError("invalid hidden-unseal authorization version")
    _identifier(payload["experiment_id"], path="payload.experiment_id")
    _identifier(payload["fold_id"], path="payload.fold_id")
    _integer(
        payload["authorization_sequence"],
        path="payload.authorization_sequence",
        minimum=1,
    )
    try:
        decode_base64url(payload["authorization_nonce"], expected_nbytes=32)
    except DTOValidationError as exc:
        raise StageSealError(
            "payload.authorization_nonce must be a 256-bit base64url nonce"
        ) from exc
    _integer(
        payload["authorized_at_unix_ms"],
        path="payload.authorized_at_unix_ms",
        minimum=1,
    )
    _sha256(
        payload["hidden_envelope_sha256"],
        path="payload.hidden_envelope_sha256",
    )
    _sha256(
        payload["hidden_stage_commitment_sha256"],
        path="payload.hidden_stage_commitment_sha256",
    )
    _validate_selection_gate_receipt(payload["selection_gate_receipt"])
    _validate_candidate_artifacts(payload["candidate_artifacts"])
    bindings = _closed(
        payload["bindings"],
        path="payload.bindings",
        fields=frozenset(_UNSEAL_BINDING_FIELDS),
    )
    for field in _UNSEAL_BINDING_FIELDS:
        _sha256(bindings[field], path=f"payload.bindings.{field}")
    prior = payload["prior_hidden_unseal_receipt_sha256"]
    if prior is not None:
        _sha256(
            prior, path="payload.prior_hidden_unseal_receipt_sha256"
        )
    return payload


def sign_hidden_unseal_authorization(
    payload: Mapping[str, Any],
    *,
    private_key: Ed25519PrivateKey,
    key_id: str,
) -> dict[str, Any]:
    """Sign the gate authority's exact hidden-unseal preconditions."""

    validated = _validate_unseal_authorization_payload(dict(payload))
    return {
        "payload": validated,
        "signature": _signature(
            private_key=private_key,
            key_id=key_id,
            payload=validated,
            domain=_HIDDEN_UNSEAL_SIGNATURE_DOMAIN,
        ),
    }


def verify_hidden_unseal_authorization(
    authorization: Any,
    *,
    public_key: Ed25519PublicKey,
    expected_key_id: str,
    expected_experiment_id: str,
    expected_fold_id: str,
    expected_hidden_envelope_sha256: str,
    expected_hidden_stage_commitment_sha256: str,
    expected_selection_manifest_sha256: str,
    expected_candidate_artifacts: Sequence[Mapping[str, Any]],
    candidate_artifact_public_keys: Mapping[str, Ed25519PublicKey],
    expected_bindings: Mapping[str, str],
) -> dict[str, Any]:
    """Verify every frozen precondition before hidden decryption."""

    if authorization is None:
        raise StageSealError("a signed hidden-unseal authorization is required")
    document = _closed(
        authorization,
        path="$",
        fields=frozenset({"payload", "signature"}),
    )
    payload = _validate_unseal_authorization_payload(document["payload"])
    _verify_signature(
        payload=payload,
        signature=document["signature"],
        public_key=public_key,
        expected_key_id=expected_key_id,
        domain=_HIDDEN_UNSEAL_SIGNATURE_DOMAIN,
    )
    for field, expected in (
        ("experiment_id", expected_experiment_id),
        ("fold_id", expected_fold_id),
        ("hidden_envelope_sha256", expected_hidden_envelope_sha256),
        (
            "hidden_stage_commitment_sha256",
            expected_hidden_stage_commitment_sha256,
        ),
    ):
        if not hmac.compare_digest(payload[field], expected):
            raise StageSealError(
                f"hidden-unseal authorization {field} does not match"
            )
    gate = payload["selection_gate_receipt"]
    if not gate["passed"] or gate["preregistered_gate_decision"] != "unseal":
        raise StageSealError("selection gate did not authorize hidden unseal")
    if not hmac.compare_digest(
        gate["selection_manifest_sha256"],
        expected_selection_manifest_sha256,
    ):
        raise StageSealError("selection manifest hash does not match")
    _validate_candidate_artifacts(
        payload["candidate_artifacts"],
        proposer_public_keys=candidate_artifact_public_keys,
        expected_experiment_id=expected_experiment_id,
    )
    normalized_candidates = _validate_candidate_artifacts(
        [dict(item) for item in expected_candidate_artifacts],
        proposer_public_keys=candidate_artifact_public_keys,
        expected_experiment_id=expected_experiment_id,
    )
    if not hmac.compare_digest(
        canonical_json_bytes(payload["candidate_artifacts"]),
        canonical_json_bytes(normalized_candidates),
    ):
        raise StageSealError("candidate artifact receipts do not match")
    normalized_bindings = _closed(
        dict(expected_bindings),
        path="expected_bindings",
        fields=frozenset(_UNSEAL_BINDING_FIELDS),
    )
    for field in _UNSEAL_BINDING_FIELDS:
        _sha256(
            normalized_bindings[field], path=f"expected_bindings.{field}"
        )
    if not hmac.compare_digest(
        canonical_json_bytes(payload["bindings"]),
        canonical_json_bytes(normalized_bindings),
    ):
        raise StageSealError("hidden-unseal runtime bindings do not match")
    if payload["prior_hidden_unseal_receipt_sha256"] is not None:
        raise StageReplayError(
            "authorization records a prior hidden-unseal receipt"
        )
    return payload


def _parse_canonical_document(data: bytes) -> dict[str, Any]:
    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        parsed: dict[str, Any] = {}
        for key, value in pairs:
            if key in parsed:
                raise StageSealError(
                    f"hidden plaintext has duplicate field {key!r}"
                )
            parsed[key] = value
        return parsed

    def reject_float(value: str) -> Any:
        raise StageSealError(
            f"hidden plaintext contains forbidden numeric value {value!r}"
        )

    try:
        text = data.decode("utf-8", errors="strict")
        parsed = json.loads(
            text,
            object_pairs_hook=reject_duplicates,
            parse_float=reject_float,
            parse_constant=reject_float,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StageSealError("hidden plaintext is not strict UTF-8 JSON") from exc
    if type(parsed) is not dict:
        raise StageSealError("hidden plaintext must be an object")
    try:
        if not hmac.compare_digest(canonical_json_bytes(parsed), data):
            raise StageSealError("hidden plaintext is not canonical JCS bytes")
    except DTOValidationError as exc:
        raise StageSealError(str(exc)) from exc
    return parsed


def open_hidden_stage_envelope(
    envelope: Any,
    *,
    unseal_authorization: Any,
    unseal_authorization_public_key: Ed25519PublicKey,
    expected_unseal_authorization_key_id: str,
    expected_hidden_stage_commitment_sha256: str,
    expected_selection_manifest_sha256: str,
    expected_candidate_artifacts: Sequence[Mapping[str, Any]],
    candidate_artifact_public_keys: Mapping[str, Ed25519PublicKey],
    expected_bindings: Mapping[str, str],
    recipient_private_key: X25519PrivateKey,
    expected_recipient_key_id: str,
    envelope_public_key: Ed25519PublicKey,
    expected_envelope_key_id: str,
    manifest_public_key: Ed25519PublicKey,
    expected_manifest_key_id: str,
    stage_id_key: bytes,
    expected_experiment_id: str,
    expected_fold_id: str,
    replay_guard: HiddenEnvelopeReplayGuard,
) -> dict[str, Any]:
    """Verify, context-bind, decrypt, and single-open a hidden manifest."""

    document = _closed(
        envelope,
        path="$",
        fields=frozenset({"payload", "signature"}),
    )
    payload = _hidden_envelope_payload(document["payload"])
    _verify_signature(
        payload=payload,
        signature=document["signature"],
        public_key=envelope_public_key,
        expected_key_id=expected_envelope_key_id,
        domain=_HIDDEN_ENVELOPE_SIGNATURE_DOMAIN,
    )
    header = payload["header"]
    for field, expected in (
        ("experiment_id", expected_experiment_id),
        ("fold_id", expected_fold_id),
        ("stage_role", "hidden_test"),
        ("recipient_key_id", expected_recipient_key_id),
        ("manifest_signer_key_id", expected_manifest_key_id),
    ):
        if not hmac.compare_digest(header[field], expected):
            raise StageSealError(
                f"hidden-envelope {field} does not match expected context"
            )
    envelope_sha256 = _hash_bytes(canonical_json_bytes(document))
    verify_hidden_unseal_authorization(
        unseal_authorization,
        public_key=unseal_authorization_public_key,
        expected_key_id=expected_unseal_authorization_key_id,
        expected_experiment_id=expected_experiment_id,
        expected_fold_id=expected_fold_id,
        expected_hidden_envelope_sha256=envelope_sha256,
        expected_hidden_stage_commitment_sha256=(
            expected_hidden_stage_commitment_sha256
        ),
        expected_selection_manifest_sha256=(
            expected_selection_manifest_sha256
        ),
        expected_candidate_artifacts=expected_candidate_artifacts,
        candidate_artifact_public_keys=candidate_artifact_public_keys,
        expected_bindings=expected_bindings,
    )
    recipient_public_bytes = _public_key_bytes(
        recipient_private_key.public_key()
    )
    if not hmac.compare_digest(
        _hash_bytes(recipient_public_bytes),
        header["recipient_public_key_sha256"],
    ):
        raise StageSealError(
            "recipient private key does not match the bound recipient"
        )
    ephemeral_public_key = X25519PublicKey.from_public_bytes(
        decode_base64url(
            header["ephemeral_public_key_base64url"], expected_nbytes=32
        )
    )
    salt = decode_base64url(
        header["hkdf_salt_base64url"], expected_nbytes=32
    )
    nonce = decode_base64url(header["nonce_base64url"], expected_nbytes=12)
    ciphertext = decode_base64url(payload["ciphertext_base64url"])
    shared_secret = recipient_private_key.exchange(ephemeral_public_key)
    content_key = _derive_hidden_content_key(
        shared_secret=shared_secret, salt=salt, header=header
    )
    aad = _HIDDEN_ENVELOPE_SIGNATURE_DOMAIN + canonical_json_bytes(header)
    try:
        plaintext = ChaCha20Poly1305(content_key).decrypt(
            nonce, ciphertext, aad
        )
    except InvalidTag as exc:
        raise StageSealError(
            "hidden-envelope authenticated decryption failed"
        ) from exc
    if not hmac.compare_digest(
        _hash_bytes(plaintext), header["signed_manifest_sha256"]
    ):
        raise StageSealError("decrypted signed-manifest hash does not match")
    signed_manifest = _parse_canonical_document(plaintext)
    manifest_payload = verify_stage_manifest(
        signed_manifest,
        public_key=manifest_public_key,
        expected_key_id=expected_manifest_key_id,
        stage_id_key=stage_id_key,
        expected_experiment_id=expected_experiment_id,
        expected_fold_id=expected_fold_id,
        expected_stage_role="hidden_test",
    )
    if manifest_payload["manifest_sequence"] != header["manifest_sequence"]:
        raise StageSealError(
            "hidden-envelope manifest sequence does not match plaintext"
        )
    if not isinstance(replay_guard, HiddenEnvelopeReplayGuard):
        raise StageSealError("a HiddenEnvelopeReplayGuard is required")
    replay_guard.claim(
        _hash_bytes(
            b"FG-HIDDEN-STAGE-OPEN-IDENTITY-V1\0"
            + canonical_json_bytes(
                {
                    "experiment_id": header["experiment_id"],
                    "fold_id": header["fold_id"],
                    "stage_role": header["stage_role"],
                    "manifest_sequence": header["manifest_sequence"],
                    "signed_manifest_sha256": header[
                        "signed_manifest_sha256"
                    ],
                }
            )
        )
    )
    return signed_manifest
