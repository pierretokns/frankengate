#!/usr/bin/env python3
"""Run matched frontier transfer seeds with one disposable Postgres per seed.

The earlier multiseed run used one Postgres cluster with per-run roles.  That
is authorization-isolated, but it still shares connection pools, WAL, cache,
and scheduler state.  This runner gives each seed its own container, mapped
port, database, audit directory, and loopback Codex proxy.  Raw trajectory
audits remain outside the repository; only hash-bearing receipts are written.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = Path("/private/tmp/defog-sql-eval-research")
COHORT = ROOT / "experiments/manifests/defog-sql-eval-enterprise-96-2026-07-30.json"
DATASET = ROOT / "configs/datasets/defog-sql-eval-enterprise.json"
AUTHORITY = ROOT / "configs/governance/defog-factorial-authority-epoch-2026-07-30.json"
TRACE = ROOT / "experiments/results/trace-mined-skill-candidate-car-schema-injected-2026-08-02.json"
TASKS = [
    "defog-sql-eval:instruct_advanced_postgres:broker:11:9c7b2337a36d",
    "defog-sql-eval:instruct_advanced_postgres:broker:12:9e137a09d497",
    "defog-sql-eval:instruct_advanced_postgres:broker:14:e4d51056245a",
    "defog-sql-eval:instruct_advanced_postgres:broker:2:fcfd29423477",
]
IMAGE = "postgres:16-alpine"


def colima(*args: str, check: bool = True, timeout: int = 120) -> str:
    cp = subprocess.run(["colima", "ssh", "--", *args], text=True,
                        capture_output=True, timeout=timeout)
    if check and cp.returncode:
        raise RuntimeError(cp.stderr.strip() or cp.stdout.strip())
    return cp.stdout.strip()


def wait_port(port: int, timeout: float = 90) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return
        except OSError:
            time.sleep(1)
    raise TimeoutError(f"port {port} did not become reachable")


def run_seed(seed: int, port: int, proxy_port: int, keep: bool, arms: tuple[str, ...], task_mutation: str | None = None) -> dict[str, str | int | list[str] | str | None]:
    suffix = f"{os.getpid()}-{seed}"
    container = f"fg-frontier-pg-{suffix}"
    password = f"fg_frontier_pw_{seed}"
    app_user = f"fg_frontier_app_{seed}"
    audit = Path(f"/private/tmp/defog-codex-docker-audit-seed-{seed}-{os.getpid()}")
    verify_audit = Path(f"/private/tmp/defog-codex-docker-verify-seed-{seed}-{os.getpid()}")
    result = ROOT / f"experiments/results/defog-codex-frontier-broker-transfer-docker-seed-{seed}-2026-08-02.json"
    verification = ROOT / f"experiments/results/defog-codex-frontier-broker-transfer-docker-seed-{seed}-independent-verification-2026-08-02.json"
    audit.mkdir(parents=True, exist_ok=True)
    verify_audit.mkdir(parents=True, exist_ok=True)
    proxy = None
    try:
        colima("docker", "run", "-d", "--name", container, "-p", f"{port}:5432",
               "-e", "POSTGRES_USER=research", "-e", f"POSTGRES_PASSWORD={password}",
               "-e", "POSTGRES_DB=broker", IMAGE)
        for _ in range(90):
            ready = colima("docker", "exec", container, "pg_isready", "-U", "research", "-d", "broker", check=False)
            if "accepting connections" in ready:
                break
            time.sleep(1)
        else:
            raise TimeoutError(f"{container} did not become ready")
        # Copy only the pinned public benchmark database; no user traces enter
        # the container. The pipe runs inside the Colima VM.
        colima("sh", "-lc", f"docker exec frankengate-defog-skill-pg pg_dump -U research -d broker --clean --if-exists | docker exec -i {container} psql -U research -d broker", timeout=180)
        # The image's bootstrap owner is a superuser. Create the actual
        # governed application role before handing the DSN to the pilot;
        # otherwise the executor correctly rejects a BYPASSRLS role.
        colima("docker", "exec", container, "psql", "-U", "research", "-d", "broker", "-v", "ON_ERROR_STOP=1", "-c",
               f"CREATE ROLE {app_user} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD '{password}'; GRANT CONNECT ON DATABASE broker TO {app_user}; GRANT USAGE ON SCHEMA public TO {app_user}; GRANT SELECT ON ALL TABLES IN SCHEMA public TO {app_user};")
        proxy = subprocess.Popen(["uv", "run", "python", str(ROOT / "codex_openai_proxy.py"),
                                  "--port", str(proxy_port), "--timeout", "120"], cwd=ROOT,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        wait_port(proxy_port)
        base = ["uv", "run", "python", "defog_trace_mined_skill_pilot.py",
                "--source-root", str(SOURCE_ROOT), "--cohort-manifest", str(COHORT),
                "--dataset-manifest", str(DATASET), "--authority-manifest", str(AUTHORITY),
                "--dsn", f"host=127.0.0.1 port={port} user={app_user} password={password} dbname=broker",
                "--endpoint", f"http://127.0.0.1:{proxy_port}", "--model", "gpt-5.6-luna",
                "--model-provider", "codex-cli", "--endpoint-scope", "codex-subscription-loopback-proxy",
                "--raw-audit-dir", str(audit), "--output", str(result), "--seed-base", str(seed),
                "--max-model-turns", "8", "--max-sql-attempts", "4", "--max-tokens", "800",
                "--request-timeout-seconds", "120", "--max-generated-tokens-per-episode", "4800",
                "--protocol-remediation-id", "frontier-codex-family-disjoint-schema-injected-docker-db-multiseed-v1",
                "--inject-authorized-schema", "--trace-mined-candidate-file", str(TRACE)]
        for arm in arms:
            base += ["--arm", arm]
        if task_mutation:
            base += ["--task-mutation", task_mutation]
        for task in TASKS:
            base += ["--task-id", task]
        subprocess.run(base, cwd=ROOT, check=True, timeout=1800)
        verify = ["uv", "run", "python", "defog_semantic_outcome_verifier.py", "--result", str(result),
                  "--raw-audit-dir", str(audit), "--source-root", str(SOURCE_ROOT),
                  "--cohort-manifest", str(COHORT), "--dataset-manifest", str(DATASET),
                  "--authority-manifest", str(AUTHORITY), "--dsn-template",
                  f"host=127.0.0.1 port={port} user={app_user} password={password} dbname={{database}}",
                  "--verifier-audit-dir", str(verify_audit), "--output", str(verification)]
        for task in TASKS:
            verify += ["--task-id", task]
        subprocess.run(verify, cwd=ROOT, check=True, timeout=600)
        return {"seed": seed, "result": str(result), "verification": str(verification), "database_container": container, "database_port": port, "proxy_port": proxy_port, "arms": list(arms), "task_mutation": task_mutation}
    finally:
        if proxy is not None:
            proxy.terminate()
            try:
                proxy.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proxy.kill()
        if not keep:
            colima("docker", "rm", "-f", container, check=False)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, action="append", required=True)
    parser.add_argument("--base-port", type=int, default=55640)
    parser.add_argument("--base-proxy-port", type=int, default=18140)
    parser.add_argument("--parallel", type=int, default=2)
    parser.add_argument("--keep-containers", action="store_true")
    parser.add_argument("--arm", action="append", choices=("no_skill", "formatting_placebo", "length_matched_neutral", "trace_mined_terminal_discipline"))
    parser.add_argument("--task-mutation", choices=("broker-four-task-renamed-paraphrase-v1",))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = []
    arms = tuple(args.arm or ("no_skill", "formatting_placebo", "trace_mined_terminal_discipline"))
    with ThreadPoolExecutor(max_workers=args.parallel) as pool:
        futures = {pool.submit(run_seed, seed, args.base_port + i, args.base_proxy_port + i, args.keep_containers, arms, args.task_mutation): seed for i, seed in enumerate(args.seed)}
        for future in as_completed(futures):
            rows.append(future.result())
    payload = {"schema_version": "frankengate-frontier-transfer-docker-isolated-run-v1", "runs": sorted(rows, key=lambda x: int(x["seed"])), "claim_boundary": "Container/database isolation is proven for this run; it does not establish universal skill utility or promotion eligibility."}
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
