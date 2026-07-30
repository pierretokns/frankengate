"""Append-once, content-addressed evidence for NL2SQL attempts.

This module is intentionally independent from the solver/evaluator DTO module.
It implements the bounded local-filesystem portion of the capability-isolation
design:

* canonical JSON-subset bytes;
* SHA-256-addressed attempt and terminal-ledger blobs;
* private temporary writes followed by create-exclusive atomic publication;
* file and directory fsync plus immediate read-back verification;
* episode-scoped random attempt capabilities;
* ordered previous-blob links and a terminal ledger root; and
* submission by durable attempt ID, with no SQL or callback API.

Threat-model limit
------------------
The store is append-once and tamper-evident only while its process boundary,
open directory descriptors, and expected in-memory roots are trusted. It is
not signed, WORM storage, crash-recoverable state, or protection against root,
the storage administrator, or a process that can alter both blobs and trusted
in-memory state. Those stronger properties belong to later signing/object-lock
and recovery slices. Corruption by an unprivileged/runtime actor is detected
before evidence is returned or evaluated.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
import threading
from typing import Any, Mapping

from .dto import canonical_json_bytes as _canonical_jcs_bytes


ATTEMPT_SCHEMA_VERSION = "fg-attempt-evidence-v1"
LEDGER_SCHEMA_VERSION = "fg-attempt-ledger-v1"
CHAIN_SCHEMA_VERSION = "fg-attempt-chain-v1"
INTEGRITY_MODEL = "local-content-addressed-no-signature-v1"
THREAT_MODEL_LIMIT = (
    "Tamper-evident only while the store process, open directory descriptors, "
    "and expected in-memory roots are trusted; not signed, WORM, "
    "crash-recoverable, or resistant to root/storage-administrator collusion."
)

_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_EPISODE_REF_RE = re.compile(r"^[A-Za-z0-9_-]{8,256}$")
_ATTEMPT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{24,128}$")
_SUCCESS_STATUS = "executed"
_FAILURE_STATUSES = frozenset({"failed", "denied"})
_ALLOWED_STATUSES = frozenset({_SUCCESS_STATUS, *_FAILURE_STATUSES})


class AttemptStoreError(RuntimeError):
    """Base class for attempt-store contract failures."""


class CanonicalDataError(AttemptStoreError):
    """Input or stored data is outside the canonical JSON subset."""


class IntegrityError(AttemptStoreError):
    """Stored bytes, links, permissions, or roots failed verification."""


class PublicationConflict(IntegrityError):
    """A create-exclusive content-addressed publication already exists."""


class EpisodeStateError(AttemptStoreError):
    """An episode is unknown, duplicated, or already terminal."""


class UnknownAttemptError(AttemptStoreError):
    """An attempt capability is not known to this store."""


class CrossEpisodeAttemptError(AttemptStoreError):
    """An attempt capability belongs to a different episode."""


class UnsubmittableAttemptError(AttemptStoreError):
    """The selected attempt was durable but not successful."""


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_value(value: Any, *, path: str = "$") -> Any:
    """Return a detached value in the store's deterministic JSON subset."""

    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        raise CanonicalDataError(f"{path}: floats are forbidden")
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalDataError(
                    f"{path}: mapping keys must be strings"
                )
            normalized[key] = _canonical_value(
                item,
                path=f"{path}.{key}",
            )
        return normalized
    if isinstance(value, (list, tuple)):
        return [
            _canonical_value(item, path=f"{path}[{index}]")
            for index, item in enumerate(value)
        ]
    raise CanonicalDataError(
        f"{path}: unsupported canonical value {type(value).__name__}"
    )


def canonical_json_bytes(value: Any) -> bytes:
    """Encode the detached JSON subset with the package's shared JCS encoder."""

    normalized = _canonical_value(value)
    return _canonical_jcs_bytes(normalized)


def query_result_content_sha256(value: Mapping[str, Any]) -> str:
    """Hash the semantic ``columns`` and ``rows`` of fg-query-result-v1."""

    if not isinstance(value, Mapping):
        raise CanonicalDataError("query_result must be a mapping")
    if value.get("schema_version") != "fg-query-result-v1":
        return sha256_bytes(canonical_json_bytes(value))
    columns = value.get("columns")
    rows = value.get("rows")
    if not isinstance(columns, list) or not isinstance(rows, list):
        raise CanonicalDataError(
            "fg-query-result-v1 requires columns and rows arrays"
        )
    digest = sha256_bytes(
        canonical_json_bytes({"columns": columns, "rows": rows})
    )
    return digest


def _validated_query_result_content_sha256(
    value: Mapping[str, Any],
) -> str:
    """Verify the embedded semantic hash before durable publication."""

    digest = query_result_content_sha256(value)
    if value.get("schema_version") != "fg-query-result-v1":
        return digest
    supplied = value.get("result_content_sha256")
    if supplied is None:
        raise CanonicalDataError(
            "fg-query-result-v1 requires result_content_sha256"
        )
    if supplied != digest:
        raise CanonicalDataError(
            "query_result result_content_sha256 does not match columns/rows"
        )
    return digest


def _decode_canonical_json(value: bytes) -> Any:
    def reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        decoded: dict[str, Any] = {}
        for key, item in pairs:
            if key in decoded:
                raise CanonicalDataError(f"duplicate stored JSON key: {key}")
            decoded[key] = item
        return decoded

    try:
        decoded = json.loads(
            value.decode("utf-8"),
            object_pairs_hook=reject_duplicate_keys,
            parse_float=lambda raw: (_ for _ in ()).throw(
                CanonicalDataError(f"stored float is forbidden: {raw}")
            ),
            parse_constant=lambda raw: (_ for _ in ()).throw(
                CanonicalDataError(f"stored constant is forbidden: {raw}")
            ),
        )
    except UnicodeDecodeError as exc:
        raise CanonicalDataError("stored blob is not UTF-8") from exc
    except json.JSONDecodeError as exc:
        raise CanonicalDataError("stored blob is not valid JSON") from exc
    if canonical_json_bytes(decoded) != value:
        raise CanonicalDataError("stored JSON bytes are not canonical")
    return decoded


def _require_sha256(value: str, *, field: str) -> None:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{field} must be a lowercase SHA-256 hex digest")


def _require_episode_ref(value: str) -> None:
    if not isinstance(value, str) or not _EPISODE_REF_RE.fullmatch(value):
        raise ValueError(
            "episode_ref must be an opaque 8-256 character token"
        )


def _write_all(fd: int, value: bytes) -> None:
    offset = 0
    while offset < len(value):
        written = os.write(fd, value[offset:])
        if written <= 0:
            raise OSError("short write while publishing canonical blob")
        offset += written


def _mkdir_checked(path: Path, mode: int) -> None:
    try:
        path.mkdir(mode=mode)
    except FileExistsError:
        pass
    metadata = path.lstat()
    if not stat.S_ISDIR(metadata.st_mode):
        raise IntegrityError(f"store path is not a directory: {path}")
    if stat.S_ISLNK(metadata.st_mode):
        raise IntegrityError(f"store directory may not be a symlink: {path}")
    os.chmod(path, mode)


@dataclass(frozen=True)
class BlobReceipt:
    sha256: str
    byte_count: int


@dataclass(frozen=True)
class AttemptReceipt:
    episode_ref: str
    attempt_id: str
    attempt_index: int
    attempt_blob_sha256: str
    previous_attempt_blob_sha256: str | None
    attempt_chain_root_sha256: str
    status: str
    successful: bool
    result_content_sha256: str | None


@dataclass(frozen=True)
class SubmissionReceipt:
    episode_ref: str
    selected_attempt_id: str
    selected_attempt_blob_sha256: str
    selected_result_content_sha256: str
    attempt_count: int
    attempt_chain_root_sha256: str
    ledger_root_sha256: str
    integrity_model: str = INTEGRITY_MODEL
    threat_model_limit: str = THREAT_MODEL_LIMIT


@dataclass(frozen=True)
class _AttemptPointer:
    attempt_id: str
    attempt_index: int
    blob_sha256: str
    previous_blob_sha256: str | None
    status: str
    result_content_sha256: str | None


@dataclass
class _EpisodeState:
    episode_ref: str
    attempts: list[_AttemptPointer]
    by_id: dict[str, _AttemptPointer]
    terminal_receipt: SubmissionReceipt | None = None


class AttemptStore:
    """One-process writer and verifying reader for attempt evidence."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).absolute()
        self._lock = threading.RLock()
        self._closed = False
        self._episodes: dict[str, _EpisodeState] = {}
        self._attempt_owner: dict[str, str] = {}

        if not self.root.exists():
            self.root.mkdir(parents=True, mode=0o700)
        _mkdir_checked(self.root, 0o700)
        self._private_dir = self.root / "private"
        self._blob_parent_dir = self.root / "blobs"
        self._blob_dir = self._blob_parent_dir / "sha256"
        _mkdir_checked(self._private_dir, 0o700)
        _mkdir_checked(self._blob_parent_dir, 0o750)
        _mkdir_checked(self._blob_dir, 0o750)

        directory_flags = os.O_RDONLY
        directory_flags |= getattr(os, "O_DIRECTORY", 0)
        directory_flags |= getattr(os, "O_NOFOLLOW", 0)
        try:
            self._private_fd = os.open(
                self._private_dir,
                directory_flags,
            )
            self._blob_fd = os.open(self._blob_dir, directory_flags)
        except Exception:
            private_fd = getattr(self, "_private_fd", None)
            if private_fd is not None:
                os.close(private_fd)
            raise
        self._private_identity = self._directory_identity(self._private_fd)
        self._blob_identity = self._directory_identity(self._blob_fd)

    def __enter__(self) -> "AttemptStore":
        self._require_open()
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            os.close(self._private_fd)
            os.close(self._blob_fd)
            self._closed = True

    def _require_open(self) -> None:
        if self._closed:
            raise AttemptStoreError("attempt store is closed")

    @staticmethod
    def _directory_identity(fd: int) -> tuple[int, int]:
        metadata = os.fstat(fd)
        if not stat.S_ISDIR(metadata.st_mode):
            raise IntegrityError("opened store descriptor is not a directory")
        return metadata.st_dev, metadata.st_ino

    def _verify_directory_descriptors(self) -> None:
        if self._directory_identity(self._private_fd) != self._private_identity:
            raise IntegrityError("private directory descriptor changed")
        if self._directory_identity(self._blob_fd) != self._blob_identity:
            raise IntegrityError("blob directory descriptor changed")

    def _publish_canonical(self, value: Any) -> BlobReceipt:
        self._require_open()
        self._verify_directory_descriptors()
        payload = canonical_json_bytes(value)
        digest = sha256_bytes(payload)
        temp_name = f".publish-{secrets.token_hex(24)}"
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        flags |= getattr(os, "O_NOFOLLOW", 0)
        temp_fd: int | None = None
        temp_exists = False
        try:
            temp_fd = os.open(
                temp_name,
                flags,
                0o600,
                dir_fd=self._private_fd,
            )
            temp_exists = True
            _write_all(temp_fd, payload)
            os.fchmod(temp_fd, 0o440)
            os.fsync(temp_fd)
            os.close(temp_fd)
            temp_fd = None
            try:
                os.link(
                    temp_name,
                    digest,
                    src_dir_fd=self._private_fd,
                    dst_dir_fd=self._blob_fd,
                    follow_symlinks=False,
                )
            except FileExistsError as exc:
                raise PublicationConflict(
                    f"content-addressed destination already exists: {digest}"
                ) from exc
            os.fsync(self._blob_fd)
            os.unlink(temp_name, dir_fd=self._private_fd)
            temp_exists = False
            os.fsync(self._private_fd)
            receipt = BlobReceipt(sha256=digest, byte_count=len(payload))
            self._read_blob_bytes(digest, expected_bytes=payload)
            return receipt
        finally:
            if temp_fd is not None:
                os.close(temp_fd)
            if temp_exists:
                try:
                    os.unlink(temp_name, dir_fd=self._private_fd)
                except FileNotFoundError:
                    pass
                os.fsync(self._private_fd)

    def _read_blob_bytes(
        self,
        digest: str,
        *,
        expected_bytes: bytes | None = None,
    ) -> bytes:
        self._require_open()
        self._verify_directory_descriptors()
        _require_sha256(digest, field="blob digest")
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(digest, flags, dir_fd=self._blob_fd)
        except OSError as exc:
            raise IntegrityError(
                f"cannot open content-addressed blob {digest}: {exc}"
            ) from exc
        try:
            metadata = os.fstat(fd)
            if not stat.S_ISREG(metadata.st_mode):
                raise IntegrityError(f"blob {digest} is not a regular file")
            if stat.S_IMODE(metadata.st_mode) != 0o440:
                raise IntegrityError(
                    f"blob {digest} mode is not immutable reader mode 0440"
                )
            if metadata.st_nlink != 1:
                raise IntegrityError(
                    f"blob {digest} has unexpected hard-link count"
                )
            chunks: list[bytes] = []
            while True:
                chunk = os.read(fd, 1024 * 1024)
                if not chunk:
                    break
                chunks.append(chunk)
            payload = b"".join(chunks)
        finally:
            os.close(fd)
        if sha256_bytes(payload) != digest:
            raise IntegrityError(f"blob {digest} content hash mismatch")
        if expected_bytes is not None and payload != expected_bytes:
            raise IntegrityError(f"blob {digest} read-back mismatch")
        _decode_canonical_json(payload)
        return payload

    def read_blob(self, digest: str) -> Any:
        """Return verified canonical data for a known content hash."""

        with self._lock:
            return _decode_canonical_json(self._read_blob_bytes(digest))

    def blob_path(self, digest: str) -> Path:
        """Return a path for inspection/tests; reads must still call read_blob."""

        _require_sha256(digest, field="blob digest")
        return self._blob_dir / digest

    def create_episode(self, episode_ref: str) -> None:
        with self._lock:
            self._require_open()
            _require_episode_ref(episode_ref)
            if episode_ref in self._episodes:
                raise EpisodeStateError(f"duplicate episode: {episode_ref}")
            self._episodes[episode_ref] = _EpisodeState(
                episode_ref=episode_ref,
                attempts=[],
                by_id={},
            )

    def _episode(self, episode_ref: str) -> _EpisodeState:
        _require_episode_ref(episode_ref)
        try:
            return self._episodes[episode_ref]
        except KeyError as exc:
            raise EpisodeStateError(
                f"unknown episode: {episode_ref}"
            ) from exc

    def _new_attempt_id(self) -> str:
        for _ in range(32):
            attempt_id = secrets.token_urlsafe(24)
            if attempt_id not in self._attempt_owner:
                return attempt_id
        raise AttemptStoreError("could not allocate a unique attempt ID")

    @staticmethod
    def _chain_root(
        episode_ref: str,
        attempts: list[_AttemptPointer],
    ) -> str:
        payload = {
            "schema_version": CHAIN_SCHEMA_VERSION,
            "episode_ref": episode_ref,
            "ordered_attempt_blob_sha256": [
                pointer.blob_sha256 for pointer in attempts
            ],
        }
        return sha256_bytes(canonical_json_bytes(payload))

    def record_attempt(
        self,
        *,
        episode_ref: str,
        candidate_sql_sha256: str,
        status: str,
        authority_valid: bool,
        policy_accepted: bool | None,
        query_result: Mapping[str, Any] | None = None,
        error_code: str | None = None,
        bindings: Mapping[str, Any] | None = None,
    ) -> AttemptReceipt:
        """Durably record one attempted query without accepting raw SQL."""

        with self._lock:
            self._require_open()
            state = self._episode(episode_ref)
            if state.terminal_receipt is not None:
                raise EpisodeStateError("cannot append after terminal submission")
            _require_sha256(
                candidate_sql_sha256,
                field="candidate_sql_sha256",
            )
            if status not in _ALLOWED_STATUSES:
                raise ValueError(f"unsupported attempt status: {status}")
            if not isinstance(authority_valid, bool):
                raise ValueError("authority_valid must be boolean")
            if policy_accepted is not None and not isinstance(
                policy_accepted,
                bool,
            ):
                raise ValueError("policy_accepted must be boolean or null")

            successful = status == _SUCCESS_STATUS
            if successful:
                if not authority_valid or policy_accepted is not True:
                    raise ValueError(
                        "executed attempts require valid authority and policy"
                    )
                if query_result is None:
                    raise ValueError(
                        "executed attempts require a full query_result"
                    )
                if error_code is not None:
                    raise ValueError(
                        "executed attempts cannot contain an error_code"
                    )
            else:
                if query_result is not None:
                    raise ValueError(
                        "failed/denied attempts cannot contain query_result"
                    )
                if not isinstance(error_code, str) or not error_code:
                    raise ValueError(
                        "failed/denied attempts require error_code"
                    )

            canonical_result = (
                _canonical_value(query_result, path="$.query_result")
                if query_result is not None
                else None
            )
            result_content_sha256 = (
                _validated_query_result_content_sha256(canonical_result)
                if canonical_result is not None
                else None
            )
            canonical_bindings = _canonical_value(
                bindings or {},
                path="$.bindings",
            )
            attempt_id = self._new_attempt_id()
            attempt_index = len(state.attempts)
            previous_blob = (
                state.attempts[-1].blob_sha256
                if state.attempts
                else None
            )
            evidence = {
                "schema_version": ATTEMPT_SCHEMA_VERSION,
                "integrity_model": INTEGRITY_MODEL,
                "episode_ref": episode_ref,
                "attempt_id": attempt_id,
                "attempt_index": attempt_index,
                "previous_attempt_blob_sha256": previous_blob,
                "candidate_sql_sha256": candidate_sql_sha256,
                "status": status,
                "successful": successful,
                "authority_valid": authority_valid,
                "policy_accepted": policy_accepted,
                "result_content_sha256": result_content_sha256,
                "query_result": canonical_result,
                "error_code": error_code,
                "bindings": canonical_bindings,
            }
            blob = self._publish_canonical(evidence)
            pointer = _AttemptPointer(
                attempt_id=attempt_id,
                attempt_index=attempt_index,
                blob_sha256=blob.sha256,
                previous_blob_sha256=previous_blob,
                status=status,
                result_content_sha256=result_content_sha256,
            )
            state.attempts.append(pointer)
            state.by_id[attempt_id] = pointer
            self._attempt_owner[attempt_id] = episode_ref
            return AttemptReceipt(
                episode_ref=episode_ref,
                attempt_id=attempt_id,
                attempt_index=attempt_index,
                attempt_blob_sha256=blob.sha256,
                previous_attempt_blob_sha256=previous_blob,
                attempt_chain_root_sha256=self._chain_root(
                    episode_ref,
                    state.attempts,
                ),
                status=status,
                successful=successful,
                result_content_sha256=result_content_sha256,
            )

    def _verify_attempt_pointer(
        self,
        state: _EpisodeState,
        pointer: _AttemptPointer,
        *,
        expected_index: int,
        expected_previous: str | None,
    ) -> dict[str, Any]:
        payload = self.read_blob(pointer.blob_sha256)
        expected = {
            "schema_version": ATTEMPT_SCHEMA_VERSION,
            "integrity_model": INTEGRITY_MODEL,
            "episode_ref": state.episode_ref,
            "attempt_id": pointer.attempt_id,
            "attempt_index": expected_index,
            "previous_attempt_blob_sha256": expected_previous,
            "status": pointer.status,
            "result_content_sha256": pointer.result_content_sha256,
        }
        for field, value in expected.items():
            if payload.get(field) != value:
                raise IntegrityError(
                    f"attempt {pointer.attempt_id} has invalid {field}"
                )
        if payload.get("successful") != (
            pointer.status == _SUCCESS_STATUS
        ):
            raise IntegrityError(
                f"attempt {pointer.attempt_id} success marker mismatch"
            )
        if pointer.status == _SUCCESS_STATUS:
            query_result = payload.get("query_result")
            if query_result is None:
                raise IntegrityError("successful attempt lost query_result")
            actual_result_sha = _validated_query_result_content_sha256(
                query_result
            )
            if actual_result_sha != pointer.result_content_sha256:
                raise IntegrityError("query_result content hash mismatch")
        return payload

    def verify_attempt(
        self,
        *,
        episode_ref: str,
        attempt_id: str,
    ) -> Mapping[str, Any]:
        with self._lock:
            state = self._episode(episode_ref)
            owner = self._attempt_owner.get(attempt_id)
            if owner is not None and owner != episode_ref:
                raise CrossEpisodeAttemptError(
                    "attempt belongs to another episode"
                )
            pointer = state.by_id.get(attempt_id)
            if pointer is None:
                raise UnknownAttemptError(f"unknown attempt: {attempt_id}")
            expected_previous = (
                state.attempts[pointer.attempt_index - 1].blob_sha256
                if pointer.attempt_index
                else None
            )
            return self._verify_attempt_pointer(
                state,
                pointer,
                expected_index=pointer.attempt_index,
                expected_previous=expected_previous,
            )

    def _verify_chain(self, state: _EpisodeState) -> str:
        previous: str | None = None
        for index, pointer in enumerate(state.attempts):
            if pointer.attempt_index != index:
                raise IntegrityError("in-memory attempt order is invalid")
            if pointer.previous_blob_sha256 != previous:
                raise IntegrityError("in-memory previous-hash link is invalid")
            self._verify_attempt_pointer(
                state,
                pointer,
                expected_index=index,
                expected_previous=previous,
            )
            previous = pointer.blob_sha256
        return self._chain_root(state.episode_ref, state.attempts)

    def submit(
        self,
        *,
        episode_ref: str,
        attempt_id: str,
    ) -> SubmissionReceipt:
        """Select a durable successful attempt; this API has no SQL/callback."""

        with self._lock:
            self._require_open()
            state = self._episode(episode_ref)
            if state.terminal_receipt is not None:
                raise EpisodeStateError("episode already has terminal submission")
            if not isinstance(attempt_id, str) or not _ATTEMPT_ID_RE.fullmatch(
                attempt_id
            ):
                raise UnknownAttemptError("attempt ID has invalid shape")
            owner = self._attempt_owner.get(attempt_id)
            if owner is not None and owner != episode_ref:
                raise CrossEpisodeAttemptError(
                    "attempt belongs to another episode"
                )
            selected = state.by_id.get(attempt_id)
            if selected is None:
                raise UnknownAttemptError(f"unknown attempt: {attempt_id}")
            if (
                selected.status != _SUCCESS_STATUS
                or selected.result_content_sha256 is None
            ):
                raise UnsubmittableAttemptError(
                    "only durable successful attempts may be submitted"
                )

            chain_root = self._verify_chain(state)
            entries = [
                {
                    "attempt_id": pointer.attempt_id,
                    "attempt_index": pointer.attempt_index,
                    "attempt_blob_sha256": pointer.blob_sha256,
                    "previous_attempt_blob_sha256": (
                        pointer.previous_blob_sha256
                    ),
                    "status": pointer.status,
                    "result_content_sha256": (
                        pointer.result_content_sha256
                    ),
                }
                for pointer in state.attempts
            ]
            ledger = {
                "schema_version": LEDGER_SCHEMA_VERSION,
                "integrity_model": INTEGRITY_MODEL,
                "threat_model_limit": THREAT_MODEL_LIMIT,
                "episode_ref": episode_ref,
                "attempt_chain_root_sha256": chain_root,
                "attempt_count": len(entries),
                "entries": entries,
                "terminal": {
                    "action": "submit_sql",
                    "selected_attempt_id": selected.attempt_id,
                    "selected_attempt_blob_sha256": selected.blob_sha256,
                    "selected_result_content_sha256": (
                        selected.result_content_sha256
                    ),
                },
            }
            ledger_blob = self._publish_canonical(ledger)
            receipt = SubmissionReceipt(
                episode_ref=episode_ref,
                selected_attempt_id=selected.attempt_id,
                selected_attempt_blob_sha256=selected.blob_sha256,
                selected_result_content_sha256=(
                    selected.result_content_sha256
                ),
                attempt_count=len(entries),
                attempt_chain_root_sha256=chain_root,
                ledger_root_sha256=ledger_blob.sha256,
            )
            state.terminal_receipt = receipt
            self.verify_submission(receipt)
            return receipt

    def verify_submission(
        self,
        receipt: SubmissionReceipt,
    ) -> Mapping[str, Any]:
        with self._lock:
            self._require_open()
            state = self._episode(receipt.episode_ref)
            if state.terminal_receipt is None:
                raise IntegrityError("episode has no terminal ledger")
            if state.terminal_receipt != receipt:
                raise IntegrityError(
                    "submission receipt differs from trusted terminal state"
                )
            chain_root = self._verify_chain(state)
            if chain_root != receipt.attempt_chain_root_sha256:
                raise IntegrityError("submission chain root mismatch")
            ledger = self.read_blob(receipt.ledger_root_sha256)
            if ledger.get("schema_version") != LEDGER_SCHEMA_VERSION:
                raise IntegrityError("terminal ledger schema mismatch")
            if ledger.get("episode_ref") != receipt.episode_ref:
                raise IntegrityError("terminal ledger episode mismatch")
            if ledger.get("attempt_chain_root_sha256") != chain_root:
                raise IntegrityError("terminal ledger chain root mismatch")
            if ledger.get("attempt_count") != len(state.attempts):
                raise IntegrityError("terminal ledger attempt count mismatch")

            entries = ledger.get("entries")
            if not isinstance(entries, list) or len(entries) != len(
                state.attempts
            ):
                raise IntegrityError("terminal ledger entries are invalid")
            previous: str | None = None
            for index, (entry, pointer) in enumerate(
                zip(entries, state.attempts)
            ):
                expected_entry = {
                    "attempt_id": pointer.attempt_id,
                    "attempt_index": index,
                    "attempt_blob_sha256": pointer.blob_sha256,
                    "previous_attempt_blob_sha256": previous,
                    "status": pointer.status,
                    "result_content_sha256": (
                        pointer.result_content_sha256
                    ),
                }
                if entry != expected_entry:
                    raise IntegrityError(
                        "terminal ledger was substituted or reordered"
                    )
                previous = pointer.blob_sha256

            selected = state.by_id[receipt.selected_attempt_id]
            expected_terminal = {
                "action": "submit_sql",
                "selected_attempt_id": selected.attempt_id,
                "selected_attempt_blob_sha256": selected.blob_sha256,
                "selected_result_content_sha256": (
                    selected.result_content_sha256
                ),
            }
            if ledger.get("terminal") != expected_terminal:
                raise IntegrityError("terminal selection mismatch")
            if (
                receipt.selected_attempt_blob_sha256
                != selected.blob_sha256
                or receipt.selected_result_content_sha256
                != selected.result_content_sha256
                or receipt.attempt_count != len(state.attempts)
            ):
                raise IntegrityError("submission receipt fields are invalid")
            return ledger

    def submission_receipt(self, *, episode_ref: str) -> SubmissionReceipt:
        """Return the verified terminal receipt without exposing mutable state."""

        with self._lock:
            state = self._episode(episode_ref)
            if state.terminal_receipt is None:
                raise EpisodeStateError("episode has no terminal submission")
            receipt = state.terminal_receipt
            self.verify_submission(receipt)
            return receipt
