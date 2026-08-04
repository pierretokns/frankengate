"""Launch the pinned Trace2Skill runner with a governed tool boundary.

This adapter deliberately does not copy or fork the benchmark.  It verifies the
source snapshot, imports the upstream runner, and replaces every imported
``create_bash_tool`` binding before an agent is constructed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Sequence

from governed_tool_sandbox import create_trace2skill_bash_tool


PINNED_REVISION = "3d0b52a140f002a512930252b613c49048f7d5ac"
PINNED_DATASET_SHA256 = (
    "bcecaa89a005bd4e3bbe98da150a86e8062c27f262e575d5e47bd9861b3525e7"
)
DATASET_RELATIVE_PATH = Path(
    "data/spreadsheetbench_verified/spreadsheetbench_verified_400/dataset.json"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_source(root: Path) -> dict:
    root = root.resolve(strict=True)
    required = (
        root / "run_spreadsheetbench.py",
        root / "evaluate_with_official.py",
        root / "spreadsheet_agent" / "tools" / "bash.py",
        root / DATASET_RELATIVE_PATH,
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"pinned Trace2Skill files missing: {missing}")
    observed = sha256_file(root / DATASET_RELATIVE_PATH)
    if observed != PINNED_DATASET_SHA256:
        raise ValueError(
            "Trace2Skill dataset manifest hash mismatch: "
            f"expected {PINNED_DATASET_SHA256}, observed {observed}"
        )
    rows = json.loads((root / DATASET_RELATIVE_PATH).read_text(encoding="utf-8"))
    if not isinstance(rows, list) or len(rows) != 400:
        raise ValueError("pinned Trace2Skill dataset must contain exactly 400 rows")
    return {
        "revision": PINNED_REVISION,
        "dataset_sha256": observed,
        "dataset_rows": len(rows),
    }


def option_value(arguments: Sequence[str], name: str) -> str | None:
    for index, value in enumerate(arguments):
        if value == name and index + 1 < len(arguments):
            return arguments[index + 1]
        prefix = f"{name}="
        if value.startswith(prefix):
            return value[len(prefix) :]
    return None


def patch_upstream_tool_boundary(
    upstream_root: Path,
    runtime_bin: Path,
    raw_audit_root: Path,
    upstream_arguments: Sequence[str],
) -> None:
    sys.path.insert(0, str(upstream_root))
    sys.path.insert(0, str(upstream_root / "src"))

    import spreadsheet_agent.agents.cli_only_agent as cli_only
    import spreadsheet_agent.agents.cli_skill_preloaded_agent as skill_preloaded
    import spreadsheet_agent.tools as upstream_tools

    configured_skills = option_value(upstream_arguments, "--skills_dir")
    skills_root = (
        Path(configured_skills).resolve(strict=True)
        if configured_skills
        else (upstream_root / "spreadsheet_agent" / "skills").resolve(strict=True)
    )
    runtime_bin = runtime_bin.resolve(strict=True)
    python_runtime_root = Path(sys.executable).resolve(strict=True).parent.parent
    raw_audit_root = raw_audit_root.resolve(strict=True)

    def governed_factory(working_dir: str, timeout: int = 120):
        task_name = Path(working_dir).resolve().name
        return create_trace2skill_bash_tool(
            working_dir,
            readable_roots=(str(skills_root), str(python_runtime_root)),
            executable_dirs=(str(runtime_bin),),
            audit_path=str(raw_audit_root / f"{task_name}.tool-calls.jsonl"),
            timeout=timeout,
        )

    # Both agent modules imported the symbol directly, so all three bindings
    # must be replaced before create_agent() constructs the first agent.
    upstream_tools.create_bash_tool = governed_factory
    cli_only.create_bash_tool = governed_factory
    skill_preloaded.create_bash_tool = governed_factory


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run pinned Trace2Skill with fail-closed tool execution"
    )
    parser.add_argument("--trace2skill-root", required=True, type=Path)
    parser.add_argument(
        "--runtime-bin",
        required=True,
        type=Path,
        help="bin directory of the disposable Python environment",
    )
    parser.add_argument(
        "--raw-audit-root",
        required=True,
        type=Path,
        help="external directory for content-bearing tool-call JSONL",
    )
    parser.add_argument(
        "upstream_arguments",
        nargs=argparse.REMAINDER,
        help="arguments after -- are passed to run_spreadsheetbench.py",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    upstream_arguments = list(args.upstream_arguments)
    if upstream_arguments and upstream_arguments[0] == "--":
        upstream_arguments = upstream_arguments[1:]
    if not upstream_arguments:
        raise ValueError("Trace2Skill runner arguments are required after --")

    upstream_root = args.trace2skill_root.resolve(strict=True)
    runtime_bin = args.runtime_bin.resolve(strict=True)
    raw_audit_root = args.raw_audit_root.resolve()
    raw_audit_root.mkdir(parents=True, exist_ok=True)
    if any(raw_audit_root.iterdir()):
        raise ValueError("raw audit root must be empty for an immutable run")

    receipt = verify_source(upstream_root)
    patch_upstream_tool_boundary(
        upstream_root, runtime_bin, raw_audit_root, upstream_arguments
    )

    import run_spreadsheetbench

    # A local OpenAI-compatible model endpoint still needs a non-secret sentinel.
    os.environ.setdefault("OPENAI_API_KEY", "EMPTY")
    print(json.dumps({"governed_launcher": receipt}, sort_keys=True))
    previous = sys.argv
    try:
        sys.argv = [str(upstream_root / "run_spreadsheetbench.py")] + upstream_arguments
        run_spreadsheetbench.main()
    finally:
        sys.argv = previous
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
