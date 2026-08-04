#!/usr/bin/env python3
"""Run each treatment arm in its own disposable Postgres process.

The seed-isolated runner deliberately keeps arms together for matched runs.
That is useful for throughput, but it leaves a possible cross-arm state/cache
confound.  This wrapper invokes it once per seed/arm, giving every arm a fresh
container, role, port, audit root, and verifier process.  The resulting receipts
can be passed directly to ``frontier_transfer_multiseed_aggregate.py``.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RUNNER = ROOT / "frontier_transfer_docker_isolated.py"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, action="append", required=True)
    parser.add_argument("--base-port", type=int, default=55740)
    parser.add_argument("--base-proxy-port", type=int, default=18240)
    parser.add_argument("--arm", action="append", required=True,
                        choices=("no_skill", "formatting_placebo", "length_matched_neutral", "trace_mined_terminal_discipline", "trace2skill_compiled_procedure"))
    parser.add_argument("--task-mutation", choices=("broker-four-task-renamed-paraphrase-v1",))
    parser.add_argument("--harness", choices=("openai-proxy", "codex-cli-native-json-v1"), default="openai-proxy")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--trace", type=Path,
                        default=ROOT / "experiments/results/trace-mined-skill-candidate-car-schema-injected-2026-08-02.json")
    parser.add_argument("--task-id", action="append",
                        help="task IDs to replay; defaults to the sealed four-task cohort")
    args = parser.parse_args()

    runs: list[dict[str, object]] = []
    tasks = tuple(args.task_id or [])
    job_index = 0
    for seed in args.seed:
        for arm in args.arm:
            # The inner runner writes seed-keyed files.  Each invocation is
            # sequential, so it cannot overwrite another arm's receipt.
            metadata_path = ROOT / f"experiments/results/.arm-isolated-run-{seed}-{arm}-{job_index}.json"
            cmd = [
                "uv", "run", "--project", ".", "python", str(RUNNER),
                "--seed", str(seed), "--parallel", "1",
                "--base-port", str(args.base_port + job_index),
                "--base-proxy-port", str(args.base_proxy_port + job_index),
                "--harness", args.harness, "--arm", arm,
                "--trace", str(args.trace.resolve(strict=True)),
                "--result-tag", f"arm-{arm}",
                "--output", str(metadata_path),
            ]
            if args.task_mutation:
                cmd += ["--task-mutation", args.task_mutation]
            for task in tasks:
                cmd += ["--task-id", task]
            subprocess.run(cmd, cwd=ROOT, check=True, timeout=2400)
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if len(metadata.get("runs", [])) != 1:
                raise ValueError(f"expected one run in {metadata_path}")
            run = dict(metadata["runs"][0])
            result_src = Path(str(run["result"]))
            verification_src = Path(str(run["verification"]))
            result_dst = ROOT / f"experiments/results/defog-codex-frontier-broker-transfer-docker-arm-{arm}-seed-{seed}-2026-08-02.json"
            verification_dst = ROOT / f"experiments/results/defog-codex-frontier-broker-transfer-docker-arm-{arm}-seed-{seed}-independent-verification-2026-08-02.json"
            shutil.copyfile(result_src, result_dst)
            shutil.copyfile(verification_src, verification_dst)
            run["result"] = str(result_dst)
            run["verification"] = str(verification_dst)
            run["isolation"] = "one-disposable-postgres-container-and-verifier-per-seed-arm"
            runs.append(run)
            metadata_path.unlink(missing_ok=True)
            job_index += 1

    payload = {
        "schema_version": "frankengate-frontier-transfer-docker-arm-isolated-run-v1",
        "runs": runs,
        "claim_boundary": "Every seed-arm receipt used a fresh database container, role, port, raw audit root, and independent verifier. This controls cross-arm state leakage; it does not establish universal skill utility or promotion eligibility.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "runs": len(runs), "output": str(args.output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
