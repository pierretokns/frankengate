"""Extract and audit a procedure candidate from natural agent traces.

This is an offline, content-minimized diagnostic.  It accepts Claude Code
JSONL and Codex JSONL, reduces tool calls to protocol predicates, and compares
those predicates with the source run status.  It cannot establish that the
candidate caused success: the historical traces were not randomized, and no
candidate was injected into a replay.  A causal claim requires the separate
no-skill/placebo/mined intervention runner.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping


SCHEMA_VERSION = "frankengate-natural-trace-skill-candidate-audit-v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


@dataclass(frozen=True)
class ToolEvent:
    name: str
    arguments: Mapping[str, Any]


def _json_object(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _claude_events(row: Mapping[str, Any]) -> Iterable[ToolEvent]:
    if row.get("type") != "assistant":
        return ()
    message = _json_object(row.get("message"))
    values = message.get("content")
    if not isinstance(values, list):
        return ()
    output: list[ToolEvent] = []
    for value in values:
        item = _json_object(value)
        if item.get("type") == "tool_use":
            output.append(
                ToolEvent(str(item.get("name", "unknown")), _json_object(item.get("input")))
            )
    return output


def _codex_events(row: Mapping[str, Any]) -> Iterable[ToolEvent]:
    if row.get("type") != "response_item":
        return ()
    payload = _json_object(row.get("payload"))
    if payload.get("type") != "function_call":
        return ()
    name = str(payload.get("name", "unknown"))
    raw = payload.get("arguments")
    if isinstance(raw, str):
        try:
            arguments = _json_object(json.loads(raw))
        except json.JSONDecodeError:
            arguments = {}
    else:
        arguments = _json_object(raw)
    return (ToolEvent(name, arguments),)


def load_tool_events(path: Path) -> list[ToolEvent]:
    events: list[ToolEvent] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, Mapping):
                continue
            events.extend(_claude_events(row))
            events.extend(_codex_events(row))
    return events


def _argument_text(event: ToolEvent) -> str:
    return json.dumps(event.arguments, ensure_ascii=False, sort_keys=True).lower()


def protocol_predicates(events: list[ToolEvent]) -> dict[str, bool | int]:
    """Evaluate the frozen candidate procedure without retaining content."""

    names = [event.name.lower() for event in events]
    texts = [_argument_text(event) for event in events]
    combined = "\n".join(texts)
    read_problem = (
        "read" in names
        and "/task/problem/readme.md" in combined
        and "/task/problem/data_description.md" in combined
    )
    inspect_data = any(
        token in combined for token in ("/task/problem/data", "train.csv", "test_input.csv")
    ) and any(token in names for token in ("bash", "exec_command", "read", "glob", "grep"))
    runtime_check = any(
        token in combined for token in ("health", "nvidia-smi", "torch", "time_remaining", "pip list")
    )
    writes_artifact = any(
        name in {"write", "edit", "bash", "exec_command"}
        and any(token in text for token in ("/workspace", "run.py", "output", "submission"))
        for name, text in zip(names, texts)
    )
    validates_or_evaluates = any(
        token in combined for token in ("evaluate", "evaluation", "score", "validate", "submission", "submit")
    )
    iterates = sum(name in {"edit", "write", "bash", "exec_command"} for name in names) >= 5
    required = (read_problem, inspect_data, runtime_check, writes_artifact, validates_or_evaluates)
    return {
        "tool_events": len(events),
        "read_problem_and_schema": read_problem,
        "inspect_task_data": inspect_data,
        "check_runtime_or_budget": runtime_check,
        "write_or_edit_artifact": writes_artifact,
        "evaluate_or_verify_output": validates_or_evaluates,
        "iterate_after_inspection": iterates,
        "candidate_protocol_score": sum(required) / len(required),
        "candidate_protocol_complete": all(required),
    }


def audit(source: tuple[str, Path, Path], targets: list[tuple[str, Path, Path | None]]) -> dict[str, Any]:
    source_label, source_trace, source_result = source
    rows: list[dict[str, Any]] = []

    def add(label: str, trace: Path | None, result: Path, role: str) -> None:
        result_payload = json.loads(result.read_text(encoding="utf-8"))
        status = str(result_payload.get("status", "unknown"))
        row: dict[str, Any] = {
            "label": label,
            "role": role,
            "status": status,
            "result_sha256": _sha256(result),
            "trace_available": trace is not None and trace.is_file() if trace else False,
        }
        if trace is None or not trace.is_file():
            row["typed_null"] = "transcript unavailable; no protocol score"
        else:
            row["trace_sha256"] = _sha256(trace)
            row["protocol"] = protocol_predicates(load_tool_events(trace))
        rows.append(row)

    add(source_label, source_trace, source_result, "candidate_source")
    for label, result, trace in targets:
        add(label, trace, result, "transfer_target")

    observed = [row for row in rows if "protocol" in row]
    complete = sum(bool(row["protocol"]["candidate_protocol_complete"]) for row in observed)
    success_observed = [row for row in observed if row["status"] == "success"]
    return {
        "schema_version": SCHEMA_VERSION,
        "candidate": {
            "name": "research-task-orchestration-v1",
            "source_role": source_label,
            "steps": [
                "inspect problem statement and data schema",
                "inspect task data",
                "check runtime, budget, and available tools",
                "write or edit a reproducible artifact",
                "evaluate or verify the output",
                "iterate after inspection",
            ],
        },
        "rows": rows,
        "aggregate": {
            "run_count": len(rows),
            "transcript_observed_count": len(observed),
            "transcript_typed_null_count": len(rows) - len(observed),
            "complete_protocol_count": complete,
            "complete_protocol_rate": complete / len(observed) if observed else None,
            "successful_runs_with_observed_protocol": len(success_observed),
        },
        "claim_boundary": {
            "candidate_extracted": True,
            "cross_harness_protocol_observed": any(
                label.startswith("codex") for label, _, _ in targets if label.startswith("codex")
            ) and any(row["trace_available"] for row in rows if row["label"].startswith("codex")),
            "skill_improvement_confirmed": False,
            "causal_intervention_run": False,
            "reason": "Protocol adherence is a historical diagnostic. Model, harness, task, and timeout are confounded; no candidate was injected and no independent outcome was rerun.",
            "next_required": "Run the candidate, no-skill, placebo, expert, SkillOpt, SkillGen, and RHO arms on a family-disjoint replay with an independent verifier.",
        },
        "raw_trace_policy": "raw transcripts remain external; only hashes, statuses, predicates, and aggregates are durable",
    }


def _spec(value: str, allow_missing: bool = False) -> tuple[str, Path, Path | None]:
    parts = value.split("=", 2)
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("spec must be LABEL=TRACE=RESULT")
    label, trace_raw, result_raw = parts
    trace = None if allow_missing and trace_raw == "-" else Path(trace_raw)
    return label, Path(result_raw), trace


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="LABEL=TRACE=RESULT")
    parser.add_argument("--target", action="append", default=[], help="LABEL=TRACE|-=RESULT")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    source_label, source_result, source_trace = _spec(args.source)
    targets: list[tuple[str, Path, Path | None]] = []
    for raw in args.target:
        label, result, trace = _spec(raw, allow_missing=True)
        targets.append((label, result, trace))
    receipt = audit((source_label, source_trace, source_result), targets)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "run_count": receipt["aggregate"]["run_count"], "skill_improvement_confirmed": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
