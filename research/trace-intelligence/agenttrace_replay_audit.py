#!/usr/bin/env python3
"""Loss-aware AgentTrace admission and bounded NL2Bash replay audit.

The source release contains rich tool telemetry but no task-correctness field.
This module therefore separates three questions:

1. can every source LLM step and tool span be represented without silent loss;
2. can the historical bash command and released upstream gold command be
   replayed by a deliberately narrow, non-shell executor; and
3. do their stdout and exit codes agree on the same deterministic fixture?

The executor never invokes ``shell=True``.  It supports only fixed read-only
utilities and validates every path against a per-run fixture copy.  Unsupported
commands are an explicit result, not a reason to weaken the sandbox.
"""

from __future__ import annotations

import argparse
import ast
import collections
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Mapping, NamedTuple, Sequence

import pyarrow.parquet as pq


SCHEMA_VERSION = "agenttrace-nl2bash-replay-audit-v1"
CANONICAL_SCHEMA_VERSION = "canonical-trajectory-v1"
DATASET_ID = "pagarsky/agent-trace"
DATASET_REVISION = "4b05b2f00eea267a5bb4d841c228059d1bf9ac0c"
DATASET_LICENSE = "Apache-2.0"
PARQUET_SHA256 = "11c04875f9b6e91b117b5739d748e6bd4f8fa621e95faf430fa40d5d4d223c97"
PARQUET_SIZE = 10_638_584
REFERENCE_ID = "epinnock/intercode-nl2bash-curated"
REFERENCE_REVISION = "019dd0389e872d8b075efbbd94a14d089e5c9f26"
REFERENCE_LICENSE = "MIT"
REFERENCE_SHA256 = "28883a1da8d74d2cd486325dbdda977d17612e9c54f1df46189c199966d85153"
REFERENCE_SIZE = 16_521
EXPECTED_ROWS = 1_400
EXPECTED_NL2BASH_ROWS = 400
EXPECTED_REFERENCE_ROWS = 200
READ_ONLY_PROGRAMS = {
    "basename",
    "cat",
    "cut",
    "dirname",
    "du",
    "find",
    "grep",
    "head",
    "ls",
    "sort",
    "tail",
    "uniq",
    "wc",
}
SAFE_LONG_OPTIONS = {
    "cat": {"--number", "--number-nonblank", "--squeeze-blank", "--show-ends"},
    "cut": {"--characters", "--bytes", "--delimiter", "--fields", "--only-delimited"},
    "du": {"--all", "--human-readable", "--summarize", "--max-depth"},
    "grep": {
        "--extended-regexp",
        "--fixed-strings",
        "--ignore-case",
        "--line-number",
        "--word-regexp",
        "--count",
        "--files-with-matches",
        "--include",
        "--invert-match",
        "--only-matching",
        "--recursive",
    },
    "head": {"--lines", "--bytes", "--quiet", "--verbose"},
    "ls": {"--all", "--almost-all", "--directory", "--recursive"},
    "sort": {"--unique", "--reverse", "--numeric-sort", "--ignore-case"},
    "tail": {"--lines", "--bytes", "--quiet", "--verbose"},
    "uniq": {"--count", "--repeated", "--unique", "--ignore-case"},
    "wc": {"--lines", "--words", "--bytes", "--chars"},
}
SAFE_SHORT_OPTION_CHARS = {
    "cat": set("bEnsTv"),
    "cut": set("bcdsfn"),
    "du": set("ahsk"),
    "grep": set("eEFHhcilnoqRruvw"),
    "head": set("cnqv"),
    "ls": set("AaCdhilRrSst1"),
    "sort": set("bdfhinruz"),
    "tail": set("cnqv"),
    "uniq": set("cdiu"),
    "wc": set("clmw"),
}
FIND_SAFE_EXPRESSIONS = {
    "!",
    "(",
    ")",
    "-a",
    "-and",
    "-atime",
    "-depth",
    "-empty",
    "-false",
    "-iname",
    "-maxdepth",
    "-mindepth",
    "-mtime",
    "-name",
    "-not",
    "-o",
    "-or",
    "-perm",
    "-print",
    "-print0",
    "-size",
    "-type",
    "-true",
}
SHELL_CONTROL = {";", "&&", "||", "&", ">", ">>", "<", "<<", "(", ")"}
FORBIDDEN_TEXT = re.compile(r"[\n\r`]|(?:\$\()|(?:\${)")
PATH_PREFIXES = ("/system", "/testbed", "/workspace", "/testdata")


class AgentTraceAuditError(RuntimeError):
    pass


class UnsupportedCommand(AgentTraceAuditError):
    pass


class CommandResult(NamedTuple):
    returncode: int
    stdout: bytes
    stderr: bytes

    def normalized(self, fixture_root: Path) -> dict[str, Any]:
        root = str(fixture_root).encode("utf-8")
        return {
            "returncode": self.returncode,
            "stdout_sha256": sha256_bytes(self.stdout.replace(root, b"/fixture")),
            "stderr_sha256": sha256_bytes(self.stderr.replace(root, b"/fixture")),
            "stdout_bytes": len(self.stdout),
            "stderr_bytes": len(self.stderr),
        }


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(stable_json(value).encode("utf-8"))


def verify_file(path: Path, expected_sha256: str, expected_size: int) -> None:
    if not path.is_file():
        raise AgentTraceAuditError(f"missing source file: {path}")
    if path.stat().st_size != expected_size:
        raise AgentTraceAuditError(f"size mismatch for {path}")
    if sha256_file(path) != expected_sha256:
        raise AgentTraceAuditError(f"SHA-256 mismatch for {path}")


def load_json_field(value: Any, label: str) -> Any:
    if not isinstance(value, str):
        raise AgentTraceAuditError(f"{label} must be JSON text")
    try:
        return json.loads(value)
    except json.JSONDecodeError as exc:
        raise AgentTraceAuditError(f"{label} is invalid JSON") from exc


def load_agenttrace(path: Path) -> list[dict[str, Any]]:
    verify_file(path, PARQUET_SHA256, PARQUET_SIZE)
    rows = pq.read_table(path).to_pylist()
    if len(rows) != EXPECTED_ROWS:
        raise AgentTraceAuditError(
            f"expected {EXPECTED_ROWS} AgentTrace rows, found {len(rows)}"
        )
    return rows


def load_reference(path: Path) -> list[dict[str, Any]]:
    verify_file(path, REFERENCE_SHA256, REFERENCE_SIZE)
    rows = pq.read_table(path).to_pylist()
    if len(rows) != EXPECTED_REFERENCE_ROWS:
        raise AgentTraceAuditError(
            f"expected {EXPECTED_REFERENCE_ROWS} reference rows, found {len(rows)}"
        )
    if any(set(row) != {"query", "gold"} for row in rows):
        raise AgentTraceAuditError("unexpected NL2Bash reference schema")
    return rows


def canonicalize_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Preserve source LLM and tool lanes without inventing their correlation."""

    spans = load_json_field(row.get("spans_json"), "spans_json")
    llm_steps = load_json_field(row.get("llm_steps_json"), "llm_steps_json")
    metadata = load_json_field(row.get("metadata_json"), "metadata_json")
    if not isinstance(spans, list) or not all(isinstance(item, dict) for item in spans):
        raise AgentTraceAuditError("spans_json must decode to a list of objects")
    if not isinstance(llm_steps, list) or not all(
        isinstance(item, dict) for item in llm_steps
    ):
        raise AgentTraceAuditError("llm_steps_json must decode to a list of objects")
    if not isinstance(metadata, dict):
        raise AgentTraceAuditError("metadata_json must decode to an object")

    trace_id = str(row.get("trace_id"))
    events: list[dict[str, Any]] = []
    previous_llm: str | None = None
    for sequence, step in enumerate(llm_steps):
        source_id = step.get("step_id")
        event_id = (
            f"llm:{source_id}"
            if isinstance(source_id, str) and source_id
            else f"llm:{trace_id}:{sequence:06d}"
        )
        events.append(
            {
                "event_id": event_id,
                "kind": "llm_generation",
                "lane": "llm",
                "sequence": sequence,
                "parent_event_id": previous_llm,
                "observation_status": "observed",
                "source": dict(step),
            }
        )
        previous_llm = event_id

    span_ids = {
        str(span.get("span_id"))
        for span in spans
        if isinstance(span.get("span_id"), str) and span.get("span_id")
    }
    for sequence, span in enumerate(spans):
        source_id = span.get("span_id")
        event_id = (
            f"tool:{source_id}"
            if isinstance(source_id, str) and source_id
            else f"tool:{trace_id}:{sequence:06d}"
        )
        parent = span.get("parent_span_id")
        parent_event = f"tool:{parent}" if parent in span_ids else None
        events.append(
            {
                "event_id": event_id,
                "kind": "tool_execution",
                "lane": "tool",
                "sequence": sequence,
                "parent_event_id": parent_event,
                "observation_status": "observed",
                "source": dict(span),
            }
        )

    if len(events) != len(spans) + len(llm_steps):
        raise AgentTraceAuditError("canonicalization silently changed event count")

    source = dict(row)
    return {
        "schema_version": CANONICAL_SCHEMA_VERSION,
        "trace_id": trace_id,
        "source": {
            "dataset_id": DATASET_ID,
            "dataset_revision": DATASET_REVISION,
            "dataset_name": row.get("dataset_name"),
            "task_id": row.get("task_id"),
            "model": row.get("model"),
            "adapter": "agenttrace_v0_3_0_loss_aware_v1",
        },
        "events": events,
        "loss_receipt": {
            "source_llm_steps": len(llm_steps),
            "source_tool_spans": len(spans),
            "canonical_events": len(events),
            "silently_dropped_events": 0,
            "unsupported_relations": [
                "LLM tool proposals lack a call ID that joins them to tool spans",
                "tool perf-counter timestamps cannot be ordered against LLM step durations",
                "collection completion is not task correctness",
            ],
        },
        "source_record": source,
    }


def extract_bash_command(span: Mapping[str, Any]) -> str | None:
    if span.get("tool_name") != "bash":
        return None
    encoded = span.get("tool_input")
    if not isinstance(encoded, str):
        return None
    try:
        if encoded.startswith("kwargs="):
            value = ast.literal_eval(encoded[len("kwargs=") :])
            if isinstance(value, dict) and isinstance(value.get("command"), str):
                return value["command"]
        if encoded.startswith("args="):
            value = ast.literal_eval(encoded[len("args=") :])
            if isinstance(value, tuple) and value and isinstance(value[0], str):
                return value[0]
    except (SyntaxError, ValueError):
        return None
    return None


def last_bash_command(row: Mapping[str, Any]) -> str | None:
    spans = load_json_field(row.get("spans_json"), "spans_json")
    commands = [extract_bash_command(span) for span in spans]
    present = [command for command in commands if command is not None]
    return present[-1] if present else None


def tokenize_pipeline(command: str) -> list[list[str]]:
    if not command or FORBIDDEN_TEXT.search(command):
        raise UnsupportedCommand("empty command or forbidden shell expansion")
    lexer = shlex.shlex(command, posix=True, punctuation_chars="|;&<>")
    lexer.whitespace_split = True
    lexer.commenters = ""
    try:
        tokens = list(lexer)
    except ValueError as exc:
        raise UnsupportedCommand("malformed shell quoting") from exc
    if not tokens:
        raise UnsupportedCommand("empty token stream")
    if any(token in SHELL_CONTROL for token in tokens):
        raise UnsupportedCommand("shell control operator is unsupported")
    stages: list[list[str]] = [[]]
    for token in tokens:
        if token == "|":
            if not stages[-1]:
                raise UnsupportedCommand("empty pipeline stage")
            stages.append([])
        else:
            stages[-1].append(token)
    if not stages[-1]:
        raise UnsupportedCommand("empty pipeline stage")
    return stages


def map_virtual_path(value: str, fixture_root: Path) -> str:
    for prefix in PATH_PREFIXES:
        if value == prefix or value.startswith(prefix + "/"):
            suffix = value[len(prefix) :].lstrip("/")
            if prefix == "/testdata":
                mapped = fixture_root / suffix
            else:
                mapped = fixture_root / prefix.lstrip("/") / suffix
            return str(mapped)
    return value


def validate_path(value: str, fixture_root: Path) -> None:
    if not value:
        return
    if value.startswith("-"):
        return
    if "/" not in value and value not in {".", ".."}:
        return
    path = Path(value)
    resolved = (fixture_root / path).resolve() if not path.is_absolute() else path.resolve()
    try:
        resolved.relative_to(fixture_root.resolve())
    except ValueError as exc:
        raise UnsupportedCommand("path escapes the replay fixture") from exc


def validate_stage(stage: Sequence[str], fixture_root: Path) -> list[str]:
    if not stage:
        raise UnsupportedCommand("empty stage")
    program = Path(stage[0]).name
    if stage[0] != program or program not in READ_ONLY_PROGRAMS:
        raise UnsupportedCommand(f"program is not allowlisted: {stage[0]}")
    args = [map_virtual_path(value, fixture_root) for value in stage[1:]]
    if program == "find" and any(
        value in {"-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprint"}
        or value.startswith("-exec")
        for value in args
    ):
        raise UnsupportedCommand("find mutation/execution is unsupported")
    if program == "grep" and any(
        value in {"-f", "--file", "--exclude-from"}
        or value.startswith("--file=")
        or value.startswith("--exclude-from=")
        for value in args
    ):
        raise UnsupportedCommand("grep file-driven patterns are unsupported")
    if program == "find":
        for value in args:
            if value.startswith("-") and value not in FIND_SAFE_EXPRESSIONS:
                raise UnsupportedCommand(f"unsupported find expression: {value}")
    elif program in {"basename", "dirname"}:
        if any(value.startswith("-") for value in args):
            raise UnsupportedCommand(f"{program} options are unsupported")
    else:
        safe_long = SAFE_LONG_OPTIONS.get(program, set())
        safe_short = SAFE_SHORT_OPTION_CHARS.get(program, set())
        for value in args:
            if value == "-":
                continue
            if value.startswith("--"):
                name = value.split("=", 1)[0]
                if name not in safe_long:
                    raise UnsupportedCommand(
                        f"unsupported {program} long option: {name}"
                    )
                continue
            if value.startswith("-") and len(value) > 1:
                compact = value[1:]
                # Numeric values such as ``-10`` are accepted only by head/tail.
                if compact.isdigit() and program in {"head", "tail"}:
                    continue
                if value == "-1" and program == "ls":
                    continue
                option_chars = "".join(character for character in compact if character.isalpha())
                if not option_chars or any(
                    character not in safe_short for character in option_chars
                ):
                    raise UnsupportedCommand(
                        f"unsupported {program} short option: {value}"
                    )
    for value in args:
        if "\x00" in value:
            raise UnsupportedCommand("NUL byte in argument")
        validate_path(value, fixture_root)
    binary = shutil.which(program)
    if binary is None:
        raise UnsupportedCommand(f"allowlisted program is unavailable: {program}")
    return [binary, *args]


def compile_pipeline(command: str, fixture_root: Path) -> list[list[str]]:
    return [validate_stage(stage, fixture_root) for stage in tokenize_pipeline(command)]


def execute_pipeline(
    pipeline: Sequence[Sequence[str]],
    fixture_root: Path,
    timeout_seconds: float = 2.0,
) -> CommandResult:
    """Execute a prevalidated read-only argv pipeline without a shell."""

    input_bytes: bytes | None = None
    stderr = bytearray()
    returncode = 0
    env = {
        "PATH": "/usr/bin:/bin",
        "LC_ALL": "C",
        "LANG": "C",
        "HOME": str(fixture_root),
        "TMPDIR": str(fixture_root),
    }
    for argv in pipeline:
        completed = subprocess.run(
            list(argv),
            input=input_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=fixture_root,
            env=env,
            timeout=timeout_seconds,
            check=False,
        )
        input_bytes = completed.stdout
        stderr.extend(completed.stderr)
        returncode = completed.returncode
    return CommandResult(
        returncode=returncode,
        stdout=input_bytes or b"",
        stderr=bytes(stderr),
    )


def replay_pair(
    candidate: str,
    gold: str,
    fixture_source: Path,
    timeout_seconds: float = 2.0,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="frankengate-agenttrace-replay-") as temp:
        fixture_root = Path(temp) / "fixture"
        shutil.copytree(fixture_source, fixture_root)
        candidate_error = None
        gold_error = None
        try:
            candidate_pipeline = compile_pipeline(candidate, fixture_root)
        except UnsupportedCommand as exc:
            candidate_pipeline = None
            candidate_error = str(exc)
        try:
            gold_pipeline = compile_pipeline(gold, fixture_root)
        except UnsupportedCommand as exc:
            gold_pipeline = None
            gold_error = str(exc)
        if candidate_error or gold_error:
            if candidate_error and gold_error:
                status = "candidate_and_gold_unsupported"
            elif candidate_error:
                status = "candidate_unsupported"
            else:
                status = "gold_unsupported"
            return {
                "status": status,
                "candidate_reason": candidate_error,
                "gold_reason": gold_error,
            }
        assert candidate_pipeline is not None
        assert gold_pipeline is not None
        try:
            candidate_result = execute_pipeline(
                candidate_pipeline, fixture_root, timeout_seconds
            )
            gold_result = execute_pipeline(gold_pipeline, fixture_root, timeout_seconds)
        except subprocess.TimeoutExpired:
            return {
                "status": "timeout",
                "reason": "a command exceeded the fixed replay timeout",
            }
        candidate_normalized = candidate_result.normalized(fixture_root)
        gold_normalized = gold_result.normalized(fixture_root)
        return {
            "status": "executed",
            "equivalent_stdout_and_exit": (
                candidate_normalized["returncode"] == gold_normalized["returncode"]
                and candidate_normalized["stdout_sha256"]
                == gold_normalized["stdout_sha256"]
            ),
            "candidate": candidate_normalized,
            "gold": gold_normalized,
        }


def fixture_digest(root: Path) -> dict[str, Any]:
    if not root.is_dir():
        raise AgentTraceAuditError(f"missing fixture directory: {root}")
    entries = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        entries.append(
            {
                "path": str(path.relative_to(root)),
                "size": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return {
        "files": len(entries),
        "bytes": sum(item["size"] for item in entries),
        "tree_sha256": sha256_json(entries),
    }


def analyze(
    rows: Sequence[Mapping[str, Any]],
    references: Sequence[Mapping[str, Any]],
    fixture_source: Path,
    replay_limit: int | None = None,
) -> dict[str, Any]:
    if len(rows) != EXPECTED_ROWS:
        raise AgentTraceAuditError("unexpected AgentTrace cardinality")
    if len(references) != EXPECTED_REFERENCE_ROWS:
        raise AgentTraceAuditError("unexpected reference cardinality")

    dataset_counts: collections.Counter[str] = collections.Counter()
    model_counts: collections.Counter[str] = collections.Counter()
    tool_counts: collections.Counter[str] = collections.Counter()
    exit_counts: collections.Counter[str] = collections.Counter()
    metadata_schema_counts: collections.Counter[str] = collections.Counter()
    source_llm_steps = 0
    source_tool_spans = 0
    explicit_parent_edges = 0
    llm_tool_proposals = 0
    canonical_events = 0
    silent_drops = 0
    source_hashes = []
    nl2bash_rows: list[Mapping[str, Any]] = []

    for row in rows:
        canonical = canonicalize_row(row)
        if canonical["source_record"] != dict(row):
            raise AgentTraceAuditError("canonical adapter mutated the source row")
        receipt = canonical["loss_receipt"]
        source_llm_steps += receipt["source_llm_steps"]
        source_tool_spans += receipt["source_tool_spans"]
        canonical_events += receipt["canonical_events"]
        silent_drops += receipt["silently_dropped_events"]
        source_hashes.append(sha256_json(dict(row)))
        dataset_counts[str(row.get("dataset_name"))] += 1
        model_counts[str(row.get("model"))] += 1
        metadata = load_json_field(row.get("metadata_json"), "metadata_json")
        metadata_schema_counts[str(metadata.get("schema_version"))] += 1
        spans = load_json_field(row.get("spans_json"), "spans_json")
        steps = load_json_field(row.get("llm_steps_json"), "llm_steps_json")
        for span in spans:
            tool_counts[str(span.get("tool_name"))] += 1
            exit_counts[str(span.get("exit_code"))] += 1
            explicit_parent_edges += int(bool(span.get("parent_span_id")))
        for step in steps:
            calls = step.get("tool_calls")
            if isinstance(calls, list):
                llm_tool_proposals += len(calls)
        if row.get("dataset_name") == "nl2bash":
            nl2bash_rows.append(row)

    if len(nl2bash_rows) != EXPECTED_NL2BASH_ROWS:
        raise AgentTraceAuditError("unexpected NL2Bash trace count")

    task_model_counts = collections.Counter(
        (int(row["task_id"]), str(row["model"])) for row in nl2bash_rows
    )
    duplicate_task_model = sum(count - 1 for count in task_model_counts.values())
    missing_task_ids = sorted(
        set(range(EXPECTED_REFERENCE_ROWS))
        - {int(row["task_id"]) for row in nl2bash_rows}
    )
    if duplicate_task_model or missing_task_ids:
        raise AgentTraceAuditError("NL2Bash task/model coverage is not complete")

    selected = sorted(
        nl2bash_rows,
        key=lambda row: (
            int(row["task_id"]),
            str(row["model"]),
            str(row["trace_id"]),
        ),
    )
    if replay_limit is not None:
        selected = selected[:replay_limit]

    replay_status: collections.Counter[str] = collections.Counter()
    unsupported_reasons: collections.Counter[str] = collections.Counter()
    executed = 0
    equivalent = 0
    no_bash = 0
    per_model: dict[str, collections.Counter[str]] = collections.defaultdict(
        collections.Counter
    )
    replay_receipts = []
    for row in selected:
        task_id = int(row["task_id"])
        candidate = last_bash_command(row)
        model = str(row["model"])
        per_model[model]["selected"] += 1
        if candidate is None:
            no_bash += 1
            replay_status["no_historical_bash_command"] += 1
            per_model[model]["no_historical_bash_command"] += 1
            continue
        gold = references[task_id]["gold"]
        if not isinstance(gold, str):
            raise AgentTraceAuditError("reference gold command must be text")
        receipt = replay_pair(candidate, gold, fixture_source)
        replay_status[receipt["status"]] += 1
        per_model[model][receipt["status"]] += 1
        if receipt["status"].endswith("unsupported"):
            if receipt.get("candidate_reason"):
                unsupported_reasons[
                    "candidate: " + str(receipt["candidate_reason"])
                ] += 1
            if receipt.get("gold_reason"):
                unsupported_reasons["gold: " + str(receipt["gold_reason"])] += 1
        if receipt["status"] == "executed":
            executed += 1
            equivalent += int(receipt["equivalent_stdout_and_exit"])
            per_model[model]["equivalent"] += int(
                receipt["equivalent_stdout_and_exit"]
            )
        replay_receipts.append(
            {
                "task_model_sha256": sha256_json([task_id, model]),
                "candidate_command_sha256": sha256_bytes(
                    candidate.encode("utf-8", errors="replace")
                ),
                "gold_command_sha256": sha256_bytes(gold.encode("utf-8")),
                "status": receipt["status"],
                "equivalent_stdout_and_exit": receipt.get(
                    "equivalent_stdout_and_exit"
                ),
            }
        )

    replay_receipts.sort(key=lambda item: item["task_model_sha256"])
    model_rows = []
    for model, counts in sorted(per_model.items()):
        model_executed = counts["executed"]
        model_rows.append(
            {
                "model": model,
                "selected": counts["selected"],
                "executed": model_executed,
                "equivalent": counts["equivalent"],
                "equivalence_rate_among_executed": (
                    counts["equivalent"] / model_executed
                    if model_executed
                    else None
                ),
                "candidate_unsupported": counts["candidate_unsupported"],
                "gold_unsupported": counts["gold_unsupported"],
                "candidate_and_gold_unsupported": counts[
                    "candidate_and_gold_unsupported"
                ],
                "timeout": counts["timeout"],
                "no_historical_bash_command": counts[
                    "no_historical_bash_command"
                ],
            }
        )

    result = {
        "schema_version": SCHEMA_VERSION,
        "run_date": "2026-07-30",
        "source": {
            "dataset_id": DATASET_ID,
            "dataset_revision": DATASET_REVISION,
            "license": DATASET_LICENSE,
            "parquet_sha256": PARQUET_SHA256,
            "parquet_size_bytes": PARQUET_SIZE,
            "reference_dataset_id": REFERENCE_ID,
            "reference_revision": REFERENCE_REVISION,
            "reference_license": REFERENCE_LICENSE,
            "reference_sha256": REFERENCE_SHA256,
            "reference_size_bytes": REFERENCE_SIZE,
        },
        "corpus": {
            "rows": len(rows),
            "dataset_counts": dict(sorted(dataset_counts.items())),
            "model_counts": dict(sorted(model_counts.items())),
            "metadata_schema_counts": dict(sorted(metadata_schema_counts.items())),
            "source_record_set_sha256": sha256_json(sorted(source_hashes)),
            "fixture": fixture_digest(fixture_source),
        },
        "projection": {
            "source_llm_steps": source_llm_steps,
            "source_tool_spans": source_tool_spans,
            "canonical_events": canonical_events,
            "silently_dropped_events": silent_drops,
            "explicit_tool_parent_edges": explicit_parent_edges,
            "llm_tool_proposals": llm_tool_proposals,
            "proposal_to_execution_join_ids": 0,
            "tool_counts": dict(sorted(tool_counts.items())),
            "exit_code_counts": dict(sorted(exit_counts.items())),
        },
        "nl2bash_replay": {
            "reference_tasks": len(references),
            "historical_rows": len(nl2bash_rows),
            "selected_rows": len(selected),
            "task_model_duplicates": duplicate_task_model,
            "missing_task_ids": missing_task_ids,
            "status_counts": dict(sorted(replay_status.items())),
            "unsupported_reasons": dict(sorted(unsupported_reasons.items())),
            "executed_rows": executed,
            "equivalent_rows": equivalent,
            "equivalence_rate_among_executed": (
                equivalent / executed if executed else None
            ),
            "no_historical_bash_command": no_bash,
            "per_model": model_rows,
            "receipt_set_sha256": sha256_json(replay_receipts),
            "executor": {
                "shell": false_value(),
                "fixed_read_only_programs": sorted(READ_ONLY_PROGRAMS),
                "fixture_copy_per_pair": True,
                "timeout_seconds": 2.0,
                "network_enabled_by_executor": False,
                "arbitrary_commands_supported": False,
            },
        },
        "claim_boundary": {
            "collection_completion_is_task_correctness": False,
            "gold_command_is_expected_state_digest": False,
            "stdout_exit_equivalence_is_semantic_equivalence": False,
            "causal_memory_replay_completed": False,
            "why_not": [
                "the release has no task-correctness verdict",
                "the upstream reference has a gold command but no expected stdout or filesystem-state digest",
                "the historical traces contain no memory or procedure intervention",
                "model sampling seeds are absent",
                "tool proposals and executions have no shared call ID",
            ],
            "next_gate": (
                "instrument 40 tasks with verifier-owned stdout/state digests, "
                "frozen model and sampling seeds, and no-memory/relevant/placebo/"
                "curated procedure arms"
            ),
        },
    }
    result["result_content_sha256"] = sha256_json(result)
    return result


def false_value() -> bool:
    """Keep JSON booleans visually explicit at their call site."""

    return False


def render_summary(result: Mapping[str, Any]) -> str:
    replay = result["nl2bash_replay"]
    projection = result["projection"]
    corpus = result["corpus"]
    rows = "\n".join(
        "| {model} | {selected} | {executed} | {equivalent} | {rate} | "
        "{unsupported} | {missing} |".format(
            model=item["model"],
            selected=item["selected"],
            executed=item["executed"],
            equivalent=item["equivalent"],
            rate=(
                f"{item['equivalence_rate_among_executed']:.3f}"
                if item["equivalence_rate_among_executed"] is not None
                else "n/a"
            ),
            unsupported=(
                item["candidate_unsupported"]
                + item["gold_unsupported"]
                + item["candidate_and_gold_unsupported"]
                + item["timeout"]
            ),
            missing=item["no_historical_bash_command"],
        )
        for item in replay["per_model"]
    )
    return f"""# AgentTrace loss-aware admission and NL2Bash replay audit

**Run date:** {result['run_date']}

**Source:** [{result['source']['dataset_id']} @
`{result['source']['dataset_revision']}`](https://huggingface.co/datasets/pagarsky/agent-trace/tree/{result['source']['dataset_revision']}),
{result['source']['license']}

## Bottom line

AgentTrace is a useful tool-telemetry and bounded replay corpus, but it is not
the causal-memory benchmark the research plan previously assumed.

All {corpus['rows']:,} source rows, {projection['source_llm_steps']:,} LLM steps,
and {projection['source_tool_spans']:,} tool spans project to
{projection['canonical_events']:,} canonical lane events with zero silent loss.
However, {projection['llm_tool_proposals']:,} LLM tool proposals have zero shared
call IDs with executions, and the release contains collection completion rather
than a task-correctness verdict.

The bounded executor attempted {replay['selected_rows']:,} historical
NL2Bash task/model rows. It safely executed both the last recorded bash command
and the pinned upstream gold command for {replay['executed_rows']:,} rows;
{replay['equivalent_rows']:,} had identical stdout and exit status
({replay['equivalence_rate_among_executed']:.3f} among executable rows).
Unsupported shell constructs remain refused. This is a deterministic task proxy,
not proof of semantic correctness.

## Corpus and representation

- 1,400 traces: 1,000 MBPP and 400 NL2Bash.
- Two model strata: {stable_json(corpus['model_counts'])}.
- {projection['source_tool_spans']:,} tool spans:
  {stable_json(projection['tool_counts'])}.
- {projection['explicit_tool_parent_edges']} explicit tool-parent edges.
- Fixture: {corpus['fixture']['files']} files,
  tree digest `{corpus['fixture']['tree_sha256']}`.
- Raw traces, prompts, commands, outputs, and fixture contents remain outside Git.

## Bounded replay results

| Model | Selected | Executed | Equivalent | Rate | Unsupported/timeout | No bash |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
{rows}

Status counts: `{stable_json(replay['status_counts'])}`.

The executor uses fixed binaries and argument vectors; it never invokes a shell,
disables arbitrary commands by construction, rejects mutation/execution flags,
validates paths against a fresh fixture copy, and records only aggregate hashes.
It does not claim OS-level isolation.

## Why this does not complete E6

1. AgentTrace has no independent task-correctness field.
2. The upstream MIT reference provides a gold command, not an expected stdout or
   filesystem-state digest.
3. Historical traces contain no no-memory, relevant, placebo, or curated
   procedure exposure.
4. Model sampling seeds are absent.
5. A matching stdout and exit code can still be semantically incomplete.

The earlier plan's statement that AgentTrace already provides a deterministic
task verifier was too strong. The next experiment must add verifier-owned output
and state digests, frozen seeds, and the four intervention arms before reporting
a causal procedural-memory effect.

## Reproduce

Keep the two pinned datasets outside Git, then run:

```bash
python agenttrace_replay_audit.py \\
  --agenttrace /private/research-cache/agenttrace/data/agenttrace.parquet \\
  --reference /private/research-cache/nl2bash/data/train.parquet \\
  --fixture /private/research-cache/agenttrace/testdata \\
  --output-json experiments/results/agenttrace-nl2bash-replay-audit-2026-07-30.json \\
  --output-markdown experiments/summaries/agenttrace-nl2bash-replay-audit-2026-07-30.md
```

Result content hash: `{result['result_content_sha256']}`.
"""


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agenttrace", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path, required=True)
    parser.add_argument("--replay-limit", type=int)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    result = analyze(
        load_agenttrace(args.agenttrace),
        load_reference(args.reference),
        args.fixture,
        replay_limit=args.replay_limit,
    )
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_markdown.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    args.output_markdown.write_text(render_summary(result), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
