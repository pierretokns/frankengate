"""Fail-closed shell boundary for model-driven replay experiments.

The upstream Trace2Skill spreadsheet agent exposes ``subprocess.run(...,
shell=True)`` directly on the host.  This module keeps the benchmark agent and
evaluator reusable while replacing that boundary with a content-audited,
networkless macOS sandbox.  It is research infrastructure, not a production
Frankengate execution service.

Raw commands and tool outputs are written only to an explicitly supplied
external audit path.  Committed experiment results should contain aggregates
and content hashes, never this audit log.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import subprocess
import tempfile
import time
from typing import Callable, Iterable


DEFAULT_RUNTIME_READ_ROOTS = (
    Path("/System"),
    Path("/usr"),
    Path("/bin"),
    Path("/sbin"),
    Path("/Library"),
    Path("/opt/homebrew"),
    Path("/dev"),
    Path("/private/var/db/timezone"),
    Path("/private/etc/apache2/mime.types"),
)

SAFE_ENV_KEYS = ("LANG", "LC_ALL", "LC_CTYPE", "TZ")


class SandboxUnavailable(RuntimeError):
    """Raised when the required fail-closed execution boundary is unavailable."""


def _sandbox_literal(path: Path) -> str:
    return str(path).replace("\\", "\\\\").replace('"', '\\"')


@dataclass(frozen=True)
class SandboxPolicy:
    working_dir: Path
    readable_roots: tuple[Path, ...] = ()
    runtime_read_roots: tuple[Path, ...] = DEFAULT_RUNTIME_READ_ROOTS
    timeout_seconds: int = 120
    cpu_seconds: int = 60
    max_output_bytes: int = 1_000_000
    max_file_bytes: int = 64 * 1024 * 1024
    max_open_files: int = 128

    def normalized(self) -> "SandboxPolicy":
        work = self.working_dir.resolve(strict=True)
        if not work.is_dir():
            raise ValueError(f"working_dir must be a directory: {work}")
        if self.timeout_seconds <= 0 or self.cpu_seconds <= 0:
            raise ValueError("timeout and CPU limits must be positive")
        if self.max_output_bytes <= 0 or self.max_file_bytes <= 0:
            raise ValueError("byte limits must be positive")
        return SandboxPolicy(
            working_dir=work,
            readable_roots=tuple(path.resolve(strict=True) for path in self.readable_roots),
            runtime_read_roots=tuple(
                path.resolve(strict=False)
                for path in self.runtime_read_roots
                if path.exists()
            ),
            timeout_seconds=self.timeout_seconds,
            cpu_seconds=self.cpu_seconds,
            max_output_bytes=self.max_output_bytes,
            max_file_bytes=self.max_file_bytes,
            max_open_files=self.max_open_files,
        )


@dataclass(frozen=True)
class ToolExecution:
    command: str
    command_sha256: str
    exit_code: int | None
    timed_out: bool
    sandbox_violation: bool
    network_denied: bool
    elapsed_ms: float
    stdout: str
    stderr: str
    stdout_truncated: bool
    stderr_truncated: bool


def build_macos_profile(policy: SandboxPolicy) -> str:
    """Build a deny-by-default Seatbelt profile.

    Model-generated commands may read the task directory, declared skill/runtime
    roots, and operating-system/runtime files.  Only the task directory is
    writable.  All network operations are denied.
    """

    normalized = policy.normalized()
    readable = (
        (normalized.working_dir,)
        + normalized.readable_roots
        + normalized.runtime_read_roots
    )
    read_rules = "\n".join(
        f'  (subpath "{_sandbox_literal(path)}")' for path in readable
    )
    work = _sandbox_literal(normalized.working_dir)
    return f"""(version 1)
(deny default)
(import "system.sb")
(allow process*)
(allow signal (target self))
(allow sysctl-read)
(allow mach-lookup)
(allow file-read-metadata)
(allow file-read*
{read_rules})
(allow file-write*
  (subpath "{work}"))
(deny network*)
"""


def _limit_resources(policy: SandboxPolicy) -> Callable[[], None]:
    def apply() -> None:
        os.setsid()
        resource.setrlimit(
            resource.RLIMIT_CPU, (policy.cpu_seconds, policy.cpu_seconds)
        )
        resource.setrlimit(
            resource.RLIMIT_FSIZE, (policy.max_file_bytes, policy.max_file_bytes)
        )
        resource.setrlimit(
            resource.RLIMIT_NOFILE, (policy.max_open_files, policy.max_open_files)
        )

    return apply


def _read_limited(path: Path, limit: int) -> tuple[str, bool]:
    with path.open("rb") as handle:
        value = handle.read(limit + 1)
    truncated = len(value) > limit
    return value[:limit].decode("utf-8", errors="replace"), truncated


def is_sandbox_violation(stderr: str) -> bool:
    markers = (
        "Operation not permitted",
        "Permission denied",
        "deny(",
        "sandbox restriction",
        "file system sandbox blocked open()",
    )
    return any(marker in stderr for marker in markers)


def is_network_denial(output: str) -> bool:
    markers = (
        "Failed to establish a new connection",
        "nodename nor servname provided",
        "Network is unreachable",
        "network is denied",
    )
    return any(marker in output for marker in markers)


def _sanitized_environment(policy: SandboxPolicy, executable_dirs: Iterable[Path]) -> dict:
    env = {
        key: os.environ[key]
        for key in SAFE_ENV_KEYS
        if key in os.environ
    }
    path_entries = [str(path.resolve(strict=True)) for path in executable_dirs]
    path_entries.extend(("/opt/homebrew/bin", "/usr/bin", "/bin"))
    env.update(
        {
            "HOME": str(policy.working_dir),
            "TMPDIR": str(policy.working_dir),
            "PATH": os.pathsep.join(path_entries),
            "PYTHONNOUSERSITE": "1",
        }
    )
    return env


class SandboxedShell:
    def __init__(
        self,
        policy: SandboxPolicy,
        *,
        executable_dirs: Iterable[Path] = (),
        audit_path: Path | None = None,
    ) -> None:
        if platform.system() != "Darwin" or not Path("/usr/bin/sandbox-exec").exists():
            raise SandboxUnavailable(
                "model-driven shell replay requires macOS sandbox-exec"
            )
        self.policy = policy.normalized()
        self.profile = build_macos_profile(self.policy)
        self.executable_dirs = tuple(executable_dirs)
        self.audit_path = audit_path
        if audit_path is not None:
            audit_path.parent.mkdir(parents=True, exist_ok=True)

    def execute(self, command: str) -> ToolExecution:
        if not isinstance(command, str) or not command.strip():
            raise ValueError("command must be a non-empty string")

        started = time.monotonic()
        timed_out = False
        exit_code: int | None = None
        with tempfile.TemporaryDirectory(
            prefix=".sandbox-capture-", dir=self.policy.working_dir
        ) as capture_dir:
            capture_root = Path(capture_dir)
            stdout_path = capture_root / "stdout"
            stderr_path = capture_root / "stderr"
            with stdout_path.open("wb") as stdout_handle, stderr_path.open(
                "wb"
            ) as stderr_handle:
                process = subprocess.Popen(
                    [
                        "/usr/bin/sandbox-exec",
                        "-p",
                        self.profile,
                        "/bin/sh",
                        "-c",
                        command,
                    ],
                    cwd=self.policy.working_dir,
                    env=_sanitized_environment(self.policy, self.executable_dirs),
                    stdin=subprocess.DEVNULL,
                    stdout=stdout_handle,
                    stderr=stderr_handle,
                    preexec_fn=_limit_resources(self.policy),
                )
                try:
                    exit_code = process.wait(timeout=self.policy.timeout_seconds)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    try:
                        os.killpg(process.pid, 9)
                    except ProcessLookupError:
                        pass
                    process.wait()

            stdout, stdout_truncated = _read_limited(
                stdout_path, self.policy.max_output_bytes
            )
            stderr, stderr_truncated = _read_limited(
                stderr_path, self.policy.max_output_bytes
            )

        sandbox_violation = is_sandbox_violation(stderr)
        result = ToolExecution(
            command=command,
            command_sha256=hashlib.sha256(command.encode("utf-8")).hexdigest(),
            exit_code=exit_code,
            timed_out=timed_out,
            sandbox_violation=sandbox_violation,
            network_denied=is_network_denial(stdout + "\n" + stderr),
            elapsed_ms=round((time.monotonic() - started) * 1000, 3),
            stdout=stdout,
            stderr=stderr,
            stdout_truncated=stdout_truncated,
            stderr_truncated=stderr_truncated,
        )
        self._audit(result)
        return result

    def _audit(self, result: ToolExecution) -> None:
        if self.audit_path is None:
            return
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(result), sort_keys=True) + "\n")


def render_tool_observation(result: ToolExecution) -> str:
    sections = []
    if result.stdout:
        sections.append(result.stdout)
    if result.stderr:
        sections.append(
            f"[STDERR]\n{result.stderr}" if sections else result.stderr
        )
    if result.timed_out:
        sections.append("[ERROR] Command timed out inside governed sandbox")
    elif result.exit_code:
        sections.append(f"[Exit code: {result.exit_code}]")
    if result.sandbox_violation:
        sections.append("[SANDBOX_VIOLATION] Access was denied and recorded")
    if result.network_denied:
        sections.append("[NETWORK_DENIED] Network access was denied and recorded")
    if result.stdout_truncated or result.stderr_truncated:
        sections.append("[OUTPUT_TRUNCATED] Governed output limit reached")
    return "\n".join(section.rstrip() for section in sections if section).strip() or (
        "[Command completed with no output]"
    )


def create_trace2skill_bash_tool(
    working_dir: str,
    *,
    readable_roots: Iterable[str] = (),
    executable_dirs: Iterable[str] = (),
    audit_path: str | None = None,
    timeout: int = 120,
):
    """Return a Trace2Skill-compatible Tool backed by :class:`SandboxedShell`.

    ``react_agent`` is imported lazily from the pinned upstream checkout so the
    core sandbox and its tests stay dependency-free.
    """

    from react_agent import tool

    executable_paths = tuple(Path(path) for path in executable_dirs)
    declared_read_roots = tuple(Path(path) for path in readable_roots)
    # A disposable virtual environment keeps Python dependencies outside the
    # task directory. Its bin/ parent must be readable, but remains read-only.
    runtime_roots = tuple(path.parent for path in executable_paths)
    shell = SandboxedShell(
        SandboxPolicy(
            working_dir=Path(working_dir),
            readable_roots=declared_read_roots + runtime_roots,
            timeout_seconds=timeout,
        ),
        executable_dirs=executable_paths,
        audit_path=Path(audit_path) if audit_path else None,
    )

    @tool(name="bash")
    def bash(command: str) -> str:
        """Execute a command in the governed, networkless task sandbox.

        Args:
            command: Shell command whose reads and writes must stay within the
                declared task and skill roots.
        """

        return render_tool_observation(shell.execute(command))

    return bash
