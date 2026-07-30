"""Production OCI configuration and launcher contract for one solver episode.

The functions here construct and validate an OCI Runtime Specification config;
they do not invoke a runtime.  Unit tests on macOS prove the configuration
shape only.  A Linux runtime conformance run must separately prove that the
kernel actually enforces the network namespace, read-only root, capabilities,
no-new-privileges, seccomp filter, tmpfs mounts, and inherited-FD contract.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
from typing import Any, Mapping, Sequence


BROKER_FD = 3
MODEL_FD = 4
PRESERVED_FD_COUNT = 2
LOCAL_TESTS_PROVE_LINUX_ENFORCEMENT = False

_CONTAINER_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.+-]{0,127}$")

_SAFE_ENVIRONMENT = (
    "HOME=/home",
    "TMPDIR=/tmp",
    "XDG_CACHE_HOME=/home/.cache",
    "XDG_CONFIG_HOME=/home/.config",
    "XDG_DATA_HOME=/home/.local/share",
    "PYTHONDONTWRITEBYTECODE=1",
    "PYTHONNOUSERSITE=1",
    "LANG=C.UTF-8",
    "LC_ALL=C.UTF-8",
    f"FG_SOLVER_BROKER_FD={BROKER_FD}",
    f"FG_SOLVER_MODEL_FD={MODEL_FD}",
    "FG_SOLVER_WORK_ROOT=/work",
)

_EXPECTED_RLIMITS = (
    ("RLIMIT_NOFILE", 64, 64),
    ("RLIMIT_CORE", 0, 0),
)

_EXPECTED_RESOURCES = {
    "pids": {"limit": 16},
    "memory": {"limit": 536_870_912, "swap": 536_870_912},
    "cpu": {"shares": 128, "quota": 100_000, "period": 100_000},
}

# There is deliberately no socket/connect/accept/listen, clone/fork, mount,
# ptrace, keyring, bpf, perf, module, or namespace-creation entry.
# ``execve`` is required for the OCI runtime's initial process transition and
# therefore cannot, by itself, prevent later exec of a read-only-rootfs binary.
# sendto/recvfrom operate on the two already-inherited Unix stream sockets.
_ALLOWED_SYSCALLS = (
    "access",
    "arch_prctl",
    "brk",
    "clock_gettime",
    "close",
    "close_range",
    "dup",
    "dup2",
    "dup3",
    "epoll_create1",
    "epoll_ctl",
    "epoll_pwait",
    "epoll_wait",
    "execve",
    "exit",
    "exit_group",
    "faccessat",
    "faccessat2",
    "fcntl",
    "fstat",
    "fstatfs",
    "fsync",
    "futex",
    "getcwd",
    "getdents64",
    "geteuid",
    "getegid",
    "getgid",
    "getpeername",
    "getpid",
    "getrandom",
    "getsockname",
    "getsockopt",
    "gettid",
    "getuid",
    "ioctl",
    "lseek",
    "madvise",
    "mmap",
    "mprotect",
    "mremap",
    "munmap",
    "nanosleep",
    "newfstatat",
    "open",
    "openat",
    "pipe2",
    "poll",
    "ppoll",
    "prctl",
    "pread64",
    "prlimit64",
    "pselect6",
    "read",
    "readlink",
    "readlinkat",
    "recvfrom",
    "recvmsg",
    "restart_syscall",
    "rseq",
    "rt_sigaction",
    "rt_sigprocmask",
    "rt_sigreturn",
    "sched_getaffinity",
    "sched_yield",
    "select",
    "sendmsg",
    "sendto",
    "set_robust_list",
    "set_tid_address",
    "shutdown",
    "sigaltstack",
    "stat",
    "statx",
    "sysinfo",
    "uname",
    "write",
    "writev",
)

_FORBIDDEN_ALLOWED_SYSCALLS = frozenset(
    {
        "accept",
        "accept4",
        "bind",
        "bpf",
        "clone",
        "clone3",
        "connect",
        "execveat",
        "fork",
        "keyctl",
        "listen",
        "mount",
        "open_by_handle_at",
        "perf_event_open",
        "pivot_root",
        "ptrace",
        "reboot",
        "setns",
        "socket",
        "socketpair",
        "swapon",
        "umount",
        "umount2",
        "unshare",
        "vfork",
    }
)


class OCIProfileError(ValueError):
    """The generated or supplied solver profile weakens an invariant."""


def build_solver_oci_config(*, command: Sequence[str]) -> dict[str, Any]:
    """Build a default-deny OCI config for one non-root solver process."""

    if (
        isinstance(command, (str, bytes))
        or not command
        or any(type(argument) is not str or not argument for argument in command)
    ):
        raise OCIProfileError("command must be a non-empty string sequence")
    config: dict[str, Any] = {
        "ociVersion": "1.1.0",
        "process": {
            "terminal": False,
            "user": {"uid": 65532, "gid": 65532},
            "args": list(command),
            "env": list(_SAFE_ENVIRONMENT),
            "cwd": "/work",
            "noNewPrivileges": True,
            "capabilities": {
                "bounding": [],
                "effective": [],
                "inheritable": [],
                "permitted": [],
                "ambient": [],
            },
            "rlimits": [
                {"type": name, "hard": hard, "soft": soft}
                for name, hard, soft in _EXPECTED_RLIMITS
            ],
        },
        "root": {"path": "rootfs", "readonly": True},
        "hostname": "frankengate-solver",
        "mounts": [
            {
                "destination": "/proc",
                "type": "proc",
                "source": "proc",
                "options": ["nosuid", "noexec", "nodev", "ro"],
            },
            {
                "destination": "/home",
                "type": "tmpfs",
                "source": "tmpfs",
                "options": [
                    "nodev",
                    "nosuid",
                    "noexec",
                    "mode=0700",
                    "uid=65532",
                    "gid=65532",
                    "size=16m",
                ],
            },
            {
                "destination": "/tmp",
                "type": "tmpfs",
                "source": "tmpfs",
                "options": [
                    "nodev",
                    "nosuid",
                    "noexec",
                    "mode=0700",
                    "uid=65532",
                    "gid=65532",
                    "size=64m",
                ],
            },
            {
                "destination": "/work",
                "type": "tmpfs",
                "source": "tmpfs",
                "options": [
                    "nodev",
                    "nosuid",
                    "noexec",
                    "mode=0700",
                    "uid=65532",
                    "gid=65532",
                    "size=64m",
                ],
            },
        ],
        "linux": {
            "namespaces": [
                {"type": "pid"},
                {"type": "mount"},
                {"type": "ipc"},
                {"type": "uts"},
                # A fresh network namespace with no configured interfaces is
                # the OCI equivalent of network=none.
                {"type": "network"},
            ],
            "resources": deepcopy(_EXPECTED_RESOURCES),
            "maskedPaths": [
                "/proc/acpi",
                "/proc/asound",
                "/proc/interrupts",
                "/proc/kcore",
                "/proc/keys",
                "/proc/latency_stats",
                "/proc/sched_debug",
                "/proc/scsi",
                "/proc/timer_list",
                "/proc/timer_stats",
                "/sys/firmware",
                "/sys/fs/selinux",
            ],
            "readonlyPaths": [
                "/proc/bus",
                "/proc/fs",
                "/proc/irq",
                "/proc/sys",
                "/proc/sysrq-trigger",
            ],
            "seccomp": {
                "defaultAction": "SCMP_ACT_ERRNO",
                "defaultErrnoRet": 1,
                "syscalls": [
                    {
                        "names": list(_ALLOWED_SYSCALLS),
                        "action": "SCMP_ACT_ALLOW",
                    }
                ],
            },
        },
        "annotations": {
            "frankengate.local/profile": "fg-one-episode-solver-oci-v1",
            "frankengate.local/network": "none",
            "frankengate.local/broker-fd": str(BROKER_FD),
            "frankengate.local/model-fd": str(MODEL_FD),
            "frankengate.local/preserve-fds": str(PRESERVED_FD_COUNT),
            "frankengate.local/fd-order": "broker,model",
            "frankengate.local/enforcement-verification": (
                "required-on-linux"
            ),
            "frankengate.local/local-unit-tests-prove-enforcement": "false",
        },
    }
    validate_solver_oci_config(config)
    return deepcopy(config)


def _environment_map(values: object) -> dict[str, str]:
    if not isinstance(values, list):
        raise OCIProfileError("process.env must be an array")
    result: dict[str, str] = {}
    for value in values:
        if type(value) is not str or "=" not in value:
            raise OCIProfileError("process.env entry is invalid")
        name, item = value.split("=", 1)
        if not name or name in result:
            raise OCIProfileError("process.env has duplicate/empty name")
        result[name] = item
    return result


def validate_solver_oci_config(config: Mapping[str, Any]) -> None:
    """Fail closed if any required production enforcement is absent."""

    try:
        root = config["root"]
        process = config["process"]
        linux = config["linux"]
        annotations = config["annotations"]
        mounts = config["mounts"]
    except (KeyError, TypeError) as exc:
        raise OCIProfileError("OCI profile is incomplete") from exc
    if (
        not isinstance(root, Mapping)
        or root.get("path") != "rootfs"
        or root.get("readonly") is not True
    ):
        raise OCIProfileError("rootfs must be the read-only bundle rootfs")
    if not isinstance(process, Mapping):
        raise OCIProfileError("process profile is invalid")
    if process.get("terminal") is not False:
        raise OCIProfileError("solver must not receive a terminal")
    if process.get("noNewPrivileges") is not True:
        raise OCIProfileError("no-new-privileges is required")
    if process.get("cwd") != "/work":
        raise OCIProfileError("solver cwd must be the empty /work tmpfs")
    user = process.get("user")
    if not isinstance(user, Mapping) or user.get("uid") != 65532 or user.get(
        "gid"
    ) != 65532:
        raise OCIProfileError("solver must run as the fixed non-root user")
    args = process.get("args")
    if (
        not isinstance(args, list)
        or not args
        or any(type(argument) is not str or not argument for argument in args)
    ):
        raise OCIProfileError("solver command is invalid")
    capabilities = process.get("capabilities")
    if not isinstance(capabilities, Mapping):
        raise OCIProfileError("capability sets are missing")
    for name in (
        "bounding",
        "effective",
        "inheritable",
        "permitted",
        "ambient",
    ):
        if capabilities.get(name) != []:
            raise OCIProfileError("all Linux capability sets must be empty")
    if _environment_map(process.get("env")) != _environment_map(
        list(_SAFE_ENVIRONMENT)
    ):
        raise OCIProfileError(
            "solver environment must equal the sanitized allowlist"
        )
    rlimits = process.get("rlimits")
    if not isinstance(rlimits, list):
        raise OCIProfileError("solver rlimits are missing")
    observed_rlimits = {
        (
            item.get("type"),
            item.get("hard"),
            item.get("soft"),
        )
        for item in rlimits
        if isinstance(item, Mapping)
    }
    if observed_rlimits != set(_EXPECTED_RLIMITS):
        raise OCIProfileError("solver rlimits differ from the frozen profile")

    if not isinstance(linux, Mapping):
        raise OCIProfileError("linux profile is missing")
    if linux.get("resources") != _EXPECTED_RESOURCES:
        raise OCIProfileError("solver cgroup resources differ from the profile")
    namespaces = linux.get("namespaces")
    if not isinstance(namespaces, list):
        raise OCIProfileError("Linux namespaces are missing")
    namespace_types = {
        item.get("type")
        for item in namespaces
        if isinstance(item, Mapping)
    }
    if not {"pid", "mount", "ipc", "uts", "network"}.issubset(
        namespace_types
    ):
        raise OCIProfileError("network and process namespaces are required")
    seccomp = linux.get("seccomp")
    if (
        not isinstance(seccomp, Mapping)
        or seccomp.get("defaultAction") != "SCMP_ACT_ERRNO"
        or seccomp.get("defaultErrnoRet") != 1
    ):
        raise OCIProfileError("default-deny seccomp is required")
    syscall_entries = seccomp.get("syscalls")
    if not isinstance(syscall_entries, list):
        raise OCIProfileError("seccomp syscall allowlist is missing")
    allowed = {
        name
        for entry in syscall_entries
        if isinstance(entry, Mapping)
        and entry.get("action") == "SCMP_ACT_ALLOW"
        for name in entry.get("names", [])
        if isinstance(name, str)
    }
    if _FORBIDDEN_ALLOWED_SYSCALLS.intersection(allowed):
        raise OCIProfileError(
            "seccomp allowlist includes process/network/privilege syscall"
        )
    if allowed != set(_ALLOWED_SYSCALLS):
        raise OCIProfileError("seccomp allowlist differs from the frozen set")

    if not isinstance(mounts, list):
        raise OCIProfileError("mount list is invalid")
    if any(
        not isinstance(mount, Mapping)
        or mount.get("type") not in {"proc", "tmpfs"}
        for mount in mounts
    ):
        raise OCIProfileError("host/bind/device mounts are forbidden")
    mount_destinations = {
        mount.get("destination") for mount in mounts
    }
    if mount_destinations != {"/proc", "/home", "/tmp", "/work"}:
        raise OCIProfileError("solver mount destinations differ")
    proc_mounts = [
        mount
        for mount in mounts
        if mount.get("destination") == "/proc"
    ]
    if (
        len(proc_mounts) != 1
        or proc_mounts[0].get("type") != "proc"
        or proc_mounts[0].get("source") != "proc"
        or not {"nosuid", "noexec", "nodev", "ro"}.issubset(
            proc_mounts[0].get("options", [])
        )
    ):
        raise OCIProfileError("/proc must be a hardened read-only proc mount")
    tmpfs = {
        mount.get("destination"): mount
        for mount in mounts
        if mount.get("type") == "tmpfs"
    }
    if set(tmpfs) != {"/home", "/tmp", "/work"}:
        raise OCIProfileError("empty home/tmp/work tmpfs mounts are required")
    for mount in tmpfs.values():
        options = mount.get("options")
        if not isinstance(options, list) or not {
            "nodev",
            "nosuid",
            "noexec",
            "mode=0700",
            "uid=65532",
            "gid=65532",
        }.issubset(options):
            raise OCIProfileError("tmpfs mount lacks hardening options")

    if (
        not isinstance(annotations, Mapping)
        or annotations.get("frankengate.local/profile")
        != "fg-one-episode-solver-oci-v1"
        or annotations.get("frankengate.local/network") != "none"
        or annotations.get("frankengate.local/broker-fd") != str(BROKER_FD)
        or annotations.get("frankengate.local/model-fd") != str(MODEL_FD)
        or annotations.get("frankengate.local/preserve-fds")
        != str(PRESERVED_FD_COUNT)
        or annotations.get("frankengate.local/fd-order") != "broker,model"
        or annotations.get(
            "frankengate.local/enforcement-verification"
        )
        != "required-on-linux"
        or annotations.get(
            "frankengate.local/local-unit-tests-prove-enforcement"
        )
        != "false"
    ):
        raise OCIProfileError("OCI FD/network/verification annotations differ")


def build_runc_argv(
    *,
    bundle: Path,
    container_id: str,
    runtime: str = "runc",
) -> tuple[str, ...]:
    """Return the non-shell runc invocation preserving exactly FDs 3 and 4."""

    bundle = Path(bundle)
    if not bundle.is_absolute():
        raise OCIProfileError("OCI bundle path must be absolute")
    if (
        type(container_id) is not str
        or _CONTAINER_ID_RE.fullmatch(container_id) is None
    ):
        raise OCIProfileError("container_id is invalid")
    if type(runtime) is not str or not runtime or any(
        character.isspace() for character in runtime
    ):
        raise OCIProfileError("runtime executable is invalid")
    return (
        runtime,
        "run",
        "--bundle",
        str(bundle),
        "--preserve-fds",
        str(PRESERVED_FD_COUNT),
        container_id,
    )


__all__ = [
    "BROKER_FD",
    "LOCAL_TESTS_PROVE_LINUX_ENFORCEMENT",
    "MODEL_FD",
    "OCIProfileError",
    "PRESERVED_FD_COUNT",
    "build_runc_argv",
    "build_solver_oci_config",
    "validate_solver_oci_config",
]
