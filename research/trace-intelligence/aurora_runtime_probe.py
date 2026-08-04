#!/usr/bin/env python3
"""Record whether the local container runtime can host the Aurora-like lab.

This probe is intentionally content-free and non-mutating.  A running Colima
VM is not treated as PostgreSQL/Aurora evidence unless the container CLI and
database fixture are actually reachable.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


def run_probe(command: list[str]) -> tuple[int, str]:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=15)
        return completed.returncode, completed.stderr.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, type(exc).__name__


def probe_container_cli() -> tuple[bool, str, str]:
    """Find an actually usable container path, including Colima's VM shell.

    On this machine the macOS ``docker`` shim reports a client/server version
    but its command path delegates to a missing ``podman`` binary.  A version
    check is therefore insufficient; ``ps`` is the capability probe.  Colima
    exposes the same daemon through ``colima ssh`` and is the safe fallback.
    """

    direct_code, direct_error = run_probe(["docker", "ps"])
    if direct_code == 0:
        return True, "docker", "none"

    vm_code, vm_error = run_probe(["colima", "ssh", "--", "docker", "ps"])
    if vm_code == 0:
        return True, "colima_ssh", "direct_shim_unusable"

    return False, "unavailable", direct_error or vm_error or "runtime_backend_unavailable"


def probe() -> dict[str, Any]:
    colima_code, _ = run_probe(["colima", "status"])
    container_cli_usable, container_cli_source, container_cli_error = probe_container_cli()
    psql_present = shutil.which("psql") is not None
    return {
        "schema_version": "frankengate-aurora-runtime-probe-v2",
        "colima_running": colima_code == 0,
        "container_cli_usable": container_cli_usable,
        "container_cli_source": container_cli_source,
        "container_cli_error_class": container_cli_error,
        "psql_client_present": psql_present,
        "aurora_like_database_reachable": False,
        "failover_test_executed": False,
        "pitr_test_executed": False,
        "replica_lag_test_executed": False,
        "claim_boundary": {
            "managed_aurora_behavior_proven": False,
            "local_postgresql_mechanics_proven_elsewhere": True,
            "reason": "A container command path is available through Colima's VM shell, but no Aurora-like database fixture was exercised. Managed Aurora behavior remains untested; the probe itself did not mutate container or database state.",
        },
        "raw_runtime_error_emitted": container_cli_source == "unavailable",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = probe()
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "container_cli_usable": result["container_cli_usable"], "container_cli_source": result["container_cli_source"], "aurora_like_database_reachable": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
