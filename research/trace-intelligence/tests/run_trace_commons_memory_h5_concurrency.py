#!/usr/bin/env python3
"""Run the content-free H5 PostgreSQL concurrency conformance suite.

The runner is intentionally local-lab only. It refuses any Kubernetes context
other than ``colima`` and drives independent psql sessions in the disposable
``frankengate-test/postgres-0`` pod. Every started test is followed by cleanup
and a zero-residue assertion, including on failure.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import dataclasses
import hashlib
import json
import pathlib
import re
import select
import subprocess
import sys
import time
from typing import Iterable


ROOT = pathlib.Path(__file__).resolve().parents[3]
SQL_PATH = (
    ROOT
    / "research"
    / "trace-intelligence"
    / "sql"
    / "008_trace_commons_memory_h5_concurrency.sql"
)


@dataclasses.dataclass(frozen=True)
class CommandResult:
    mode: str
    returncode: int
    stdout: str
    stderr: str
    elapsed_ms: int


class Lab:
    def __init__(
        self,
        namespace: str,
        pod: str,
        user: str,
        database: str,
        timeout: float,
    ) -> None:
        self.namespace = namespace
        self.pod = pod
        self.user = user
        self.database = database
        self.timeout = timeout
        self.sql = SQL_PATH.read_text(encoding="utf-8")

    def _psql_prefix(self, *, interactive: bool = False) -> list[str]:
        command = [
            "kubectl",
            "exec",
        ]
        if interactive:
            command.append("-i")
        command += [
            "-n",
            self.namespace,
            self.pod,
            "--",
            "psql",
            "-X",
            "-U",
            self.user,
            "-d",
            self.database,
            "-Atq",
            "-v",
            "ON_ERROR_STOP=1",
        ]
        return command

    def query(self, sql: str) -> str:
        result = subprocess.run(
            self._psql_prefix() + ["-c", sql],
            check=False,
            capture_output=True,
            text=True,
            timeout=self.timeout,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"lab query failed ({result.returncode}): {result.stderr.strip()}"
            )
        return result.stdout.strip()

    def run_mode(self, mode: str, *, timeout: float | None = None) -> CommandResult:
        started = time.monotonic()
        result = subprocess.run(
            self._psql_prefix(interactive=True) + ["-v", f"mode={mode}"],
            input=self.sql,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout or self.timeout,
        )
        return CommandResult(
            mode=mode,
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
            elapsed_ms=round((time.monotonic() - started) * 1000),
        )

    def wait_for(
        self,
        application_name: str,
        *,
        wait_event: str | None = None,
        wait_event_type: str = "Lock",
    ) -> None:
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            predicate = [
                "application_name = "
                + "'" + application_name.replace("'", "''") + "'",
                "state = 'active'",
                "wait_event_type = "
                + "'" + wait_event_type.replace("'", "''") + "'",
            ]
            if wait_event is not None:
                predicate.append(
                    "wait_event = " + "'" + wait_event.replace("'", "''") + "'"
                )
            count = self.query(
                "select count(*) from pg_stat_activity where "
                + " and ".join(predicate)
            )
            if count == "1":
                return
            time.sleep(0.05)
        event = f"/{wait_event}" if wait_event else ""
        raise TimeoutError(
            f"{application_name} did not reach {wait_event_type}{event} barrier"
        )


class AdvisoryBarrier:
    """A controller session holding one session-scoped advisory lock."""

    def __init__(self, lab: Lab, lock_id: int) -> None:
        self.lab = lab
        self.lock_id = lock_id
        self.process: subprocess.Popen[str] | None = None

    def __enter__(self) -> "AdvisoryBarrier":
        self.process = subprocess.Popen(
            self.lab._psql_prefix(interactive=True),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._send(
            f"select 'H5C_BARRIER_LOCKED_{self.lock_id}' "
            f"from (select pg_advisory_lock({self.lock_id})) held;\n"
        )
        self._read_until(f"H5C_BARRIER_LOCKED_{self.lock_id}")
        return self

    def release(self) -> None:
        self._send(
            f"select case when pg_advisory_unlock({self.lock_id}) "
            f"then 'H5C_BARRIER_RELEASED_{self.lock_id}' "
            "else 'H5C_BARRIER_NOT_HELD' end;\n"
        )
        self._read_until(f"H5C_BARRIER_RELEASED_{self.lock_id}")

    def _send(self, statement: str) -> None:
        if self.process is None or self.process.stdin is None:
            raise RuntimeError("barrier controller is not running")
        self.process.stdin.write(statement)
        self.process.stdin.flush()

    def _read_until(self, marker: str) -> None:
        if self.process is None or self.process.stdout is None:
            raise RuntimeError("barrier controller has no stdout")
        deadline = time.monotonic() + self.lab.timeout
        observed: list[str] = []
        while time.monotonic() < deadline:
            remaining = max(0.0, deadline - time.monotonic())
            ready, _, _ = select.select([self.process.stdout], [], [], remaining)
            if not ready:
                break
            line = self.process.stdout.readline()
            if line == "":
                break
            observed.append(line.rstrip())
            if marker in line:
                return
        stderr = ""
        if self.process.stderr is not None:
            ready, _, _ = select.select([self.process.stderr], [], [], 0)
            if ready:
                stderr = self.process.stderr.read()
        raise TimeoutError(
            f"barrier marker {marker!r} not observed; "
            f"stdout={observed!r}; stderr={stderr!r}"
        )

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self.process is None:
            return
        if self.process.poll() is None:
            try:
                self._send("\\q\n")
                self.process.wait(timeout=5)
            except (BrokenPipeError, subprocess.TimeoutExpired):
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)


def require_ok(result: CommandResult, marker: str | None = None) -> None:
    if result.returncode != 0:
        raise AssertionError(
            f"{result.mode} failed ({result.returncode})\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    if marker is not None and marker not in result.stdout:
        raise AssertionError(
            f"{result.mode} did not emit {marker!r}: {result.stdout!r}"
        )


def require_expected_failure(
    result: CommandResult, expected_error: str
) -> None:
    if result.returncode == 0:
        raise AssertionError(f"{result.mode} unexpectedly succeeded")
    combined = result.stdout + "\n" + result.stderr
    if expected_error not in combined:
        raise AssertionError(
            f"{result.mode} failed for the wrong reason; expected "
            f"{expected_error!r}\n{combined}"
        )


def parse_visibility(result: CommandResult) -> tuple[int, int]:
    values = [
        int(match.group(1))
        for match in re.finditer(r"^H5C_(?:BEFORE|AFTER)\|(\d+)$", result.stdout, re.M)
    ]
    if len(values) != 2:
        raise AssertionError(
            f"{result.mode} did not emit exactly two visibility counts: "
            f"{result.stdout!r}"
        )
    return values[0], values[1]


def run_visibility_race(
    lab: Lab,
    pool: concurrent.futures.ThreadPoolExecutor,
    *,
    reader_mode: str,
    reader_application: str,
    mutation_mode: str,
    lock_id: int,
    expected: tuple[int, int],
) -> dict[str, object]:
    with AdvisoryBarrier(lab, lock_id) as barrier:
        reader_future = pool.submit(lab.run_mode, reader_mode)
        lab.wait_for(reader_application, wait_event="advisory")
        mutation = lab.run_mode(mutation_mode)
        require_ok(mutation)
        barrier.release()
        reader = reader_future.result(timeout=lab.timeout)
    require_ok(reader)
    observed = parse_visibility(reader)
    if observed != expected:
        raise AssertionError(
            f"{reader_mode} visibility was {observed}, expected {expected}"
        )
    return {
        "reader_mode": reader_mode,
        "mutation_mode": mutation_mode,
        "isolation": "repeatable_read" if reader_mode.endswith("_rr") else "read_committed",
        "before": observed[0],
        "after": observed[1],
        "barrier": lock_id,
        "reader_elapsed_ms": reader.elapsed_ms,
        "mutation_elapsed_ms": mutation.elapsed_ms,
    }


def verify_lab(lab: Lab) -> dict[str, str]:
    context = subprocess.run(
        ["kubectl", "config", "current-context"],
        check=True,
        capture_output=True,
        text=True,
        timeout=lab.timeout,
    ).stdout.strip()
    if context != "colima":
        raise RuntimeError(
            f"refusing to run H5C concurrency suite in Kubernetes context {context!r}"
        )
    receipt = lab.query(
        "select current_setting('server_version') || '|' || "
        "coalesce((select extversion from pg_extension where extname='vector'),'missing')"
    )
    version, vector = receipt.split("|", 1)
    if not version.startswith("16."):
        raise RuntimeError(f"expected PostgreSQL 16, got {version}")
    if vector != "0.8.1":
        raise RuntimeError(f"expected pgvector 0.8.1, got {vector}")
    return {
        "kubernetes_context": context,
        "postgresql_version": version,
        "pgvector_version": vector,
    }


def run_suite(lab: Lab) -> dict[str, object]:
    receipt = verify_lab(lab)
    results: dict[str, object] = {
        "schema_version": "trace-commons-memory-h5-concurrency-result-v1",
        "artifacts": {
            "sql_path": str(SQL_PATH.relative_to(ROOT)),
            "sql_sha256": hashlib.sha256(lab.sql.encode("utf-8")).hexdigest(),
        },
        "lab": receipt,
        "fixture_prefix": "tc-h5c-",
        "raw_trace_content_loaded": False,
        "races": [],
        "known_gaps": [
            {
                "name": "no_persistent_governance_writer_boundary_in_research_schema",
                "severity": "schema_boundary",
                "detail": (
                    "The checked-in schema has no non-owner role allowed to advance "
                    "authority epochs or revoke memberships. The suite creates a "
                    "temporary NOSUPERUSER NOBYPASSRLS NOINHERIT role with "
                    "fixture-prefix-restricted SECURITY DEFINER helpers, then drops it."
                ),
            },
            {
                "name": "release_status_and_event_are_not_database_coupled",
                "severity": "schema_boundary",
                "detail": (
                    "The schema permits a release status update without a matching "
                    "release event. The test actor writes both in one transaction, "
                    "but the database does not force every caller to do so."
                ),
            }
        ],
        "claim_boundary": (
            "Local PostgreSQL 16.12/pgvector 0.8.1 concurrency mechanics only; "
            "not Aurora, RDS Proxy, failover, replica lag, durability, scale, "
            "memory correctness, utility, identity, or enterprise transfer."
        ),
    }
    try:
        setup = lab.run_mode("setup")
        require_ok(setup, "H5C_SETUP_OK")

        failed_job = lab.run_mode("failed_job")
        require_expected_failure(
            failed_job, "evaluation_runs_cost_microunits_check"
        )
        atomic = lab.run_mode("assert_failed_job")
        require_ok(atomic, "H5C_FAILED_JOB_ATOMIC_OK")
        results["failed_job_atomicity"] = {
            "worker_returncode": failed_job.returncode,
            "failure": "evaluation_runs_cost_microunits_check",
            "partial_rows_after_disconnect": 0,
        }

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
            with AdvisoryBarrier(lab, 85001) as barrier:
                promote_a_future = pool.submit(lab.run_mode, "promote_a")
                lab.wait_for("tc-h5c-promote-a", wait_event="advisory")
                promote_b_future = pool.submit(lab.run_mode, "promote_b")
                lab.wait_for("tc-h5c-promote-b", wait_event="transactionid")
                barrier.release()
                promote_a = promote_a_future.result(timeout=lab.timeout)
                promote_b = promote_b_future.result(timeout=lab.timeout)
            require_ok(promote_a, "H5C_PROMOTE_A_COMMITTED")
            require_expected_failure(
                promote_b, "artifact_releases_one_active_candidate_idx"
            )
            promotion_assert = lab.run_mode("assert_promotion")
            require_ok(promotion_assert, "H5C_PROMOTION_SERIALIZED_OK")
            results["races"].append(
                {
                    "name": "concurrent_promotion",
                    "barrier": 85001,
                    "schedule": [
                        "A inserts active release and blocks on advisory barrier",
                        "B attempts same-candidate active release and waits on transactionid",
                        "A commits",
                        "B fails unique active-release index",
                    ],
                    "winner": "tc-h5c-release-a",
                    "loser_persisted": False,
                }
            )

            with AdvisoryBarrier(lab, 85002) as barrier:
                withdraw_future = pool.submit(lab.run_mode, "withdraw_a")
                lab.wait_for("tc-h5c-withdraw-a", wait_event="advisory")
                promote_c_future = pool.submit(lab.run_mode, "promote_c")
                lab.wait_for("tc-h5c-promote-c", wait_event="transactionid")
                barrier.release()
                withdraw = withdraw_future.result(timeout=lab.timeout)
                promote_c = promote_c_future.result(timeout=lab.timeout)
            require_ok(withdraw, "H5C_WITHDRAW_A_COMMITTED")
            require_ok(promote_c, "H5C_PROMOTE_C_COMMITTED")
            withdraw_assert = lab.run_mode("assert_withdraw_promote")
            require_ok(
                withdraw_assert, "H5C_WITHDRAW_PROMOTE_SERIALIZED_OK"
            )
            results["races"].append(
                {
                    "name": "withdraw_then_promote",
                    "barrier": 85002,
                    "schedule": [
                        "A marks current release withdrawn and blocks before commit",
                        "C promotion waits on the partial unique-index transaction",
                        "A commits withdrawal",
                        "C commits as the sole active release",
                    ],
                    "active_release": "tc-h5c-release-c",
                }
            )

            with AdvisoryBarrier(lab, 85003) as barrier:
                expose_future = pool.submit(lab.run_mode, "expose_c")
                lab.wait_for("tc-h5c-expose-c", wait_event="advisory")
                withdraw_c = lab.run_mode("withdraw_c")
                require_ok(withdraw_c, "H5C_WITHDRAW_C_COMMITTED")
                barrier.release()
                expose_c = expose_future.result(timeout=lab.timeout)
            require_ok(expose_c, "H5C_EXPOSURE_C_COMMITTED")
            exposure_assert = lab.run_mode("assert_withdraw_exposure")
            require_ok(
                exposure_assert, "H5C_WITHDRAW_EXPOSURE_HIDDEN_OK"
            )
            if (
                "H5C_KNOWN_GAP|active_exposure_metadata_survives_withdrawal"
                not in exposure_assert.stdout
            ):
                raise AssertionError("withdraw/exposure known gap was not reported")
            results["races"].append(
                {
                    "name": "exposure_commit_after_withdrawal",
                    "barrier": 85003,
                    "runtime_visible_after_withdrawal": 0,
                    "active_exposure_metadata_rows": 1,
                }
            )
            results["known_gaps"].append(
                {
                    "name": "active_exposure_metadata_survives_withdrawal",
                    "severity": "architecture_gate",
                    "detail": (
                        "An exposure inserted before withdrawal but committed after "
                        "withdrawal remains status=active in storage. RLS hides it "
                        "from runtime reads because the parent release is inactive."
                    ),
                }
            )

            seed_d = lab.run_mode("seed_release_d")
            require_ok(seed_d, "H5C_RELEASE_D_READY")

            results["races"].append(
                run_visibility_race(
                    lab,
                    pool,
                    reader_mode="epoch_reader_rc",
                    reader_application="tc-h5c-epoch-reader-rc",
                    mutation_mode="epoch_advance",
                    lock_id=85004,
                    expected=(1, 0),
                )
            )
            require_ok(lab.run_mode("epoch_restore"), "H5C_EPOCH_RESTORED")
            results["races"].append(
                run_visibility_race(
                    lab,
                    pool,
                    reader_mode="epoch_reader_rr",
                    reader_application="tc-h5c-epoch-reader-rr",
                    mutation_mode="epoch_advance",
                    lock_id=85005,
                    expected=(1, 1),
                )
            )
            results["known_gaps"].append(
                {
                    "name": "repeatable_read_epoch_snapshot_stays_authorized",
                    "severity": "transaction_contract",
                    "detail": (
                        "A REPEATABLE READ transaction retains the authority row "
                        "snapshot after a committed epoch advance; old-epoch reads "
                        "remain visible until the transaction ends."
                    ),
                }
            )
            guarded_rr = lab.run_mode("epoch_reader_rr_guarded")
            require_expected_failure(
                guarded_rr,
                "governed queries require READ COMMITTED; repeatable read rejected",
            )
            results["governed_isolation_guard"] = {
                "repeatable_read_rejected": True,
                "required_isolation": "read committed",
                "failure": "governed queries require READ COMMITTED; repeatable read rejected",
            }
            require_ok(lab.run_mode("epoch_restore"), "H5C_EPOCH_RESTORED")

            results["races"].append(
                run_visibility_race(
                    lab,
                    pool,
                    reader_mode="membership_reader_rc",
                    reader_application="tc-h5c-membership-reader-rc",
                    mutation_mode="membership_revoke",
                    lock_id=85006,
                    expected=(1, 0),
                )
            )
            require_ok(
                lab.run_mode("membership_restore"), "H5C_MEMBERSHIP_RESTORED"
            )
            results["races"].append(
                run_visibility_race(
                    lab,
                    pool,
                    reader_mode="membership_reader_rr",
                    reader_application="tc-h5c-membership-reader-rr",
                    mutation_mode="membership_revoke",
                    lock_id=85007,
                    expected=(1, 1),
                )
            )
            results["known_gaps"].append(
                {
                    "name": "repeatable_read_membership_snapshot_stays_authorized",
                    "severity": "transaction_contract",
                    "detail": (
                        "A REPEATABLE READ transaction retains team membership "
                        "visibility after a committed membership revocation."
                    ),
                }
            )
            require_ok(
                lab.run_mode("membership_restore"), "H5C_MEMBERSHIP_RESTORED"
            )

            results["races"].append(
                run_visibility_race(
                    lab,
                    pool,
                    reader_mode="deletion_reader_rc",
                    reader_application="tc-h5c-deletion-reader-rc",
                    mutation_mode="delete_target",
                    lock_id=85008,
                    expected=(1, 0),
                )
            )
            require_ok(
                lab.run_mode("restore_delete_target"),
                "H5C_DELETE_TARGET_RESTORED",
            )
            results["races"].append(
                run_visibility_race(
                    lab,
                    pool,
                    reader_mode="deletion_reader_rr",
                    reader_application="tc-h5c-deletion-reader-rr",
                    mutation_mode="delete_target",
                    lock_id=85009,
                    expected=(1, 1),
                )
            )
            results["known_gaps"].append(
                {
                    "name": "repeatable_read_deleted_trajectory_stays_visible",
                    "severity": "transaction_contract",
                    "detail": (
                        "A REPEATABLE READ transaction retains an authorized "
                        "trajectory snapshot after a committed hard deletion."
                    ),
                }
            )

        provenance_delete = lab.run_mode("delete_provenance_source")
        require_expected_failure(
            provenance_delete, "candidate_sources_source_trajectory_id_fkey"
        )
        provenance_assert = lab.run_mode("assert_provenance_source")
        require_ok(
            provenance_assert, "H5C_PROVENANCE_DELETE_RESTRICTED_OK"
        )
        results["provenance_delete"] = {
            "blocked_by": "candidate_sources_source_trajectory_id_fkey",
            "source_preserved": True,
        }

        final = lab.run_mode("final_assertions")
        require_ok(final, "H5C_FINAL_CONTENT_FREE_AND_ROLE_ASSERTIONS_OK")
        results["content_free_and_role_assertions"] = "passed"
        results["overall"] = "mechanics_passed_with_architecture_gaps"
        return results
    finally:
        cleanup = lab.run_mode("cleanup")
        zero = lab.run_mode("verify_zero")
        if cleanup.returncode != 0 or zero.returncode != 0:
            message = (
                "H5C cleanup/zero-residue failure\n"
                f"cleanup: {cleanup}\nzero: {zero}"
            )
            if sys.exc_info()[0] is None:
                raise AssertionError(message)
            print(message, file=sys.stderr)
        elif "H5C_ZERO_RESIDUE_OK" not in zero.stdout:
            raise AssertionError(f"zero-residue marker missing: {zero.stdout!r}")
        else:
            results["cleanup"] = {
                "fixture_rows": 0,
                "temporary_helpers": 0,
                "temporary_roles": 0,
                "marker": "H5C_ZERO_RESIDUE_OK",
            }


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--namespace", default="frankengate-test")
    parser.add_argument("--pod", default="postgres-0")
    parser.add_argument("--user", default="frankengate")
    parser.add_argument("--database", default="frankengate")
    parser.add_argument("--timeout", type=float, default=30.0)
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] = sys.argv[1:]) -> int:
    args = parse_args(argv)
    lab = Lab(
        namespace=args.namespace,
        pod=args.pod,
        user=args.user,
        database=args.database,
        timeout=args.timeout,
    )
    result = run_suite(lab)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
