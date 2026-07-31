#!/usr/bin/env python3
"""Run a disposable PostgreSQL replication/RLS lab through Colima.

This is deliberately labelled as *local PostgreSQL mechanics*.  It is not a
claim about Amazon Aurora, RDS Proxy, or managed failover semantics.  The
lab exists to replace a runtime-only null with measured mechanics where the
local daemon can support them.
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
APP_PASSWORD = "app_pw"


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


def sql(name: str, statement: str, *, user: str = "postgres", password: str | None = None) -> str:
    args = ["exec"]
    if password:
        args.extend(["-e", f"PGPASSWORD={password}"])
    args.extend([name, "psql", "-U", user, "-d", "fg", "-v", "ON_ERROR_STOP=1", "-Atc", statement])
    return docker(*args)


def wait_ready(name: str, attempts: int = 45) -> None:
    for _ in range(attempts):
        result = exec_command(name, "pg_isready", "-U", "postgres", "-d", "fg", check=False)
        if "accepting connections" in result:
            return
        time.sleep(1)
    raise RuntimeError(f"{name} did not become ready")


def wait_sql(name: str, statement: str, expected: str, *, user: str = "postgres", password: str | None = None, attempts: int = 45) -> float:
    started = time.monotonic()
    for _ in range(attempts):
        try:
            if sql(name, statement, user=user, password=password).strip() == expected:
                return (time.monotonic() - started) * 1000
        except RuntimeError:
            pass
        time.sleep(0.2)
    raise RuntimeError(f"replica did not reach expected value {expected!r}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    run_id = f"fg-aurora-lab-{uuid.uuid4().hex[:10]}"
    network = f"{run_id}-net"
    primary = f"{run_id}-primary"
    replica = f"{run_id}-replica"
    primary_volume = f"{run_id}-primary-data"
    replica_volume = f"{run_id}-replica-data"
    created_containers = [primary, replica]
    created_volumes = [primary_volume, replica_volume]

    result: dict[str, Any] = {
        "schema_version": "frankengate-local-postgres-replication-lab-v1",
        "image": IMAGE,
        "claim_boundary": {
            "managed_aurora_behavior_proven": False,
            "local_postgresql_mechanics_proven": False,
            "rds_proxy_or_managed_pitr_proven": False,
        },
        "run_id": run_id,
        "replica_lag": {},
        "rls": {},
        "failover": {},
        "pitr": {"executed": False, "reason": "This first lab records replication and failover only."},
    }

    try:
        docker("network", "create", network)
        for volume in created_volumes:
            docker("volume", "create", volume)
        docker(
            "run", "-d", "--name", primary, "--network", network,
            "-e", f"POSTGRES_PASSWORD={PASSWORD}", "-e", "POSTGRES_DB=fg",
            "-v", f"{primary_volume}:/var/lib/postgresql/data", IMAGE,
            "postgres", "-c", "wal_level=replica", "-c", "max_wal_senders=5",
            "-c", "max_replication_slots=3", "-c", "listen_addresses=*",
        )
        wait_ready(primary)
        sql(primary, f"CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD '{REPLICATION_PASSWORD}';")
        sql(primary, f"CREATE ROLE app LOGIN PASSWORD '{APP_PASSWORD}';")
        sql(
            primary,
            """
            CREATE TABLE traces (
                id bigserial PRIMARY KEY,
                tenant_id text NOT NULL,
                body text NOT NULL
            );
            ALTER TABLE traces ENABLE ROW LEVEL SECURITY;
            CREATE POLICY traces_tenant ON traces
              USING (tenant_id = current_setting('app.tenant_id', true))
              WITH CHECK (tenant_id = current_setting('app.tenant_id', true));
            GRANT SELECT, INSERT ON traces TO app;
            GRANT USAGE, SELECT ON SEQUENCE traces_id_seq TO app;
            INSERT INTO traces (tenant_id, body) VALUES ('tenant-a', 'baseline-a'), ('tenant-b', 'baseline-b');
            """,
        )
        exec_command(
            primary,
            "sh", "-c",
            "echo 'host replication replicator 0.0.0.0/0 scram-sha-256' >> /var/lib/postgresql/data/pg_hba.conf",
        )
        exec_as(primary, "postgres", "pg_ctl", "reload", "-D", "/var/lib/postgresql/data")

        docker(
            "run", "--rm", "--name", f"{run_id}-basebackup", "--network", network,
            "--user", "postgres", "--entrypoint", "sh", "-v",
            f"{replica_volume}:/var/lib/postgresql/data", IMAGE, "-lc",
            "find /var/lib/postgresql/data -mindepth 1 -delete && "
            f"PGPASSWORD={REPLICATION_PASSWORD} pg_basebackup -h {primary} -U replicator "
            "-D /var/lib/postgresql/data -Fp -Xs -P -R",
            timeout=120,
        )
        docker(
            "run", "-d", "--name", replica, "--network", network,
            "-v", f"{replica_volume}:/var/lib/postgresql/data", IMAGE,
            "postgres", "-c", "hot_standby=on", "-c", "listen_addresses=*",
        )
        wait_ready(replica)
        result["replica_lag"]["in_recovery_initial"] = sql(replica, "SELECT pg_is_in_recovery();") == "t"

        marker = f"lag-marker-{run_id}"
        sql(primary, f"INSERT INTO traces (tenant_id, body) VALUES ('tenant-a', '{marker}'); SELECT pg_switch_wal();")
        propagation_ms = wait_sql(
            replica,
            f"SELECT count(*) FROM traces WHERE body = '{marker}';",
            "1",
        )
        result["replica_lag"].update({"marker": marker, "propagation_ms": round(propagation_ms, 3), "marker_visible": True})

        tenant_a_rows = sql(
            replica,
            "SET app.tenant_id='tenant-a'; SELECT count(*) FROM traces;",
            user="app", password=APP_PASSWORD,
        )
        tenant_b_rows = sql(
            replica,
            "SET app.tenant_id='tenant-b'; SELECT count(*) FROM traces;",
            user="app", password=APP_PASSWORD,
        )
        result["rls"] = {
            "tenant_a_visible_rows": int(tenant_a_rows.splitlines()[-1]),
            "tenant_b_visible_rows": int(tenant_b_rows.splitlines()[-1]),
            "cross_tenant_isolation_verified": False,
        }
        # The replica has two baseline rows plus the marker, but each tenant
        # should see only its own rows.  Keep the assertion explicit.
        result["rls"]["cross_tenant_isolation_verified"] = (
            result["rls"]["tenant_a_visible_rows"] == 2
            and result["rls"]["tenant_b_visible_rows"] == 1
        )

        docker("stop", primary)
        exec_as(replica, "postgres", "pg_ctl", "promote", "-D", "/var/lib/postgresql/data")
        promotion_ms = wait_sql(replica, "SELECT pg_is_in_recovery();", "f")
        promoted_marker = f"post-promote-{run_id}"
        sql(
            replica,
            f"SET app.tenant_id='tenant-a'; INSERT INTO traces (tenant_id, body) VALUES ('tenant-a', '{promoted_marker}');",
            user="app", password=APP_PASSWORD,
        )
        result["failover"] = {
            "primary_stopped": True,
            "replica_promoted": True,
            "promotion_ms": round(promotion_ms, 3),
            "post_promotion_write_verified": sql(replica, f"SELECT count(*) FROM traces WHERE body = '{promoted_marker}';") == "1",
        }
        result["claim_boundary"]["local_postgresql_mechanics_proven"] = all(
            [result["replica_lag"].get("marker_visible"), result["rls"].get("cross_tenant_isolation_verified"), result["failover"].get("post_promotion_write_verified")]
        )
    except (OSError, subprocess.SubprocessError, RuntimeError, ValueError) as exc:
        result["error"] = {"class": type(exc).__name__, "message": str(exc)}
    finally:
        for name in [replica, primary]:
            docker("rm", "-f", name, check=False)
        for volume in created_volumes:
            docker("volume", "rm", volume, check=False)
        docker("network", "rm", network, check=False)

    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok" if "error" not in result else "error", "local_postgresql_mechanics_proven": result["claim_boundary"]["local_postgresql_mechanics_proven"]}, sort_keys=True))
    return 0 if "error" not in result else 1


if __name__ == "__main__":
    raise SystemExit(main())
