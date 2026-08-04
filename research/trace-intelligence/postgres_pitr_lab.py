#!/usr/bin/env python3
"""Run a disposable PostgreSQL WAL/PITR checkpoint through Colima.

The receipt is intentionally scoped to PostgreSQL archive/recovery mechanics.
It does not claim Aurora/RDS managed-backup semantics.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any


IMAGE = "postgres:16-alpine"
PASSWORD = "postgres_pw"
REPLICATION_PASSWORD = "replication_pw"


def docker(*args: str, check: bool = True, timeout: int = 60) -> str:
    completed = subprocess.run(
        ["colima", "ssh", "--", "docker", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if check and completed.returncode != 0:
        raise RuntimeError(
            f"docker {' '.join(args)} failed ({completed.returncode}): "
            f"{completed.stderr.strip() or completed.stdout.strip()}"
        )
    return completed.stdout.strip()


def exec_command(name: str, *args: str, check: bool = True) -> str:
    return docker("exec", name, *args, check=check)


def exec_as(name: str, user: str, *args: str, check: bool = True) -> str:
    return docker("exec", "-u", user, name, *args, check=check)


def sql(name: str, statement: str) -> str:
    return docker(
        "exec", name, "psql", "-U", "postgres", "-d", "fg",
        "-v", "ON_ERROR_STOP=1", "-Atc", statement,
    )


def wait_ready(name: str, attempts: int = 60) -> None:
    for _ in range(attempts):
        output = exec_command(name, "pg_isready", "-U", "postgres", "-d", "fg", check=False)
        if "accepting connections" in output:
            return
        time.sleep(1)
    raise RuntimeError(f"{name} did not become ready")


def archive_file_count(name: str) -> int:
    output = exec_command(
        name, "sh", "-c", "find /var/lib/postgresql/archive -type f -maxdepth 1 | wc -l",
        check=False,
    )
    try:
        return int(output.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    run_id = f"fg-pitr-lab-{uuid.uuid4().hex[:10]}"
    network = f"{run_id}-net"
    primary = f"{run_id}-primary"
    restore = f"{run_id}-restore"
    primary_volume = f"{run_id}-primary-data"
    restore_volume = f"{run_id}-restore-data"
    archive_volume = f"{run_id}-archive"
    containers = [primary, restore]
    volumes = [primary_volume, restore_volume, archive_volume]

    result: dict[str, Any] = {
        "schema_version": "frankengate-local-postgres-pitr-lab-v1",
        "image": IMAGE,
        "run_id": run_id,
        "claim_boundary": {
            "local_postgresql_pitr_mechanics_proven": False,
            "managed_aurora_pitr_proven": False,
            "rds_managed_backup_semantics_proven": False,
        },
        "pitr": {"executed": False},
    }

    try:
        docker("network", "create", network)
        for volume in volumes:
            docker("volume", "create", volume)
        docker(
            "run", "--rm", "--user", "root", "--entrypoint", "sh", "-v",
            f"{archive_volume}:/var/lib/postgresql/archive", IMAGE, "-lc",
            "mkdir -p /var/lib/postgresql/archive && chown postgres:postgres /var/lib/postgresql/archive",
        )
        docker(
            "run", "-d", "--name", primary, "--network", network,
            "-e", f"POSTGRES_PASSWORD={PASSWORD}", "-e", "POSTGRES_DB=fg",
            "-v", f"{primary_volume}:/var/lib/postgresql/data",
            "-v", f"{archive_volume}:/var/lib/postgresql/archive", IMAGE,
            "postgres", "-c", "wal_level=replica", "-c", "max_wal_senders=3",
            "-c", "listen_addresses=*", "-c", "archive_mode=on",
            "-c", "archive_timeout=1s",
            "-c", "archive_command=test ! -f /var/lib/postgresql/archive/%f && cp %p /var/lib/postgresql/archive/%f",
        )
        wait_ready(primary)
        sql(primary, f"CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD '{REPLICATION_PASSWORD}';")
        exec_command(
            primary, "sh", "-c",
            "echo 'host replication replicator 0.0.0.0/0 scram-sha-256' >> /var/lib/postgresql/data/pg_hba.conf",
        )
        exec_as(primary, "postgres", "pg_ctl", "reload", "-D", "/var/lib/postgresql/data")
        sql(primary, "CREATE TABLE pitr_probe (id bigserial PRIMARY KEY, body text NOT NULL); INSERT INTO pitr_probe(body) VALUES ('baseline');")

        docker(
            "run", "--rm", "--name", f"{run_id}-basebackup", "--network", network,
            "--user", "postgres", "--entrypoint", "sh", "-v",
            f"{restore_volume}:/var/lib/postgresql/data", IMAGE, "-lc",
            "find /var/lib/postgresql/data -mindepth 1 -delete && "
            f"PGPASSWORD={REPLICATION_PASSWORD} pg_basebackup -h {primary} -U replicator "
            "-D /var/lib/postgresql/data -Fp -Xs -P -R",
            timeout=120,
        )
        restore_point = f"fg_before_pitr_{run_id.replace('-', '_')}"
        sql(primary, f"SELECT pg_create_restore_point('{restore_point}'); SELECT pg_switch_wal();")
        after_marker = f"after-{run_id}"
        sql(primary, f"INSERT INTO pitr_probe(body) VALUES ('{after_marker}'); SELECT pg_switch_wal();")
        archive_seen = 0
        for _ in range(20):
            archive_seen = archive_file_count(primary)
            if archive_seen > 0:
                break
            time.sleep(1)
        result["pitr"]["archive_files_seen"] = archive_seen

        # The base backup carries standby.signal; remove it before opening the
        # backup as a PITR target. The restore command reads the primary's
        # archived WAL files from the shared disposable archive volume.
        docker(
            "run", "--rm", "--user", "postgres", "--entrypoint", "sh", "-v",
            f"{restore_volume}:/var/lib/postgresql/data", IMAGE, "-lc",
            "rm -f /var/lib/postgresql/data/standby.signal /var/lib/postgresql/data/postgresql.auto.conf",
        )
        docker(
            "run", "-d", "--name", restore, "--network", network,
            "-v", f"{restore_volume}:/var/lib/postgresql/data",
            "-v", f"{archive_volume}:/var/lib/postgresql/archive", IMAGE,
            "postgres", "-c", "listen_addresses=*",
            "-c", "restore_command=cp /var/lib/postgresql/archive/%f %p",
            "-c", f"recovery_target_name={restore_point}",
            "-c", "recovery_target_action=promote",
        )
        wait_ready(restore)
        after_count = sql(restore, f"SELECT count(*) FROM pitr_probe WHERE body = '{after_marker}';")
        recovery_state = sql(restore, "SELECT pg_is_in_recovery();")
        result["pitr"].update({
            "executed": True,
            "restore_point": restore_point,
            "after_marker": after_marker,
            "after_marker_rows_at_target": int(after_count),
            "recovery_state_after_target": recovery_state,
            "target_excluded_after_marker": after_count == "0",
        })
        result["claim_boundary"]["local_postgresql_pitr_mechanics_proven"] = (
            archive_seen > 0 and recovery_state == "f" and after_count == "0"
        )
    except (OSError, subprocess.SubprocessError, RuntimeError, ValueError) as exc:
        result["error"] = {"class": type(exc).__name__, "message": str(exc)}
    finally:
        for name in containers:
            docker("rm", "-f", name, check=False)
        for volume in volumes:
            docker("volume", "rm", volume, check=False)
        docker("network", "rm", network, check=False)

    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok" if "error" not in result else "error", "local_postgresql_pitr_mechanics_proven": result["claim_boundary"]["local_postgresql_pitr_mechanics_proven"]}, sort_keys=True))
    return 0 if "error" not in result else 1


if __name__ == "__main__":
    raise SystemExit(main())
