#!/usr/bin/env python3
"""Launch-time receipts for the corrected loopback model experiment."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any, Iterable, Mapping


class AttestationError(RuntimeError):
    """Raised when a runtime or snapshot does not match its manifest."""


class AttestationChain:
    """In-memory construction of a domain-separated execution hash chain."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def append(self, event_type: str, payload: dict[str, Any]) -> None:
        self.events.append(
            _build_event(
                event_type,
                payload,
                sequence=len(self.events),
                previous_event_sha256=(
                    self.events[-1]["event_sha256"]
                    if self.events
                    else "0" * 64
                ),
            )
        )

    def receipt(self) -> dict[str, Any]:
        if not self.events:
            raise AttestationError("attestation chain is empty")
        return {
            "events": len(self.events),
            "event_chain_root_sha256": self.events[-1][
                "event_sha256"
            ],
        }


class FsyncedAttestationLog:
    """Append a restart-safe hash chain to a durable JSONL file."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        if self.path.exists():
            read_attestation_log(self.path)
        elif self.path.is_symlink():
            raise AttestationError("attestation log must not be a symbolic link")

    def append(self, event_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        existed = self.path.exists()
        flags = os.O_APPEND | os.O_CREAT | os.O_RDWR
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        try:
            descriptor = os.open(self.path, flags, 0o600)
        except OSError as error:
            raise AttestationError("attestation log cannot be opened") from error
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            if not stat.S_ISREG(os.fstat(descriptor).st_mode):
                raise AttestationError("attestation log must be an ordinary file")
            os.lseek(descriptor, 0, os.SEEK_SET)
            raw_chunks: list[bytes] = []
            while True:
                chunk = os.read(descriptor, 1024 * 1024)
                if not chunk:
                    break
                raw_chunks.append(chunk)
            events = _parse_attestation_bytes(b"".join(raw_chunks))
            if events and events[-1].get("event_type") == "run_completed":
                raise AttestationError("completed attestation log is sealed")
            event = _build_event(
                event_type,
                payload,
                sequence=len(events),
                previous_event_sha256=(
                    events[-1]["event_sha256"] if events else "0" * 64
                ),
            )
            encoded = (_stable_json(event) + "\n").encode("utf-8")
            written = 0
            while written < len(encoded):
                count = os.write(descriptor, encoded[written:])
                if count <= 0:
                    raise AttestationError("failed to append attestation event")
                written += count
            os.fsync(descriptor)
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)
        if not existed:
            _fsync_directory(self.path.parent)
        return event


def _build_event(
    event_type: str,
    payload: dict[str, Any],
    *,
    sequence: int,
    previous_event_sha256: str,
) -> dict[str, Any]:
    if sequence == 0 and event_type != "preflight_verified":
        raise AttestationError(
            "preflight receipt must precede every execution event"
        )
    unsigned = {
        "domain": "frankengate-local-attestation-v1",
        "sequence": sequence,
        "previous_event_sha256": previous_event_sha256,
        "event_type": event_type,
        "payload": payload,
    }
    return {
        **unsigned,
        "event_sha256": hashlib.sha256(
            _stable_json(unsigned).encode("utf-8")
        ).hexdigest(),
    }


def read_attestation_log(path: Path) -> list[dict[str, Any]]:
    """Read a complete JSONL chain, rejecting partial or modified records."""

    log_path = Path(path)
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(log_path, flags)
    except OSError as error:
        raise AttestationError("attestation log cannot be read") from error
    try:
        fcntl.flock(descriptor, fcntl.LOCK_SH)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise AttestationError("attestation log must be an ordinary file")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        raw = b"".join(chunks)
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)
    return _parse_attestation_bytes(raw)


def _parse_attestation_bytes(raw: bytes) -> list[dict[str, Any]]:
    if raw and not raw.endswith(b"\n"):
        raise AttestationError("attestation log contains a partial final event")
    events: list[dict[str, Any]] = []
    try:
        for line in raw.splitlines():
            if not line:
                raise AttestationError("attestation log contains a blank event")
            event = json.loads(line, object_pairs_hook=_unique_json_object)
            if not isinstance(event, dict):
                raise AttestationError("attestation event must be an object")
            events.append(event)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise AttestationError("attestation log contains invalid JSON") from error
    if events and not verify_event_chain(events):
        raise AttestationError("attestation event chain is invalid")
    return events


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError as error:
        raise AttestationError("attestation directory cannot be opened") from error
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def verify_completed_attestation(path: Path) -> dict[str, Any]:
    """Verify a closed, fully paired, server-independent execution chain."""

    events = read_attestation_log(path)
    if len(events) < 3:
        raise AttestationError("completed attestation is missing required events")
    if (
        events[0].get("event_type") != "preflight_verified"
        or events[-2].get("event_type") != "postflight_verified"
        or events[-1].get("event_type") != "run_completed"
    ):
        raise AttestationError("completed attestation event order is invalid")
    preflight = _exact_hash_payload(
        events[0],
        {
            "runtime_manifest_sha256",
            "snapshot_tree_sha256",
            "run_plan_sha256",
        },
    )
    postflight = _exact_hash_payload(
        events[-2],
        {"snapshot_tree_sha256"},
    )
    if (
        preflight["snapshot_tree_sha256"]
        != postflight["snapshot_tree_sha256"]
    ):
        raise AttestationError("snapshot changed between preflight and postflight")

    execution_events = events[1:-2]
    if len(execution_events) % 2:
        raise AttestationError("model request is missing its paired response")
    requests = 0
    seen_request_ids: set[str] = set()
    for offset in range(0, len(execution_events), 2):
        request_event = execution_events[offset]
        response_event = execution_events[offset + 1]
        if (
            request_event.get("event_type") != "model_request"
            or response_event.get("event_type") != "model_response"
        ):
            raise AttestationError("model request/response ordering is invalid")
        request = _exact_hash_payload(
            request_event,
            {"request_id_sha256", "request_sha256"},
        )
        response = _exact_hash_payload(
            response_event,
            {"request_id_sha256", "response_sha256"},
        )
        if request["request_id_sha256"] != response["request_id_sha256"]:
            raise AttestationError("model response does not match its request")
        if request["request_id_sha256"] in seen_request_ids:
            raise AttestationError("model request receipt is duplicated")
        seen_request_ids.add(request["request_id_sha256"])
        requests += 1

    if requests == 0:
        raise AttestationError("completed attestation contains no model requests")
    completion = events[-1].get("payload")
    if (
        not isinstance(completion, dict)
        or set(completion) != {"requests_completed", "result_sha256"}
        or type(completion["requests_completed"]) is not int
        or completion["requests_completed"] != requests
        or not _is_sha256(completion["result_sha256"])
    ):
        raise AttestationError("run completion receipt is invalid")
    return {
        "schema_version": "frankengate-completed-runtime-attestation-v2",
        "events": len(events),
        "model_requests_verified": requests,
        "event_chain_root_sha256": events[-1]["event_sha256"],
        "runtime_manifest_sha256": preflight["runtime_manifest_sha256"],
        "snapshot_tree_sha256": preflight["snapshot_tree_sha256"],
        "run_plan_sha256": preflight["run_plan_sha256"],
        "result_sha256": completion["result_sha256"],
    }


def _exact_hash_payload(
    event: Mapping[str, Any],
    expected_fields: set[str],
) -> dict[str, str]:
    payload = event.get("payload")
    if (
        not isinstance(payload, dict)
        or set(payload) != expected_fields
        or any(not _is_sha256(payload[field]) for field in expected_fields)
    ):
        raise AttestationError("attestation event payload is invalid")
    return payload


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def verify_event_chain(events: Iterable[dict[str, Any]]) -> bool:
    previous = "0" * 64
    count = 0
    for count, event in enumerate(events, start=1):
        unsigned = {
            key: value
            for key, value in event.items()
            if key != "event_sha256"
        }
        if (
            unsigned.get("domain")
            != "frankengate-local-attestation-v1"
            or unsigned.get("sequence") != count - 1
            or unsigned.get("previous_event_sha256") != previous
        ):
            return False
        actual = hashlib.sha256(
            _stable_json(unsigned).encode("utf-8")
        ).hexdigest()
        if event.get("event_sha256") != actual:
            return False
        previous = actual
    return count > 0


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                return digest.hexdigest()
            digest.update(chunk)


def _stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def load_runtime_manifest(path: Path) -> dict[str, Any]:
    """Load the versioned model/runtime manifest from an ordinary JSON file."""

    manifest_path = Path(path)
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise AttestationError("runtime manifest must be an ordinary file")
    try:
        value = json.loads(
            manifest_path.read_text(encoding="utf-8"),
            object_pairs_hook=_unique_json_object,
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise AttestationError("runtime manifest is not valid UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise AttestationError("runtime manifest must be a JSON object")
    if value.get("schema_version") != "frankengate-model-runtime-manifest-v2":
        raise AttestationError("unsupported runtime manifest schema")
    manifest_fields = {
        "schema_version",
        "model_id",
        "request_model_id",
        "source_url",
        "revision",
        "snapshot",
        "runtime",
        "server_contract",
        "claim_boundary",
    }
    if set(value) != manifest_fields:
        raise AttestationError("runtime manifest field census is invalid")
    runtime = value["runtime"]
    runtime_fields = {
        "python_version",
        "python_executable_sha256",
        "mlx_lm_console_script_sha256",
        "distributions",
        "critical_source_sha256",
    }
    if not isinstance(runtime, dict) or set(runtime) != runtime_fields:
        raise AttestationError("runtime manifest field census is invalid")
    return value


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise AttestationError("runtime manifest contains a duplicate field")
        value[key] = item
    return value


def verify_runtime_manifest(
    manifest_path: Path,
    *,
    snapshot_root: Path,
    python_executable: Path,
    mlx_lm_console_script: Path,
    python_version: str,
    installed_distributions: Mapping[str, str],
    critical_source_paths: Mapping[str, Path],
) -> dict[str, Any]:
    """Verify the complete declared model snapshot and runtime evidence."""

    manifest = load_runtime_manifest(manifest_path)
    declared_snapshot = manifest["snapshot"]
    if not isinstance(declared_snapshot, dict):
        raise AttestationError("snapshot manifest must be an object")
    declared_files = declared_snapshot.get("file_receipts")
    if not isinstance(declared_files, list) or not declared_files:
        raise AttestationError("snapshot file receipt census is missing")
    expected_paths = {
        item.get("relative_path")
        for item in declared_files
        if isinstance(item, dict)
    }
    if len(expected_paths) != len(declared_files) or None in expected_paths:
        raise AttestationError("snapshot file receipt census is invalid")
    observed_snapshot = snapshot_tree_receipt(
        Path(snapshot_root),
        expected_paths=expected_paths,
    )
    if observed_snapshot != declared_snapshot:
        raise AttestationError("snapshot does not match runtime manifest")

    runtime = manifest["runtime"]
    if not isinstance(runtime, dict):
        raise AttestationError("runtime manifest must be an object")
    if python_version != runtime.get("python_version"):
        raise AttestationError("Python version does not match runtime manifest")
    runtime_files = (
        (
            Path(python_executable),
            runtime.get("python_executable_sha256"),
        ),
        (
            Path(mlx_lm_console_script),
            runtime.get("mlx_lm_console_script_sha256"),
        ),
    )
    for runtime_path, expected_hash in runtime_files:
        if runtime_path.is_symlink() or not runtime_path.is_file():
            raise AttestationError("runtime executable must be an ordinary file")
        if _sha256_file(runtime_path) != expected_hash:
            raise AttestationError("runtime executable hash does not match manifest")

    declared_distributions = runtime.get("distributions")
    if (
        not isinstance(declared_distributions, dict)
        or dict(installed_distributions) != declared_distributions
    ):
        raise AttestationError("runtime distributions do not match manifest")
    declared_sources = runtime.get("critical_source_sha256")
    if (
        not isinstance(declared_sources, dict)
        or set(critical_source_paths) != set(declared_sources)
    ):
        raise AttestationError("critical runtime source census does not match manifest")
    for source_name, expected_hash in declared_sources.items():
        source_path = Path(critical_source_paths[source_name])
        if source_path.is_symlink() or not source_path.is_file():
            raise AttestationError("critical runtime source must be an ordinary file")
        if _sha256_file(source_path) != expected_hash:
            raise AttestationError("critical runtime source hash does not match manifest")

    return {
        "schema_version": "frankengate-model-runtime-attestation-v2",
        "manifest_sha256": hashlib.sha256(
            _stable_json(manifest).encode("utf-8")
        ).hexdigest(),
        "snapshot_tree_sha256": observed_snapshot["snapshot_tree_sha256"],
        "snapshot_files_verified": observed_snapshot["files"],
        "snapshot_bytes_verified": observed_snapshot["bytes"],
        "runtime_executables_verified": len(runtime_files),
        "distributions_verified": len(declared_distributions),
        "critical_sources_verified": len(declared_sources),
    }


def snapshot_tree_receipt(
    root: Path,
    *,
    expected_paths: Iterable[str],
) -> dict[str, Any]:
    """Hash an exact ordinary-file tree and reject aliases or extras."""

    resolved = root.resolve(strict=True)
    expected = set(expected_paths)
    if not expected or any(
        not path
        or Path(path).is_absolute()
        or ".." in Path(path).parts
        for path in expected
    ):
        raise AttestationError("expected snapshot path census is invalid")
    actual: dict[str, Path] = {}
    for entry in resolved.rglob("*"):
        if entry.is_symlink():
            raise AttestationError("snapshot contains a symbolic link")
        if entry.is_dir():
            continue
        if not entry.is_file():
            raise AttestationError("snapshot contains a special file")
        relative = entry.relative_to(resolved).as_posix()
        actual[relative] = entry
    if set(actual) != expected:
        raise AttestationError("snapshot file census does not match manifest")
    files = [
        {
            "relative_path": relative,
            "bytes": actual[relative].stat().st_size,
            "sha256": _sha256_file(actual[relative]),
        }
        for relative in sorted(actual)
    ]
    return {
        "files": len(files),
        "bytes": sum(item["bytes"] for item in files),
        "snapshot_tree_sha256": hashlib.sha256(
            _stable_json(files).encode("utf-8")
        ).hexdigest(),
        "file_receipts": files,
    }
