#!/usr/bin/env python3
"""Run the two-session race for the governed lifecycle procedures."""

from __future__ import annotations

import concurrent.futures
import hashlib
import pathlib
import select
import subprocess
import time


ROOT = pathlib.Path(__file__).resolve().parents[3]
SQL_PATH = ROOT / "research" / "trace-intelligence" / "sql" / "011_skill_release_atomic_lifecycle_race.sql"


class Lab:
    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout
        self.sql = SQL_PATH.read_text(encoding="utf-8")

    def prefix(self, interactive: bool = False) -> list[str]:
        command = ["kubectl", "exec"]
        if interactive:
            command.append("-i")
        return command + [
            "-n", "frankengate-test", "postgres-0", "--", "psql", "-X",
            "-U", "frankengate", "-d", "frankengate", "-Atq",
            "-v", "ON_ERROR_STOP=1",
        ]

    def query(self, sql: str) -> str:
        result = subprocess.run(
            self.prefix() + ["-c", sql], capture_output=True, text=True,
            timeout=self.timeout, check=False,
        )
        if result.returncode:
            raise RuntimeError(result.stderr.strip())
        return result.stdout.strip()

    def mode(self, mode: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            self.prefix(True) + ["-v", f"mode={mode}"], input=self.sql,
            capture_output=True, text=True, timeout=self.timeout, check=False,
        )

    def wait_for(self, application: str, event_type: str, event: str | None = None) -> None:
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            predicate = [
                "application_name = " + self.quote(application),
                "state = 'active'",
                "wait_event_type = " + self.quote(event_type),
            ]
            if event is not None:
                predicate.append("wait_event = " + self.quote(event))
            if self.query("select count(*) from pg_stat_activity where " + " and ".join(predicate)) == "1":
                return
            time.sleep(0.05)
        observed = self.query(
            "select application_name || '|' || state || '|' || "
            "coalesce(wait_event_type, '') || '|' || coalesce(wait_event, '') "
            "from pg_stat_activity where application_name like 'tc-atomicc-%'"
        )
        raise TimeoutError(
            f"{application} did not reach {event_type}/{event}; observed={observed!r}"
        )

    @staticmethod
    def quote(value: str) -> str:
        return "'" + value.replace("'", "''") + "'"


class AdvisoryBarrier:
    def __init__(self, lab: Lab, lock_id: int) -> None:
        self.lab = lab
        self.lock_id = lock_id
        self.process: subprocess.Popen[str] | None = None

    def __enter__(self) -> "AdvisoryBarrier":
        self.process = subprocess.Popen(
            self.lab.prefix(True), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1,
        )
        self.send(f"select 'ATOMICC_BARRIER_LOCKED' from (select pg_advisory_lock({self.lock_id})) held;\n")
        self.read_until("ATOMICC_BARRIER_LOCKED")
        return self

    def send(self, statement: str) -> None:
        if self.process is None or self.process.stdin is None:
            raise RuntimeError("barrier is not running")
        self.process.stdin.write(statement)
        self.process.stdin.flush()

    def read_until(self, marker: str) -> None:
        if self.process is None or self.process.stdout is None:
            raise RuntimeError("barrier has no output")
        deadline = time.monotonic() + self.lab.timeout
        while time.monotonic() < deadline:
            ready, _, _ = select.select([self.process.stdout], [], [], 0.25)
            if not ready:
                continue
            line = self.process.stdout.readline()
            if marker in line:
                return
        raise TimeoutError(f"barrier marker {marker!r} not observed")

    def release(self) -> None:
        self.send(f"select pg_advisory_unlock({self.lock_id});\n")

    def __exit__(self, *_: object) -> None:
        if self.process is not None and self.process.poll() is None:
            try:
                self.send("\\q\n")
                self.process.wait(timeout=5)
            except (BrokenPipeError, subprocess.TimeoutExpired):
                self.process.terminate()


def require(result: subprocess.CompletedProcess[str], marker: str) -> None:
    if result.returncode != 0 or marker not in result.stdout:
        raise AssertionError(
            f"expected {marker}; rc={result.returncode}; stdout={result.stdout!r}; stderr={result.stderr!r}"
        )


def main() -> None:
    lab = Lab()
    context = lab.query("select current_setting('server_version')")
    if not context.startswith("16."):
        raise RuntimeError(f"expected PostgreSQL 16, got {context}")
    require(lab.mode("setup"), "ATOMICC_SETUP_OK")
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            with AdvisoryBarrier(lab, 85101) as barrier:
                expose_future = pool.submit(lab.mode, "expose_hold")
                lab.wait_for("tc-atomicc-expose", "Lock", "advisory")
                withdraw_future = pool.submit(lab.mode, "withdraw")
                lab.wait_for("tc-atomicc-withdraw", "Lock", "transactionid")
                barrier.release()
                expose = expose_future.result(timeout=lab.timeout)
                withdraw = withdraw_future.result(timeout=lab.timeout)
        require(expose, "ATOMICC_EXPOSE_COMMITTED")
        require(withdraw, "ATOMICC_WITHDRAW_COMMITTED")
        require(lab.mode("assert"), "ATOMICC_RACE_CONTRACT_OK")
        print({
            "schema_version": "skill-release-atomic-lifecycle-race-v1",
            "sql_sha256": hashlib.sha256(lab.sql.encode()).hexdigest(),
            "postgresql_version": context,
            "schedule": [
                "exposure locks active release and waits at advisory barrier",
                "withdrawal waits on the same release row lock",
                "exposure commits first",
                "withdrawal rechecks active state, ends exposure, and appends event",
            ],
            "active_exposures_after_withdrawal": 0,
            "lifecycle_events": 1,
        })
    finally:
        require(lab.mode("cleanup"), "ATOMICC_CLEANUP_OK")
        require(lab.mode("verify_zero"), "ATOMICC_ZERO_RESIDUE_OK")


if __name__ == "__main__":
    main()
