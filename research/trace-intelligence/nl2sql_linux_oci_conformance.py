#!/usr/bin/env python3
"""Run the Frankengate one-episode solver profile under real Linux ``runc``.

This is an enforcement conformance runner, not a profile-shape test.  Run it
as root *inside* the Colima VM so that ``runc`` can create the required
namespaces and cgroups.  It refuses to pull an image and accepts only the
already-cached official image at the frozen digest.

Example from the macOS host::

    colima ssh -- sudo -n python3 \
      /Users/pierre/dev/bifrost/research/trace-intelligence/\
nl2sql_linux_oci_conformance.py \
      --raw-output /tmp/fg-nl2sql-oci-raw.json \
      --aggregate-output /tmp/fg-nl2sql-oci-aggregate.json

The raw output must be outside the repository.  It contains exact base64 wire,
stdio, OCI configuration, and probe evidence.  The aggregate output contains
only hashes, counts, classifications, and pass/fail decisions.
"""

from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
import errno
import hashlib
import json
import os
from pathlib import Path
import platform
import secrets
import shutil
import signal
import socket
import struct
import subprocess
import sys
import tarfile
import tempfile
import textwrap
import threading
import time
from pathlib import PurePosixPath
from typing import Any, Iterable, Mapping, Sequence


TRACE_INTELLIGENCE_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = TRACE_INTELLIGENCE_ROOT.parents[1]
sys.path.insert(0, str(TRACE_INTELLIGENCE_ROOT))

from nl2sql_capabilities.dto import (  # noqa: E402
    ArtifactExposureDTO,
    AuthorizedDatabaseHandleDTO,
    BROKER_PROTOCOL_VERSION,
    SOLVER_EPISODE_SCHEMA_VERSION,
    SolverEpisodeDTO,
    SolverLimitsDTO,
    canonical_json_bytes,
    encode_base64url,
)
from nl2sql_capabilities.solver_oci import (  # noqa: E402
    BROKER_FD,
    MODEL_FD,
    build_runc_argv,
    build_solver_oci_config,
    validate_solver_oci_config,
)


IMAGE_DIGEST = (
    "sha256:399babc8b49529dabfd9c922f2b5eea81d611e4512e3ed250d75bd2e7683f4b0"
)
IMAGE_REFERENCE = f"python@{IMAGE_DIGEST}"
RAW_SCHEMA_VERSION = "fg-nl2sql-linux-oci-conformance-raw-v1"
AGGREGATE_SCHEMA_VERSION = "fg-nl2sql-linux-oci-conformance-aggregate-v1"
PROBE_SCHEMA_VERSION = "fg-nl2sql-linux-oci-kernel-probe-v1"
PROBE_PREFIX = "FG_OCI_PROBE_JSON:"
EXPECTED_STAGED_FILES = (
    "nl2sql_capabilities/__init__.py",
    "nl2sql_capabilities/dto.py",
    "nl2sql_capabilities/solver_process_worker.py",
)
EXPECTED_ENV_KEYS = frozenset(
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
ABSENT_SENSITIVE_PATHS = (
    "/source",
    "/sources",
    "/workspace",
    "/repo",
    "/run/secrets",
    "/root/.aws",
    "/root/.config/gcloud",
    "/home/.aws",
    "/home/.config/gcloud",
    "/opt/frankengate/manifests",
    "/opt/frankengate/credentials",
    "/etc/frankengate/credentials",
)

OP_BOOTSTRAP = b"\x10"
OP_BROKER_CALL = b"\x20"
OP_BROKER_RESULT = b"\x21"
OP_FINISH = b"\x7f"
MAX_FRAME_BYTES = 16 * 1024 * 1024


class ConformanceError(RuntimeError):
    """The runner could not produce trustworthy enforcement evidence."""


@dataclass(frozen=True)
class WireEvent:
    sequence: int
    channel: str
    direction: str
    data: bytes


class WireRecorder:
    def __init__(self) -> None:
        self._events: list[WireEvent] = []
        self._lock = threading.Lock()
        self._sequence = 0

    def record(self, channel: str, direction: str, data: bytes) -> None:
        with self._lock:
            self._events.append(
                WireEvent(self._sequence, channel, direction, bytes(data))
            )
            self._sequence += 1

    def snapshot(self) -> tuple[WireEvent, ...]:
        with self._lock:
            return tuple(sorted(self._events, key=lambda item: item.sequence))


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _frame(payload: bytes) -> bytes:
    if len(payload) > MAX_FRAME_BYTES:
        raise ConformanceError("frame exceeds protocol maximum")
    return struct.pack(">I", len(payload)) + payload


def _recv_exact(
    peer: socket.socket,
    count: int,
    *,
    recorder: WireRecorder,
    channel: str,
) -> bytes:
    chunks: list[bytes] = []
    remaining = count
    while remaining:
        chunk = peer.recv(remaining)
        if not chunk:
            raise ConformanceError(f"{channel} closed during a frame")
        recorder.record(channel, "from_solver", chunk)
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _recv_frame(
    peer: socket.socket, *, recorder: WireRecorder, channel: str
) -> bytes:
    prefix = _recv_exact(peer, 4, recorder=recorder, channel=channel)
    size = struct.unpack(">I", prefix)[0]
    if size > MAX_FRAME_BYTES:
        raise ConformanceError(f"{channel} frame exceeds protocol maximum")
    return _recv_exact(peer, size, recorder=recorder, channel=channel)


def _send_frame(
    peer: socket.socket,
    payload: bytes,
    *,
    recorder: WireRecorder,
    channel: str,
) -> None:
    data = _frame(payload)
    peer.sendall(data)
    recorder.record(channel, "to_solver", data)


def _probe_bootstrap_source() -> str:
    """Return self-contained probe code passed directly as the Python argv."""

    # The code runs after runc has applied namespaces, mounts, seccomp, identity,
    # capabilities, and no-new-privileges, but before the solver worker starts.
    return textwrap.dedent(
        f"""
        import errno, json, os, pathlib, runpy, socket, stat, sys

        def attempt_write(path):
            try:
                with open(path, "wb") as stream:
                    stream.write(b"x")
                return {{"ok": True, "errno": None}}
            except OSError as exc:
                return {{"ok": False, "errno": exc.errno}}

        def valid_fds():
            result = {{}}
            for name in os.listdir("/proc/self/fd"):
                if not name.isdigit():
                    continue
                fd = int(name)
                try:
                    metadata = os.fstat(fd)
                except OSError:
                    continue
                try:
                    target = os.readlink("/proc/self/fd/" + name)
                except OSError:
                    target = "unreadable"
                result[name] = target
            return result

        def mount_type(destination):
            selected = None
            with open("/proc/self/mountinfo", "r", encoding="utf-8") as stream:
                for line in stream:
                    left, right = line.rstrip("\\n").split(" - ", 1)
                    fields = left.split()
                    if fields[4] == destination:
                        selected = right.split()[0]
            return selected

        def network_probe(family):
            try:
                peer = socket.socket(family, socket.SOCK_STREAM)
            except OSError as exc:
                return {{"created": False, "errno": exc.errno}}
            else:
                peer.close()
                return {{"created": True, "errno": None}}

        status = {{}}
        with open("/proc/self/status", "r", encoding="utf-8") as stream:
            for line in stream:
                if ":" in line:
                    key, value = line.split(":", 1)
                    if key in ("NoNewPrivs", "Seccomp", "CapBnd", "CapEff",
                               "CapInh", "CapPrm", "CapAmb"):
                        status[key] = value.strip()

        tmpfs = {{}}
        for destination in ("/home", "/tmp", "/work"):
            metadata = os.stat(destination)
            write_path = destination + "/.fg-write-probe"
            write_result = attempt_write(write_path)
            tmpfs[destination] = {{
                "uid": metadata.st_uid,
                "gid": metadata.st_gid,
                "mode": stat.S_IMODE(metadata.st_mode),
                "mount_type": mount_type(destination),
                "write": write_result,
            }}

        staged_root = pathlib.Path("/opt/frankengate")
        staged_files = sorted(
            str(path.relative_to(staged_root))
            for path in staged_root.rglob("*")
            if path.is_file()
        )
        probe = {{
            "schema_version": "{PROBE_SCHEMA_VERSION}",
            "uid": os.getuid(),
            "euid": os.geteuid(),
            "gid": os.getgid(),
            "egid": os.getegid(),
            "cwd": os.getcwd(),
            "environment": dict(sorted(os.environ.items())),
            "argv_sha256": __import__("hashlib").sha256(
                "\\0".join(sys.argv).encode("utf-8")
            ).hexdigest(),
            "fds": valid_fds(),
            "proc_status": status,
            "root_write": attempt_write("/opt/frankengate/.fg-root-write-probe"),
            "tmpfs": tmpfs,
            "network": {{
                "AF_INET": network_probe(socket.AF_INET),
                "AF_INET6": network_probe(socket.AF_INET6),
            }},
            "staged_files": staged_files,
            "sensitive_path_presence": {{
                path: os.path.lexists(path)
                for path in {ABSENT_SENSITIVE_PATHS!r}
            }},
        }}
        sys.stderr.write(
            "{PROBE_PREFIX}" +
            json.dumps(probe, sort_keys=True, separators=(",", ":")) +
            "\\n"
        )
        sys.stderr.flush()
        runpy.run_path(
            "/opt/frankengate/nl2sql_capabilities/solver_process_worker.py",
            run_name="__main__",
        )
        """
    ).strip()


def _build_episode() -> SolverEpisodeDTO:
    artifact_content = ""
    return SolverEpisodeDTO(
        schema_version=SOLVER_EPISODE_SCHEMA_VERSION,
        question="Return the count from the governed relation.",
        official_instructions="Use only the offered governed SQL tool.",
        authorized_database_handle=AuthorizedDatabaseHandleDTO(
            handle=encode_base64url(bytes(range(32))),
            broker_protocol_version=BROKER_PROTOCOL_VERSION,
            authorization_epoch_ref_sha256=_sha256(b"epoch-ref"),
            authority_snapshot_sha256=_sha256(b"authority-snapshot"),
            expires_at_unix_ms=4_102_444_800_000,
        ),
        artifact_exposure=ArtifactExposureDTO(
            artifact_id="no-skill-artifact",
            artifact_sha256=_sha256(artifact_content.encode()),
            content=artifact_content,
        ),
        limits=SolverLimitsDTO(
            max_model_turns=2,
            max_schema_calls=1,
            max_sql_attempts=1,
            max_generated_tokens_per_call=128,
            max_generated_tokens_per_episode=256,
            model_wall_ms=30_000,
            model_result_max_rows=8,
            model_result_max_bytes=16_384,
        ),
    )


def _canary_values() -> dict[str, bytes]:
    nonce = secrets.token_bytes(32)
    names = (
        "source_id",
        "gold_answer",
        "hidden_label",
        "adjudication",
        "database_dsn",
        "signing_key",
    )
    return {
        name: hashlib.sha256(nonce + b"\0" + name.encode()).digest()
        for name in names
    }


def _canary_representations(value: bytes) -> dict[str, bytes]:
    return {
        "raw": value,
        "hex": value.hex().encode(),
        "base64": base64.b64encode(value),
        "base64url": base64.urlsafe_b64encode(value).rstrip(b"="),
        "sha256_hex": _sha256(value).encode(),
    }


def scan_canaries(
    canaries: Mapping[str, bytes], channels: Mapping[str, bytes]
) -> list[dict[str, str]]:
    """Return every exact/encoded canary occurrence in child-visible bytes."""

    findings: list[dict[str, str]] = []
    for name, value in canaries.items():
        if not name or len(value) < 16:
            raise ValueError("canaries require a name and at least 16 bytes")
        for representation, needle in _canary_representations(value).items():
            for channel, haystack in channels.items():
                if needle and needle in haystack:
                    findings.append(
                        {
                            "canary": name,
                            "representation": representation,
                            "channel": channel,
                        }
                    )
    return findings


def parse_probe(stderr: bytes) -> tuple[dict[str, Any] | None, list[str]]:
    """Extract the kernel probe without discarding other stderr evidence."""

    errors: list[str] = []
    probes: list[dict[str, Any]] = []
    for raw_line in stderr.splitlines():
        if not raw_line.startswith(PROBE_PREFIX.encode()):
            continue
        try:
            value = json.loads(raw_line[len(PROBE_PREFIX) :])
        except (UnicodeDecodeError, json.JSONDecodeError):
            errors.append("probe_json_invalid")
            continue
        if not isinstance(value, dict):
            errors.append("probe_json_not_object")
            continue
        probes.append(value)
    if len(probes) != 1:
        errors.append(f"probe_count_{len(probes)}")
        return (probes[0] if probes else None), errors
    return probes[0], errors


def classify_enforcement(
    *,
    returncode: int,
    probe: Mapping[str, Any] | None,
    child_receipt: Mapping[str, Any] | None,
    peer_errors: Sequence[str],
    canary_findings: Sequence[Mapping[str, str]],
    profile_variant: str = "frozen",
    cleanup_status: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert raw kernel evidence to explicit, independently useful gates."""

    gates: dict[str, dict[str, Any]] = {}

    def gate(name: str, passed: bool, observed: Any) -> None:
        gates[name] = {"passed": bool(passed), "observed": observed}

    gate("runc_exit_zero", returncode == 0, returncode)
    gate("peer_protocol", not peer_errors, list(peer_errors))
    gate("worker_receipt", child_receipt is not None, child_receipt is not None)
    gate("no_canary_disclosure", not canary_findings, len(canary_findings))
    gate("frozen_profile", profile_variant == "frozen", profile_variant)
    cleanup_status = cleanup_status or {
        "passed": True,
        "reason": "not_applicable",
    }
    gate(
        "runtime_cleanup",
        cleanup_status.get("passed") is True,
        dict(cleanup_status),
    )
    if probe is None:
        gate("kernel_probe", False, "missing")
        return {
            "passed": False,
            "classification": "profile_startup_or_probe_failure",
            "gates": gates,
        }

    gate(
        "probe_schema",
        probe.get("schema_version") == PROBE_SCHEMA_VERSION,
        probe.get("schema_version"),
    )
    identities = tuple(probe.get(name) for name in ("uid", "euid", "gid", "egid"))
    gate("non_root_identity", identities == (65532, 65532, 65532, 65532), identities)
    gate("isolated_cwd", probe.get("cwd") == "/work", probe.get("cwd"))

    root_write = probe.get("root_write")
    gate(
        "readonly_rootfs",
        isinstance(root_write, Mapping)
        and root_write.get("ok") is False
        and root_write.get("errno") == errno.EROFS,
        root_write,
    )
    tmpfs = probe.get("tmpfs")
    for destination in ("/home", "/tmp", "/work"):
        observed = tmpfs.get(destination) if isinstance(tmpfs, Mapping) else None
        passed = (
            isinstance(observed, Mapping)
            and observed.get("uid") == 65532
            and observed.get("gid") == 65532
            and observed.get("mode") == 0o700
            and observed.get("mount_type") == "tmpfs"
            and isinstance(observed.get("write"), Mapping)
            and observed["write"].get("ok") is True
        )
        gate(f"tmpfs_{destination[1:]}", passed, observed)

    network = probe.get("network")
    for family in ("AF_INET", "AF_INET6"):
        observed = network.get(family) if isinstance(network, Mapping) else None
        passed = (
            isinstance(observed, Mapping)
            and observed.get("created") is False
            and observed.get("errno") == errno.EPERM
        )
        gate(f"deny_{family.lower()}_socket", passed, observed)

    status = probe.get("proc_status")
    status = status if isinstance(status, Mapping) else {}
    gate("no_new_privileges", status.get("NoNewPrivs") == "1", status.get("NoNewPrivs"))
    gate("seccomp_filter", status.get("Seccomp") == "2", status.get("Seccomp"))
    capability_values = {
        name: status.get(name)
        for name in ("CapBnd", "CapEff", "CapInh", "CapPrm", "CapAmb")
    }
    gate(
        "capabilities_empty",
        set(capability_values.values()) == {"0000000000000000"},
        capability_values,
    )
    gate(
        "exact_staged_files",
        probe.get("staged_files") == list(EXPECTED_STAGED_FILES),
        probe.get("staged_files"),
    )
    sensitive = probe.get("sensitive_path_presence")
    gate(
        "sensitive_paths_absent",
        isinstance(sensitive, Mapping)
        and set(sensitive) == set(ABSENT_SENSITIVE_PATHS)
        and not any(sensitive.values()),
        sensitive,
    )
    environment = probe.get("environment")
    gate(
        "sanitized_environment",
        isinstance(environment, Mapping)
        and set(environment) == EXPECTED_ENV_KEYS
        and environment.get("FG_SOLVER_BROKER_FD") == str(BROKER_FD)
        and environment.get("FG_SOLVER_MODEL_FD") == str(MODEL_FD),
        sorted(environment) if isinstance(environment, Mapping) else environment,
    )
    fds = probe.get("fds")
    gate(
        "exact_descriptors",
        isinstance(fds, Mapping) and set(fds) == {"0", "1", "2", "3", "4"},
        fds,
    )

    failed = [name for name, value in gates.items() if not value["passed"]]
    if not failed:
        classification = "enforcement_conformant"
    elif (
        returncode != 0
        or probe is None
        or child_receipt is None
        or bool(peer_errors)
    ):
        classification = "profile_startup_or_probe_failure"
    else:
        classification = "enforcement_nonconformant"
    return {"passed": not failed, "classification": classification, "gates": gates}


def classify_runtime_stderr(stderr: bytes) -> list[str]:
    """Classify known runtime failures while retaining exact bytes externally."""

    findings: list[str] = []
    if b"ensure /proc/self/fd is on procfs: operation not permitted" in stderr:
        findings.append(
            "preserved_fd_procfs_validation_denied_likely_missing_fstatfs"
        )
    if b"setrlimit" in stderr.lower() and b"operation not permitted" in stderr:
        findings.append("rlimit_application_denied")
    if (
        b"exec /usr/local/bin/python3: resource temporarily unavailable"
        in stderr
    ):
        findings.append("python_exec_eagain_likely_rlimit_nproc")
    return findings


def minimize_decision(decision: Mapping[str, Any]) -> dict[str, Any]:
    """Remove exact paths, descriptor targets, and diagnostics from aggregate."""

    minimized = json.loads(json.dumps(decision))
    gates = minimized.get("gates", {})
    if not isinstance(gates, dict):
        raise ConformanceError("decision gates are invalid")
    sensitive = gates.get("sensitive_paths_absent")
    if isinstance(sensitive, dict):
        observed = sensitive.get("observed")
        sensitive["observed"] = {
            "checked_path_count": (
                len(observed) if isinstance(observed, dict) else 0
            ),
            "present_path_count": (
                sum(bool(value) for value in observed.values())
                if isinstance(observed, dict)
                else 0
            ),
        }
    descriptors = gates.get("exact_descriptors")
    if isinstance(descriptors, dict):
        observed = descriptors.get("observed")
        descriptors["observed"] = {
            "fd_numbers": (
                sorted(observed) if isinstance(observed, dict) else []
            ),
            "socket_fd_numbers": (
                sorted(
                    name
                    for name, target in observed.items()
                    if isinstance(target, str)
                    and target.startswith("socket:")
                )
                if isinstance(observed, dict)
                else []
            ),
        }
    peer = gates.get("peer_protocol")
    if isinstance(peer, dict):
        observed = peer.get("observed")
        peer["observed"] = {
            "error_count": len(observed) if isinstance(observed, list) else 0
        }
    return minimized


def _run_checked(args: Sequence[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
    result = subprocess.run(
        list(args),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        **kwargs,
    )
    if result.returncode != 0:
        rendered = " ".join(args[:3])
        raise ConformanceError(
            f"{rendered} failed ({result.returncode}): "
            f"{result.stderr.decode(errors='replace')[:400]}"
        )
    return result


def _verify_cached_image() -> dict[str, Any]:
    result = _run_checked(("docker", "image", "inspect", IMAGE_REFERENCE))
    values = json.loads(result.stdout)
    if not isinstance(values, list) or len(values) != 1:
        raise ConformanceError("cached image inspect returned an unexpected shape")
    image = values[0]
    repo_digests = image.get("RepoDigests", [])
    if IMAGE_REFERENCE not in repo_digests:
        raise ConformanceError("cached image does not carry the frozen repo digest")
    return {
        "id": image.get("Id"),
        "repo_digests": repo_digests,
        "architecture": image.get("Architecture"),
        "os": image.get("Os"),
    }


def _extract_rootfs(bundle: Path, cleanup_containers: list[str]) -> None:
    name = f"fg-nl2sql-oci-rootfs-{os.getpid()}-{secrets.token_hex(4)}"
    created = _run_checked(
        ("docker", "create", "--name", name, "--network", "none", IMAGE_REFERENCE)
    )
    if not created.stdout.strip():
        raise ConformanceError("docker create returned no container ID")
    cleanup_containers.append(name)
    try:
        rootfs = bundle / "rootfs"
        rootfs.mkdir()
        archive = bundle / "rootfs.tar"
        _run_checked(("docker", "export", "--output", str(archive), name))
        # Docker exports rootfs-absolute links (for example
        # /bin/arch -> /bin/busybox). Interpret them as container-root relative
        # while rejecting members or relative links that escape that root.
        with tarfile.open(archive, "r:*") as stream:
            root = rootfs.resolve()
            for member in stream.getmembers():
                member_path = PurePosixPath(member.name)
                if member_path.is_absolute() or ".." in member_path.parts:
                    raise ConformanceError("image archive path escapes rootfs")
                target = (rootfs / member_path).resolve()
                if root != target and root not in target.parents:
                    raise ConformanceError("image archive path escapes rootfs")
                if member.issym() or member.islnk():
                    link_path = PurePosixPath(member.linkname)
                    if link_path.is_absolute():
                        link_target = rootfs.joinpath(
                            *link_path.parts[1:]
                        ).resolve()
                    else:
                        link_target = (target.parent / link_path).resolve()
                    if root != link_target and root not in link_target.parents:
                        raise ConformanceError("image archive link escapes rootfs")
            stream.extractall(rootfs, filter="tar")
        archive.unlink()
    finally:
        removed = subprocess.run(
            ("docker", "rm", "-f", name),
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if removed.returncode == 0:
            cleanup_containers.remove(name)
        else:
            raise ConformanceError(
                f"failed to remove rootfs export container ({removed.returncode})"
            )


def _stage_solver(rootfs: Path) -> dict[str, str]:
    source = TRACE_INTELLIGENCE_ROOT / "nl2sql_capabilities"
    destination = rootfs / "opt" / "frankengate" / "nl2sql_capabilities"
    destination.mkdir(parents=True, mode=0o555)
    staged_sources = {
        "dto.py": source / "dto.py",
        "solver_process_worker.py": source / "solver_process_worker.py",
    }
    hashes: dict[str, str] = {}
    init = destination / "__init__.py"
    init.write_bytes(b'"""Minimal isolated solver package."""\n')
    init.chmod(0o444)
    hashes["nl2sql_capabilities/__init__.py"] = _sha256(init.read_bytes())
    for name, source_path in staged_sources.items():
        target = destination / name
        shutil.copyfile(source_path, target)
        target.chmod(0o444)
        hashes[f"nl2sql_capabilities/{name}"] = _sha256(target.read_bytes())
    (rootfs / "opt" / "frankengate").chmod(0o555)
    for name in ("home", "tmp", "work"):
        (rootfs / name).mkdir(exist_ok=True)
    return hashes


def _write_config(
    bundle: Path, *, diagnostic_extra_syscalls: Sequence[str] = ()
) -> tuple[dict[str, Any], bytes, str]:
    command = (
        "/usr/local/bin/python3",
        "-I",
        "-B",
        "-c",
        _probe_bootstrap_source(),
    )
    config = build_solver_oci_config(command=command)
    validate_solver_oci_config(config)
    profile_variant = "frozen"
    if diagnostic_extra_syscalls:
        if any(
            type(name) is not str
            or not name
            or not name.replace("_", "").isalnum()
            for name in diagnostic_extra_syscalls
        ):
            raise ConformanceError("diagnostic syscall name is invalid")
        config["linux"]["seccomp"]["syscalls"][0]["names"].extend(
            sorted(set(diagnostic_extra_syscalls))
        )
        config["annotations"][
            "frankengate.local/diagnostic-extra-syscalls"
        ] = ",".join(sorted(set(diagnostic_extra_syscalls)))
        profile_variant = "diagnostic_nonrelease"
    encoded = canonical_json_bytes(config)
    (bundle / "config.json").write_bytes(encoded)
    return config, encoded, profile_variant


def _close_descriptors_except(allowed: set[int]) -> None:
    try:
        descriptors = [
            int(name)
            for name in os.listdir("/proc/self/fd")
            if name.isdigit()
        ]
    except OSError:
        descriptors = list(range(0, 65536))
    for descriptor in descriptors:
        if descriptor in allowed:
            continue
        try:
            os.close(descriptor)
        except OSError:
            pass


def _fork_runc(
    *,
    argv: Sequence[str],
    broker_child: socket.socket,
    model_child: socket.socket,
    stdin_read: int,
    stdout_write: int,
    stderr_write: int,
) -> int:
    pid = os.fork()
    if pid:
        return pid
    try:
        # Duplicate all sources first so fd-number collisions cannot corrupt a
        # later mapping.  runc assigns preserved host FDs 3,4 to container 3,4.
        sources = [
            os.dup(stdin_read),
            os.dup(stdout_write),
            os.dup(stderr_write),
            os.dup(broker_child.fileno()),
            os.dup(model_child.fileno()),
        ]
        for source, target in zip(sources, (0, 1, 2, BROKER_FD, MODEL_FD)):
            os.dup2(source, target, inheritable=True)
        _close_descriptors_except({0, 1, 2, BROKER_FD, MODEL_FD})
        os.execvp(argv[0], list(argv))
    except BaseException as exc:
        os.write(2, f"runc exec failed: {type(exc).__name__}: {exc}\n".encode())
    os._exit(127)


def _reader(fd: int, output: bytearray) -> None:
    try:
        while True:
            chunk = os.read(fd, 65536)
            if not chunk:
                return
            output.extend(chunk)
    finally:
        os.close(fd)


def _wait_pid(pid: int, timeout_seconds: float) -> int:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        observed, status = os.waitpid(pid, os.WNOHANG)
        if observed == pid:
            return os.waitstatus_to_exitcode(status)
        time.sleep(0.02)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    _, status = os.waitpid(pid, 0)
    raise ConformanceError(
        f"runc timed out; final status {os.waitstatus_to_exitcode(status)}"
    )


def _peer_services(
    broker: socket.socket,
    model: socket.socket,
    recorder: WireRecorder,
    errors: list[str],
) -> list[threading.Thread]:
    def broker_service() -> None:
        try:
            request = _recv_frame(broker, recorder=recorder, channel="broker")
            if request != b'{"operation":"schema_summary"}':
                raise ConformanceError("broker received an unexpected request")
            _send_frame(
                broker,
                b'{"columns":["record_count"],"ok":true}',
                recorder=recorder,
                channel="broker",
            )
        except BaseException as exc:
            errors.append(f"broker:{type(exc).__name__}:{exc}")

    def model_service() -> None:
        try:
            bootstrap = _recv_frame(model, recorder=recorder, channel="model")
            if not bootstrap.startswith(OP_BOOTSTRAP):
                raise ConformanceError("model bootstrap opcode is invalid")
            _send_frame(
                model,
                OP_BROKER_CALL + b'{"operation":"schema_summary"}',
                recorder=recorder,
                channel="model",
            )
            result = _recv_frame(model, recorder=recorder, channel="model")
            if not result.startswith(OP_BROKER_RESULT):
                raise ConformanceError("model broker-result opcode is invalid")
            _send_frame(
                model,
                OP_FINISH + b'{"answer":"complete"}',
                recorder=recorder,
                channel="model",
            )
        except BaseException as exc:
            errors.append(f"model:{type(exc).__name__}:{exc}")

    threads = [
        threading.Thread(target=broker_service, name="broker-peer", daemon=True),
        threading.Thread(target=model_service, name="model-peer", daemon=True),
    ]
    for thread in threads:
        thread.start()
    return threads


def _parse_child_receipt(stdout: bytes) -> dict[str, Any] | None:
    values: list[dict[str, Any]] = []
    for line in stdout.splitlines():
        try:
            value = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if (
            isinstance(value, dict)
            and value.get("schema_version")
            == "fg-one-episode-solver-worker-receipt-v1"
        ):
            values.append(value)
    return values[0] if len(values) == 1 else None


def _raw_wire(events: Iterable[WireEvent]) -> list[dict[str, Any]]:
    return [
        {
            "sequence": event.sequence,
            "channel": event.channel,
            "direction": event.direction,
            "bytes_b64": base64.b64encode(event.data).decode(),
            "byte_count": len(event.data),
            "sha256": _sha256(event.data),
        }
        for event in events
    ]


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(value, sort_keys=True, indent=2).encode() + b"\n"
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_bytes(encoded)
    os.replace(temporary, path)


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, indent=2).encode() + b"\n"


def _exclusive_private_write(path: Path, content: bytes) -> None:
    """Create raw evidence once with mode 0600 and refuse links/overwrites."""

    path.parent.mkdir(parents=True, exist_ok=True)
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        view = memoryview(content)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise ConformanceError("raw evidence write made no progress")
            view = view[written:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _runc_cleanup_status(container_id: str) -> dict[str, Any]:
    listed = subprocess.run(
        ("runc", "list", "--format", "json"),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if listed.returncode != 0:
        return {"passed": False, "reason": "runc_list_failed"}
    try:
        values = json.loads(listed.stdout)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"passed": False, "reason": "runc_list_invalid_json"}
    if values is None:
        values = []
    if not isinstance(values, list):
        return {"passed": False, "reason": "runc_list_invalid_shape"}
    present = any(
        isinstance(value, Mapping) and value.get("id") == container_id
        for value in values
    )
    if not present:
        return {"passed": True, "reason": "container_absent"}
    deleted = subprocess.run(
        ("runc", "delete", "--force", container_id),
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return {
        "passed": deleted.returncode == 0,
        "reason": (
            "forced_delete_succeeded"
            if deleted.returncode == 0
            else "forced_delete_failed"
        ),
    }


def _assert_raw_output_external(path: Path) -> None:
    resolved = path.resolve()
    repository = REPOSITORY_ROOT.resolve()
    if resolved == repository or repository in resolved.parents:
        raise ConformanceError("raw output must be outside the repository")


def run_conformance(
    *,
    raw_output: Path,
    aggregate_output: Path,
    timeout_seconds: float = 60.0,
    diagnostic_extra_syscalls: Sequence[str] = (),
) -> dict[str, Any]:
    """Create a disposable bundle, run one episode, and emit both evidence tiers."""

    if platform.system() != "Linux":
        raise ConformanceError("actual OCI conformance requires Linux")
    if os.geteuid() != 0:
        raise ConformanceError("run as root inside the disposable Colima VM")
    _assert_raw_output_external(raw_output)
    if raw_output.resolve() == aggregate_output.resolve():
        raise ConformanceError("raw and aggregate output paths must differ")
    image = _verify_cached_image()
    runc_version = _run_checked(("runc", "--version")).stdout.decode(
        errors="replace"
    )
    episode = SolverEpisodeDTO.from_json_bytes(_build_episode().canonical_bytes())
    episode_frame = _frame(episode.canonical_bytes())
    canaries = _canary_values()
    cleanup_containers: list[str] = []
    cleanup_errors: list[str] = []
    started = time.time()

    try:
        with tempfile.TemporaryDirectory(prefix="fg-nl2sql-runc-") as temporary:
            bundle = Path(temporary) / "bundle"
            bundle.mkdir()
            _extract_rootfs(bundle, cleanup_containers)
            staged_hashes = _stage_solver(bundle / "rootfs")
            config, config_bytes, profile_variant = _write_config(
                bundle,
                diagnostic_extra_syscalls=diagnostic_extra_syscalls,
            )

            broker_parent, broker_child = socket.socketpair(
                socket.AF_UNIX, socket.SOCK_STREAM
            )
            model_parent, model_child = socket.socketpair(
                socket.AF_UNIX, socket.SOCK_STREAM
            )
            for peer in (broker_parent, broker_child, model_parent, model_child):
                peer.settimeout(timeout_seconds)
            stdin_read, stdin_write = os.pipe()
            stdout_read, stdout_write = os.pipe()
            stderr_read, stderr_write = os.pipe()
            recorder = WireRecorder()
            peer_errors: list[str] = []
            stdout = bytearray()
            stderr = bytearray()
            container_id = f"fg-nl2sql-conformance-{os.getpid()}"
            argv = build_runc_argv(bundle=bundle, container_id=container_id)
            pid = _fork_runc(
                argv=argv,
                broker_child=broker_child,
                model_child=model_child,
                stdin_read=stdin_read,
                stdout_write=stdout_write,
                stderr_write=stderr_write,
            )
            broker_child.close()
            model_child.close()
            os.close(stdin_read)
            os.close(stdout_write)
            os.close(stderr_write)
            # Fork before creating any Python threads.  This avoids inheriting
            # partially-held interpreter locks into the runc launcher child.
            threads = _peer_services(
                broker_parent, model_parent, recorder, peer_errors
            )
            output_threads = [
                threading.Thread(
                    target=_reader, args=(stdout_read, stdout), daemon=True
                ),
                threading.Thread(
                    target=_reader, args=(stderr_read, stderr), daemon=True
                ),
            ]
            for thread in output_threads:
                thread.start()
            runtime_exception: BaseException | None = None
            returncode = 127
            try:
                try:
                    os.write(stdin_write, episode_frame)
                finally:
                    os.close(stdin_write)
                returncode = _wait_pid(pid, timeout_seconds)
            except BaseException as exc:
                runtime_exception = exc
                try:
                    os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                try:
                    os.waitpid(pid, 0)
                except ChildProcessError:
                    pass
            finally:
                try:
                    os.close(stdin_write)
                except OSError:
                    pass
                cleanup_status = _runc_cleanup_status(container_id)
                for peer in (broker_parent, model_parent):
                    try:
                        peer.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                    peer.close()
                for thread in threads + output_threads:
                    thread.join(timeout=5)
                    if thread.is_alive():
                        peer_errors.append(f"{thread.name}:did_not_finish")
            if runtime_exception is not None:
                if cleanup_status.get("passed") is not True:
                    raise ConformanceError(
                        f"{runtime_exception}; runtime cleanup also failed: "
                        f"{cleanup_status.get('reason')}"
                    ) from runtime_exception
                raise runtime_exception

            stdout_bytes = bytes(stdout)
            stderr_bytes = bytes(stderr)
            events = recorder.snapshot()
            probe, probe_errors = parse_probe(stderr_bytes)
            peer_errors.extend(probe_errors)
            child_receipt = _parse_child_receipt(stdout_bytes)
            visible_channels: dict[str, bytes] = {
                "episode_dto": episode.canonical_bytes(),
                "episode_stdin": episode_frame,
                "oci_config": config_bytes,
                "process_args": "\0".join(config["process"]["args"]).encode(),
                "process_environment": "\0".join(
                    config["process"]["env"]
                ).encode(),
                "stdout": stdout_bytes,
                "stderr": stderr_bytes,
            }
            for relative, digest in staged_hashes.items():
                del digest
                visible_channels[f"staged:{relative}"] = (
                    bundle / "rootfs" / "opt" / "frankengate" / relative
                ).read_bytes()
            for event in events:
                visible_channels[
                    f"wire:{event.sequence}:{event.channel}:{event.direction}"
                ] = event.data
            canary_findings = scan_canaries(canaries, visible_channels)
            decision = classify_enforcement(
                returncode=returncode,
                probe=probe,
                child_receipt=child_receipt,
                peer_errors=peer_errors,
                canary_findings=canary_findings,
                profile_variant=profile_variant,
                cleanup_status=cleanup_status,
            )
            runtime_findings = classify_runtime_stderr(stderr_bytes)

            raw = {
                "schema_version": RAW_SCHEMA_VERSION,
                "started_unix_ms": int(started * 1000),
                "completed_unix_ms": int(time.time() * 1000),
                "platform": {
                    "uname": list(platform.uname()),
                    "uid": os.getuid(),
                    "gid": os.getgid(),
                },
                "runtime": {
                    "runc_version": runc_version,
                    "image_reference": IMAGE_REFERENCE,
                    "image_inspect": image,
                    "profile_variant": profile_variant,
                    "runtime_failure_classifications": runtime_findings,
                },
                "bundle": {
                    "config": config,
                    "config_sha256": _sha256(config_bytes),
                    "staged_file_sha256": staged_hashes,
                },
                "episode_stdin_b64": base64.b64encode(episode_frame).decode(),
                "episode_stdin_sha256": _sha256(episode_frame),
                "process": {
                    "argv": list(argv),
                    "returncode": returncode,
                    "stdout_b64": base64.b64encode(stdout_bytes).decode(),
                    "stderr_b64": base64.b64encode(stderr_bytes).decode(),
                    "stdout_sha256": _sha256(stdout_bytes),
                    "stderr_sha256": _sha256(stderr_bytes),
                },
                "wire_events": _raw_wire(events),
                "probe": probe,
                "probe_errors": probe_errors,
                "child_receipt": child_receipt,
                "peer_errors": peer_errors,
                "cleanup_status": cleanup_status,
                "canaries": {
                    name: {"sha256": _sha256(value)}
                    for name, value in sorted(canaries.items())
                },
                "canary_findings": canary_findings,
                "decision": decision,
            }
            raw_bytes = _json_bytes(raw)
            aggregate_decision = minimize_decision(decision)
            aggregate = {
                "schema_version": AGGREGATE_SCHEMA_VERSION,
                "runtime": {
                    "kernel": platform.release(),
                    "machine": platform.machine(),
                    "runc_version_sha256": _sha256(runc_version.encode()),
                    "image_digest": IMAGE_DIGEST,
                    "profile_variant": profile_variant,
                    "runtime_failure_classifications": runtime_findings,
                },
                "evidence": {
                    "raw_sha256": _sha256(raw_bytes),
                    "config_sha256": _sha256(config_bytes),
                    "episode_stdin_sha256": _sha256(episode_frame),
                    "stdout_sha256": _sha256(stdout_bytes),
                    "stderr_sha256": _sha256(stderr_bytes),
                    "wire_event_count": len(events),
                    "wire_byte_count": sum(len(event.data) for event in events),
                    "staged_file_count": len(staged_hashes),
                    "canary_count": len(canaries),
                    "canary_finding_count": len(canary_findings),
                },
                "decision": aggregate_decision,
                "limitations": [
                    "one Colima Linux kernel and runc version were tested",
                    "the peer services are deterministic emulators, not production services",
                    "this proves boundary enforcement, not SQL correctness or model quality",
                    "raw evidence is mutable local evidence, not a signed WORM attestation",
                    "the pinned Python image is a general rootfs with other executables, not a minimal solver image",
                    "execve is permitted for startup and is not independently blocked after startup",
                ],
            }
            _exclusive_private_write(raw_output, raw_bytes)
            _atomic_json(aggregate_output, aggregate)
            return aggregate
    finally:
        for name in cleanup_containers:
            result = subprocess.run(
                ("docker", "rm", "-f", name),
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if result.returncode != 0:
                cleanup_errors.append(f"container:{name}:{result.returncode}")
        if cleanup_errors:
            sys.stderr.write(
                json.dumps(
                    {"cleanup_errors": cleanup_errors},
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            )


def _arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-output", type=Path, required=True)
    parser.add_argument("--aggregate-output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument(
        "--diagnostic-extra-syscall",
        action="append",
        default=[],
        help=(
            "add a syscall only to a diagnostic non-release variant; any such "
            "run is forced nonconformant even if its kernel probes succeed"
        ),
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _arguments(argv)
    try:
        aggregate = run_conformance(
            raw_output=args.raw_output,
            aggregate_output=args.aggregate_output,
            timeout_seconds=args.timeout_seconds,
            diagnostic_extra_syscalls=args.diagnostic_extra_syscall,
        )
    except ConformanceError as exc:
        sys.stderr.write(f"conformance runner failed: {exc}\n")
        return 2
    print(json.dumps(aggregate, sort_keys=True, separators=(",", ":")))
    return 0 if aggregate["decision"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
