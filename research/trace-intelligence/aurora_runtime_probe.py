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


def probe() -> dict[str, Any]:
    colima_code, _ = run_probe(["colima", "status"])
    docker_code, docker_error = run_probe(["docker", "ps"])
    psql_present = shutil.which("psql") is not None
    docker_cli_usable = docker_code == 0
    return {
        "schema_version": "frankengate-aurora-runtime-probe-v1",
        "colima_running": colima_code == 0,
        "container_cli_usable": docker_cli_usable,
        "container_cli_error_class": "none" if docker_cli_usable else "runtime_backend_unavailable",
        "psql_client_present": psql_present,
        "aurora_like_database_reachable": False,
        "failover_test_executed": False,
        "pitr_test_executed": False,
        "replica_lag_test_executed": False,
        "claim_boundary": {
            "managed_aurora_behavior_proven": False,
            "local_postgresql_mechanics_proven_elsewhere": True,
            "reason": "The local Colima VM reports running, but the Docker shim is not usable and no PostgreSQL fixture is reachable. No container or database state was mutated.",
        },
        "raw_runtime_error_emitted": bool(docker_error),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = probe()
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "container_cli_usable": result["container_cli_usable"], "aurora_like_database_reachable": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
