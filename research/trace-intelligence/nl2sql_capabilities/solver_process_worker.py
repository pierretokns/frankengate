#!/usr/bin/env python3
"""Minimal child worker for one isolated solver episode.

The worker decodes only SolverEpisodeDTO.  Model and broker messages remain
opaque bounded binary frames distinguished by a one-byte routing opcode.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import struct
import sys
from typing import Any


PACKAGE_PARENT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PACKAGE_PARENT))

from nl2sql_capabilities.dto import (  # noqa: E402
    MAX_FRAME_BYTES,
    SolverEpisodeDTO,
    canonical_json_bytes,
)


OP_BOOTSTRAP = b"\x10"
OP_BROKER_CALL = b"\x20"
OP_BROKER_RESULT = b"\x21"
OP_FINISH = b"\x7f"
RECEIPT_SCHEMA_VERSION = "fg-one-episode-solver-worker-receipt-v1"
SANITIZED_ENVIRONMENT_KEYS = frozenset(
    {
        "HOME",
        "TMPDIR",
        "XDG_CACHE_HOME",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "PYTHONDONTWRITEBYTECODE",
        "PYTHONNOUSERSITE",
        "LANG",
        "LC_ALL",
        "FG_SOLVER_BROKER_FD",
        "FG_SOLVER_MODEL_FD",
        "FG_SOLVER_WORK_ROOT",
    }
)


def _sanitize_runtime_environment() -> None:
    for key in tuple(os.environ):
        if key not in SANITIZED_ENVIRONMENT_KEYS:
            del os.environ[key]


def _close_unlisted_fds(allowed: set[int]) -> None:
    descriptor_root = Path("/proc/self/fd")
    if not descriptor_root.is_dir():
        descriptor_root = Path("/dev/fd")
    try:
        candidates = [
            int(entry.name)
            for entry in descriptor_root.iterdir()
            if entry.name.isdigit()
        ]
    except OSError:
        candidates = list(range(3, 4096))
    for descriptor in candidates:
        if descriptor in allowed:
            continue
        try:
            os.close(descriptor)
        except OSError:
            pass


def _socket_from_inherited_fd(name: str) -> socket.socket:
    raw = os.environ.get(name)
    if raw is None or not raw.isdigit():
        raise RuntimeError(f"{name} is not an inherited descriptor")
    descriptor = int(raw)
    if descriptor < 3 or not stat.S_ISSOCK(os.fstat(descriptor).st_mode):
        raise RuntimeError(f"{name} is not a Unix socket")
    peer = socket.socket(fileno=descriptor)
    if peer.family != socket.AF_UNIX or peer.type & socket.SOCK_STREAM == 0:
        raise RuntimeError(f"{name} must be a Unix stream socket")
    return peer


def _read_exact_stream(stream: Any, count: int) -> bytes:
    chunks: list[bytes] = []
    remaining = count
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            raise RuntimeError("input closed during frame")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _read_exact_socket(peer: socket.socket, count: int) -> bytes:
    chunks: list[bytes] = []
    remaining = count
    while remaining:
        chunk = peer.recv(remaining)
        if not chunk:
            raise RuntimeError("socket closed during frame")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _read_frame_stream(stream: Any) -> bytes:
    prefix = _read_exact_stream(stream, 4)
    size = struct.unpack(">I", prefix)[0]
    if size > MAX_FRAME_BYTES:
        raise RuntimeError("episode frame exceeds limit")
    return _read_exact_stream(stream, size)


def _read_frame_socket(peer: socket.socket) -> bytes:
    prefix = _read_exact_socket(peer, 4)
    size = struct.unpack(">I", prefix)[0]
    if size > MAX_FRAME_BYTES:
        raise RuntimeError("peer frame exceeds limit")
    return _read_exact_socket(peer, size)


def _send_frame(peer: socket.socket, payload: bytes) -> None:
    if len(payload) > MAX_FRAME_BYTES:
        raise RuntimeError("outbound frame exceeds limit")
    peer.sendall(struct.pack(">I", len(payload)) + payload)


def _open_fd_targets() -> dict[str, str]:
    result: dict[str, str] = {}
    root = Path("/proc/self/fd")
    if not root.is_dir():
        root = Path("/dev/fd")
    try:
        descriptors = sorted(
            int(entry.name)
            for entry in root.iterdir()
            if entry.name.isdigit()
        )
    except OSError:
        descriptors = list(range(0, 64))
    for descriptor in descriptors:
        try:
            metadata = os.fstat(descriptor)
        except OSError:
            continue
        target_path = root / str(descriptor)
        try:
            target = os.readlink(target_path)
        except OSError:
            if stat.S_ISSOCK(metadata.st_mode):
                kind = "socket"
            elif stat.S_ISFIFO(metadata.st_mode):
                kind = "pipe"
            elif stat.S_ISREG(metadata.st_mode):
                kind = "regular"
            else:
                kind = "other"
            target = f"{kind}:{metadata.st_dev}:{metadata.st_ino}"
        result[str(descriptor)] = target
    return result


def _model_bootstrap(episode: SolverEpisodeDTO) -> bytes:
    # The fixed-model proxy sees task content and limits, but never the bearer
    # database handle, epoch/snapshot binding, expiry, source, or gold.
    return canonical_json_bytes(
        {
            "schema_version": "fg-solver-model-bootstrap-v1",
            "question": episode.question,
            "official_instructions": episode.official_instructions,
            "artifact_exposure": episode.artifact_exposure.to_dict(),
            "limits": episode.limits.to_dict(),
            "broker_protocol_version": (
                episode.authorized_database_handle.broker_protocol_version
            ),
        }
    )


def main() -> int:
    _sanitize_runtime_environment()
    broker_fd = int(os.environ["FG_SOLVER_BROKER_FD"])
    model_fd = int(os.environ["FG_SOLVER_MODEL_FD"])
    _close_unlisted_fds({0, 1, 2, broker_fd, model_fd})
    broker = _socket_from_inherited_fd("FG_SOLVER_BROKER_FD")
    model = _socket_from_inherited_fd("FG_SOLVER_MODEL_FD")
    try:
        work_root = Path(os.environ["FG_SOLVER_WORK_ROOT"]).resolve()
        home = Path(os.environ["HOME"]).resolve()
        initial_home_entries = sorted(entry.name for entry in home.iterdir())
        initial_cwd_entries = sorted(
            entry.name for entry in Path.cwd().iterdir()
        )
        episode_bytes = _read_frame_stream(sys.stdin.buffer)
        episode = SolverEpisodeDTO.from_json_bytes(episode_bytes)
        timeout = episode.limits.model_wall_ms / 1000.0
        broker.settimeout(timeout)
        model.settimeout(timeout)

        _send_frame(model, OP_BOOTSTRAP + _model_bootstrap(episode))
        broker_calls = 0
        finish_payload = b""
        for _ in range(episode.limits.max_model_turns):
            command = _read_frame_socket(model)
            if not command:
                raise RuntimeError("model command is empty")
            opcode, payload = command[:1], command[1:]
            if opcode == OP_FINISH:
                finish_payload = payload
                break
            if opcode != OP_BROKER_CALL:
                raise RuntimeError("model command opcode is not allowlisted")
            _send_frame(broker, payload)
            response = _read_frame_socket(broker)
            _send_frame(model, OP_BROKER_RESULT + response)
            broker_calls += 1
        else:
            raise RuntimeError("model turn budget exhausted without finish")

        receipt = {
            "schema_version": RECEIPT_SCHEMA_VERSION,
            "pid": os.getpid(),
            "episode_sha256": hashlib.sha256(episode_bytes).hexdigest(),
            "model_bootstrap_sha256": hashlib.sha256(
                _model_bootstrap(episode)
            ).hexdigest(),
            "finish_payload_sha256": hashlib.sha256(
                finish_payload
            ).hexdigest(),
            "broker_calls": broker_calls,
            "work_root": str(work_root),
            "cwd": str(Path.cwd()),
            "home": str(home),
            "initial_home_entries": initial_home_entries,
            "initial_cwd_entries": initial_cwd_entries,
            "final_home_entries": sorted(
                entry.name for entry in home.iterdir()
            ),
            "final_cwd_entries": sorted(
                entry.name for entry in Path.cwd().iterdir()
            ),
            "environment": dict(sorted(os.environ.items())),
            "open_fd_targets": _open_fd_targets(),
            "linux_oci_enforcement_verified": False,
        }
        sys.stdout.buffer.write(canonical_json_bytes(receipt) + b"\n")
        sys.stdout.buffer.flush()
        return 0
    finally:
        broker.close()
        model.close()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BaseException as exc:
        error = {
            "schema_version": "fg-one-episode-solver-worker-error-v1",
            "error_type": type(exc).__name__,
            "message_sha256": hashlib.sha256(
                str(exc).encode("utf-8", errors="replace")
            ).hexdigest(),
        }
        sys.stderr.write(
            json.dumps(error, sort_keys=True, separators=(",", ":")) + "\n"
        )
        raise
