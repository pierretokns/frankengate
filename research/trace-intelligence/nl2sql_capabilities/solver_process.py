"""Fresh-process supervisor for one capability-isolated solver episode.

The child receives exactly one length-prefixed :class:`SolverEpisodeDTO` on
stdin.  Its only non-standard inherited descriptors are two explicitly passed
Unix stream sockets: one broker channel and one fixed-model-proxy channel.
Model and broker payloads are opaque binary frames to this harness; the child
does not deserialize benchmark manifests, source locators, gold, evaluator
inputs, database credentials, or signing material.

This module proves process construction and byte capture on the local host.  It
does not claim that macOS process tests enforce the Linux OCI controls defined
in :mod:`nl2sql_capabilities.solver_oci`.
"""

from __future__ import annotations

from dataclasses import dataclass
import base64
import hashlib
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import tempfile
import threading
from typing import Callable, Mapping

from .dto import MAX_FRAME_BYTES, SolverEpisodeDTO, canonical_json_bytes


OP_BOOTSTRAP = b"\x10"
OP_BROKER_CALL = b"\x20"
OP_BROKER_RESULT = b"\x21"
OP_FINISH = b"\x7f"

PROCESS_RECEIPT_SCHEMA_VERSION = "fg-solver-process-supervisor-receipt-v1"
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


class SolverProcessError(RuntimeError):
    """The child or one of its supervised peer services failed."""


class FrameProtocolError(SolverProcessError):
    """A model/broker peer violated the bounded binary framing contract."""


@dataclass(frozen=True)
class WireEvent:
    sequence: int
    channel: str
    direction: str
    data: bytes


class _WireRecorder:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: list[WireEvent] = []
        self._next_sequence = 0

    def record(self, channel: str, direction: str, data: bytes) -> None:
        if type(data) is not bytes:
            raise TypeError("captured wire data must be exact bytes")
        with self._lock:
            self._events.append(
                WireEvent(
                    sequence=self._next_sequence,
                    channel=channel,
                    direction=direction,
                    data=data,
                )
            )
            self._next_sequence += 1

    def snapshot(self) -> tuple[WireEvent, ...]:
        with self._lock:
            return tuple(sorted(self._events, key=lambda event: event.sequence))


def _frame(payload: bytes) -> bytes:
    if type(payload) is not bytes or len(payload) > MAX_FRAME_BYTES:
        raise FrameProtocolError("payload exceeds the bounded frame contract")
    return struct.pack(">I", len(payload)) + payload


class CapturedPeer:
    """Parent-side Unix peer that records every framed byte sent or received."""

    def __init__(
        self,
        *,
        sock: socket.socket,
        channel: str,
        recorder: _WireRecorder,
    ) -> None:
        self._socket = sock
        self._channel = channel
        self._recorder = recorder

    def _recv_exact(self, count: int) -> bytes:
        chunks: list[bytes] = []
        remaining = count
        while remaining:
            chunk = self._socket.recv(remaining)
            if not chunk:
                raise FrameProtocolError(
                    f"{self._channel} closed during a frame"
                )
            chunks.append(chunk)
            remaining -= len(chunk)
            self._recorder.record(
                self._channel, "from_solver", chunk
            )
        return b"".join(chunks)

    def recv_frame(self) -> bytes:
        prefix = self._recv_exact(4)
        size = struct.unpack(">I", prefix)[0]
        if size > MAX_FRAME_BYTES:
            raise FrameProtocolError(
                f"{self._channel} frame exceeds {MAX_FRAME_BYTES} bytes"
            )
        payload = self._recv_exact(size)
        return payload

    def send_frame(self, payload: bytes) -> None:
        framed = _frame(payload)
        offset = 0
        while offset < len(framed):
            sent = self._socket.send(framed[offset:])
            if sent <= 0:
                raise FrameProtocolError(
                    f"{self._channel} closed while sending a frame"
                )
            chunk = framed[offset : offset + sent]
            self._recorder.record(self._channel, "to_solver", chunk)
            offset += sent

    def close(self) -> None:
        try:
            self._socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self._socket.close()


PeerService = Callable[[CapturedPeer], None]


@dataclass(frozen=True)
class CanaryFinding:
    canary_name: str
    representation: str
    channel: str


@dataclass(frozen=True)
class SolverProcessResult:
    returncode: int
    pid: int
    work_root: Path
    episode_stdin: bytes
    stdout: bytes
    stderr: bytes
    wire_events: tuple[WireEvent, ...]
    child_receipt: Mapping[str, object]
    canary_findings: tuple[CanaryFinding, ...]


def _canary_representations(value: bytes) -> dict[str, bytes]:
    digest = hashlib.sha256(value).hexdigest().encode("ascii")
    return {
        "raw": value,
        "hex": value.hex().encode("ascii"),
        "base64": base64.b64encode(value),
        "base64url": base64.urlsafe_b64encode(value).rstrip(b"="),
        "sha256_hex": digest,
    }


def _scan_canaries(
    *,
    canaries: Mapping[str, bytes],
    channels: Mapping[str, bytes],
) -> tuple[CanaryFinding, ...]:
    findings: list[CanaryFinding] = []
    for name, value in canaries.items():
        if type(name) is not str or not name:
            raise ValueError("canary names must be non-empty strings")
        if type(value) is not bytes or len(value) < 16:
            raise ValueError("canaries must contain at least 16 exact bytes")
        for representation, needle in _canary_representations(value).items():
            for channel, haystack in channels.items():
                if needle and needle in haystack:
                    findings.append(
                        CanaryFinding(
                            canary_name=name,
                            representation=representation,
                            channel=channel,
                        )
                    )
    return tuple(findings)


def _sanitized_environment(
    *,
    work_root: Path,
    broker_fd: int,
    model_fd: int,
) -> dict[str, str]:
    return {
        "HOME": str(work_root / "home"),
        "TMPDIR": str(work_root / "tmp"),
        "XDG_CACHE_HOME": str(work_root / "xdg-cache"),
        "XDG_CONFIG_HOME": str(work_root / "xdg-config"),
        "XDG_DATA_HOME": str(work_root / "xdg-data"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "FG_SOLVER_BROKER_FD": str(broker_fd),
        "FG_SOLVER_MODEL_FD": str(model_fd),
        "FG_SOLVER_WORK_ROOT": str(work_root),
    }


class OneEpisodeSolverHarness:
    """Launch a new isolated child and supervise exactly one episode."""

    def __init__(
        self,
        *,
        python_executable: str | None = None,
        worker_path: Path | None = None,
        timeout_grace_seconds: float = 2.0,
    ) -> None:
        self._python_executable = python_executable or sys.executable
        self._worker_path = worker_path or (
            Path(__file__).with_name("solver_process_worker.py")
        )
        self._timeout_grace_seconds = timeout_grace_seconds

    def run(
        self,
        *,
        episode: SolverEpisodeDTO,
        broker_service: PeerService,
        model_service: PeerService,
        canaries: Mapping[str, bytes],
    ) -> SolverProcessResult:
        if type(episode) is not SolverEpisodeDTO:
            raise TypeError("one-episode harness accepts only SolverEpisodeDTO")
        # Re-enter through strict decoding so direct dataclass construction
        # cannot bypass the closed solver boundary.
        episode = SolverEpisodeDTO.from_json_bytes(episode.canonical_bytes())
        episode_stdin = _frame(episode.canonical_bytes())

        recorder = _WireRecorder()
        recorder.record("episode_stdin", "to_solver", episode_stdin)
        service_errors: list[tuple[str, BaseException]] = []
        service_error_lock = threading.Lock()

        with tempfile.TemporaryDirectory(
            prefix="fg-one-episode-solver-"
        ) as temporary:
            work_root = Path(temporary).resolve()
            for name in (
                "home",
                "cwd",
                "tmp",
                "xdg-cache",
                "xdg-config",
                "xdg-data",
            ):
                (work_root / name).mkdir(mode=0o700)

            broker_parent, broker_child = socket.socketpair(
                socket.AF_UNIX, socket.SOCK_STREAM
            )
            model_parent, model_child = socket.socketpair(
                socket.AF_UNIX, socket.SOCK_STREAM
            )
            timeout_seconds = (
                episode.limits.model_wall_ms / 1000.0
                + self._timeout_grace_seconds
            )
            for peer in (
                broker_parent,
                broker_child,
                model_parent,
                model_child,
            ):
                peer.settimeout(timeout_seconds)

            environment = _sanitized_environment(
                work_root=work_root,
                broker_fd=broker_child.fileno(),
                model_fd=model_child.fileno(),
            )
            command = [
                self._python_executable,
                "-I",
                "-B",
                str(self._worker_path.resolve()),
            ]
            process = subprocess.Popen(
                command,
                cwd=work_root / "cwd",
                env=environment,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                pass_fds=(broker_child.fileno(), model_child.fileno()),
                close_fds=True,
                start_new_session=True,
            )
            broker_child.close()
            model_child.close()

            broker_peer = CapturedPeer(
                sock=broker_parent,
                channel="broker",
                recorder=recorder,
            )
            model_peer = CapturedPeer(
                sock=model_parent,
                channel="model",
                recorder=recorder,
            )

            def invoke(
                name: str, service: PeerService, peer: CapturedPeer
            ) -> None:
                try:
                    service(peer)
                except BaseException as exc:
                    with service_error_lock:
                        service_errors.append((name, exc))
                finally:
                    peer.close()

            threads = [
                threading.Thread(
                    target=invoke,
                    args=("broker", broker_service, broker_peer),
                    daemon=True,
                ),
                threading.Thread(
                    target=invoke,
                    args=("model", model_service, model_peer),
                    daemon=True,
                ),
            ]
            for thread in threads:
                thread.start()
            try:
                stdout, stderr = process.communicate(
                    input=episode_stdin,
                    timeout=timeout_seconds,
                )
            except subprocess.TimeoutExpired as exc:
                process.kill()
                stdout, stderr = process.communicate()
                raise SolverProcessError(
                    "one-episode solver exceeded its wall-time boundary"
                ) from exc
            finally:
                broker_peer.close()
                model_peer.close()
                for thread in threads:
                    thread.join(timeout=self._timeout_grace_seconds)

            if any(thread.is_alive() for thread in threads):
                raise SolverProcessError("peer service did not terminate")
            if service_errors:
                name, error = service_errors[0]
                raise SolverProcessError(
                    f"{name} peer service failed: {error}"
                ) from error

            child_receipt: Mapping[str, object] = {}
            if stdout:
                try:
                    decoded = json.loads(stdout.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise SolverProcessError(
                        "child stdout is not its single JSON receipt"
                    ) from exc
                if type(decoded) is not dict:
                    raise SolverProcessError("child receipt is not an object")
                child_receipt = decoded

            events = recorder.snapshot()
            channels: dict[str, bytes] = {
                "episode_stdin": episode_stdin,
                "stdout": stdout,
                "stderr": stderr,
                "child_environment": canonical_json_bytes(environment),
                "process_command": "\0".join(command).encode("utf-8"),
                "process_cwd": str(work_root / "cwd").encode("utf-8"),
            }
            aggregate_wire: dict[tuple[str, str], list[bytes]] = {}
            for event in events:
                key = (
                    f"wire:{event.sequence}:{event.channel}:"
                    f"{event.direction}"
                )
                channels[key] = event.data
                aggregate_wire.setdefault(
                    (event.channel, event.direction), []
                ).append(event.data)
            for (channel, direction), chunks in aggregate_wire.items():
                channels[
                    f"wire-aggregate:{channel}:{direction}"
                ] = b"".join(chunks)
            findings = _scan_canaries(
                canaries=canaries,
                channels=channels,
            )
            result = SolverProcessResult(
                returncode=process.returncode,
                pid=process.pid,
                work_root=work_root,
                episode_stdin=episode_stdin,
                stdout=stdout,
                stderr=stderr,
                wire_events=events,
                child_receipt=child_receipt,
                canary_findings=findings,
            )
        return result


__all__ = [
    "CanaryFinding",
    "CapturedPeer",
    "FrameProtocolError",
    "OP_BOOTSTRAP",
    "OP_BROKER_CALL",
    "OP_BROKER_RESULT",
    "OP_FINISH",
    "OneEpisodeSolverHarness",
    "SANITIZED_ENVIRONMENT_KEYS",
    "SolverProcessError",
    "SolverProcessResult",
    "WireEvent",
]
