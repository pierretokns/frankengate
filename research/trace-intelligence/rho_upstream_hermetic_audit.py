#!/usr/bin/env python3
"""Run and receipt the pinned RHO upstream hermetic mechanics suite."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any


TARGETED = [
    "tests/hermetic/test_dpp_core.py",
    "tests/hermetic/test_reasoningbank_store.py",
    "tests/hermetic/test_reasoningbank_retrieval.py",
    "tests/hermetic/test_loop_no_op_optimize_is_rejected.py",
    "tests/hermetic/test_loop_rejects_harmful_optimize.py",
    "tests/hermetic/test_evaluate_primitive.py",
    "tests/hermetic/test_optimize_primitive.py",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_pytest(root: Path, paths: list[str]) -> dict[str, Any]:
    proc = subprocess.run(
        ["uv", "run", "--project", str(root), "pytest", "-q", "-n", "1", *paths],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
        timeout=300,
    )
    text = proc.stdout + "\n" + proc.stderr
    summary = re.findall(r"(\d+) failed, (\d+) passed(?:, (\d+) skipped)?", text)
    passed_only = re.findall(r"(\d+) passed(?: in [0-9.]+s)?", text)
    failures = sorted(
        item for item in set(re.findall(r"(?:FAILED|ERROR) ([^\s]+)", text))
        if item.startswith("tests/")
    )
    return {
        "returncode": proc.returncode,
        "summary_lines": summary,
        "passed_only_lines": passed_only,
        "failure_or_error_nodes": failures,
        "output_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "output_bytes": len(text.encode()),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rho-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.rho_root.resolve()
    commit = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    full = run_pytest(root, ["tests/hermetic"])
    targeted = run_pytest(root, TARGETED)
    result = {
        "schema_version": "frankengate-rho-upstream-hermetic-audit-v1",
        "upstream": {
            "repository": "wbopan/retro-harness",
            "source_commit": commit,
            "pyproject_sha256": sha256(root / "pyproject.toml"),
        },
        "protocol": {
            "full_command": "uv run --project <root> pytest tests/hermetic -q -n 1",
            "targeted_command": "uv run --project <root> pytest -q -n 1 " + " ".join(TARGETED),
            "llm_calls": False,
            "docker_or_external_benchmarks": False,
        },
        "full_hermetic": full,
        "targeted_core_mechanics": targeted,
        "claim_boundary": {
            "upstream_mechanics_executed": True,
            "rho_efficacy_reproduced": False,
            "reason": "Hermetic code paths were exercised without LLM or benchmark calls; full-suite failures are retained as typed upstream/environment compatibility findings.",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"full": full, "targeted": targeted}, sort_keys=True))
    return 0 if targeted["returncode"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
