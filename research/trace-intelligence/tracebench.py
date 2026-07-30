#!/usr/bin/env python3
"""Dependency-free pilot harness for public agent trajectories.

The current adapter is intentionally conservative. SWE-agent encodes commands and
environment responses inside alternating chat messages. We preserve every source
message and mark tool semantics as reconstructed rather than pretending they were
observed OpenTelemetry spans.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "trace-pilot-result-v1"
CANONICAL_SCHEMA_VERSION = "canonical-trajectory-v1"
DATASET_ID = "nebius/SWE-agent-trajectories"
DATASET_REVISION = "68195a1450865274106246d0d0296a1d6807b88e"
ADAPTER = "nebius_swe_agent_v1"

FENCED_BLOCK_RE = re.compile(r"```(?:[A-Za-z0-9_+.-]+)?\s*\n(.*?)```", re.DOTALL)
ERROR_PATTERNS = {
    "syntax_error": re.compile(
        r"\b(?:syntaxerror|syntax error|parse error|introduced new syntax error)\b",
        re.IGNORECASE,
    ),
    "not_found": re.compile(
        r"\b(?:not found|no such file|directory .* not found|cannot open)\b",
        re.IGNORECASE,
    ),
    "permission_error": re.compile(
        r"\b(?:permission denied|forbidden|unauthorized|http(?:error)?[: ]+40[13])\b",
        re.IGNORECASE,
    ),
    "test_failure": re.compile(
        r"\b(?:failed|failure|errors?)\b|={2,}\s*\d+\s+failed",
        re.IGNORECASE,
    ),
}


def stable_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def extract_command(text: str | None) -> str | None:
    if not text:
        return None
    blocks = FENCED_BLOCK_RE.findall(text)
    if not blocks:
        return None
    lines = [line.strip() for line in blocks[-1].splitlines() if line.strip()]
    return "\n".join(lines) if lines else None


def normalize_command(command: str) -> str:
    value = command.strip().lower()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"\b\d+\b", "<n>", value)
    return value


def canonicalize_nebius(row: dict[str, Any]) -> dict[str, Any]:
    trajectory = row.get("trajectory") or []
    trace_material = {
        "instance_id": row.get("instance_id"),
        "model_name": row.get("model_name"),
        "trajectory": trajectory,
        "generated_patch": row.get("generated_patch"),
        "eval_logs": row.get("eval_logs"),
    }
    trace_id = sha256_text(stable_json(trace_material))

    events: list[dict[str, Any]] = []
    previous_event_id: str | None = None
    previous_had_command = False
    reconstructed_fields: set[str] = set()

    for sequence, source_event in enumerate(trajectory):
        source_role = str(source_event.get("role") or "unknown")
        content = source_event.get("text")
        if content is None:
            content = source_event.get("system_prompt")
        command = extract_command(content) if source_role == "ai" else None

        if source_role == "system":
            kind = "system_instruction"
            observation_status = "observed"
        elif source_role == "ai" and command:
            kind = "tool_call_proposal"
            observation_status = "reconstructed"
            reconstructed_fields.update(("events.kind", "events.command"))
        elif source_role == "ai":
            kind = "agent_message"
            observation_status = "observed"
        elif source_role == "user" and previous_had_command:
            kind = "tool_result"
            observation_status = "reconstructed"
            reconstructed_fields.add("events.kind")
        elif source_role == "user":
            kind = "task_input"
            observation_status = "observed"
        else:
            kind = "unknown_message"
            observation_status = "observed"

        event_id = f"{trace_id[:16]}:{sequence:06d}"
        events.append(
            {
                "event_id": event_id,
                "sequence": sequence,
                "kind": kind,
                "observation_status": observation_status,
                "source_role": source_role,
                "content": content,
                "command": command,
                "parent_event_id": previous_event_id,
                "source": {
                    "mask": source_event.get("mask"),
                    "cutoff_date": source_event.get("cutoff_date"),
                },
            }
        )
        previous_event_id = event_id
        previous_had_command = bool(command)

    return {
        "schema_version": CANONICAL_SCHEMA_VERSION,
        "trace_id": trace_id,
        "source": {
            "dataset_id": DATASET_ID,
            "dataset_revision": DATASET_REVISION,
            "adapter": ADAPTER,
            "model_name": row.get("model_name"),
        },
        "task": {"task_id": row.get("instance_id")},
        "events": events,
        "artifacts": {
            "exit_status": row.get("exit_status"),
            "generated_patch": row.get("generated_patch"),
            "eval_logs": row.get("eval_logs"),
        },
        "outcome": {
            "value": bool(row.get("target")),
            "source": "dataset_external_evaluation",
        },
        "loss_receipt": {
            "source_event_count": len(trajectory),
            "canonical_event_count": len(events),
            "silently_dropped_event_count": 0,
            "reconstructed_fields": sorted(reconstructed_fields),
            "known_missing_fields": [
                "timestamps",
                "explicit_tool_call_ids",
                "authorization_decisions",
                "tool_latency",
                "provider_request_ids",
                "branch_edges",
            ],
            "source_fields_preserved": [
                "instance_id",
                "model_name",
                "target",
                "trajectory",
                "exit_status",
                "generated_patch",
                "eval_logs",
            ],
        },
    }


def error_classes(text: str | None) -> set[str]:
    if not text:
        return set()
    return {name for name, pattern in ERROR_PATTERNS.items() if pattern.search(text)}


def deterministic_signals(trace: dict[str, Any]) -> dict[str, float]:
    """Compute label-blind friction features.

    This function must not read ``trace["outcome"]``. The conformance tests flip the
    outcome and require bit-identical signals.
    """

    events = trace["events"]
    commands: list[str] = []
    result_classes: list[set[str]] = []
    result_texts: list[str] = []
    counts: Counter[str] = Counter()

    for event in events:
        if event.get("command"):
            commands.append(normalize_command(event["command"]))
        if event.get("kind") == "tool_result":
            text = event.get("content") or ""
            classes = error_classes(text)
            result_classes.append(classes)
            result_texts.append(re.sub(r"\s+", " ", text.strip().lower())[:500])
            for item in classes:
                counts[item] += 1

    command_counts = Counter(commands)
    repeated_actions = sum(value - 1 for value in command_counts.values() if value > 1)
    immediate_repeats = sum(
        1 for left, right in zip(commands, commands[1:]) if left == right
    )
    repeated_results = sum(
        1 for left, right in zip(result_texts, result_texts[1:]) if left and left == right
    )
    repeated_error_class = sum(
        1
        for left, right in zip(result_classes, result_classes[1:])
        if left and right and left == right
    )
    edit_rejections = sum(
        1
        for event in events
        if "proposed edit has introduced new syntax error"
        in (event.get("content") or "").lower()
    )
    characters = sum(len(event.get("content") or "") for event in events)

    # Fixed before outcome inspection. This is a screening score, not a diagnosis.
    friction_score = (
        1.0 * counts["syntax_error"]
        + 0.75 * counts["not_found"]
        + 1.0 * counts["permission_error"]
        + 0.35 * counts["test_failure"]
        + 1.5 * immediate_repeats
        + 0.75 * repeated_actions
        + 1.25 * repeated_results
        + 1.0 * repeated_error_class
        + 1.5 * edit_rejections
    )

    return {
        "turn_count": float(len(events)),
        "character_count": float(characters),
        "tool_action_count": float(len(commands)),
        "syntax_error_count": float(counts["syntax_error"]),
        "not_found_count": float(counts["not_found"]),
        "permission_error_count": float(counts["permission_error"]),
        "test_failure_count": float(counts["test_failure"]),
        "repeated_action_count": float(repeated_actions),
        "immediate_repeat_count": float(immediate_repeats),
        "repeated_result_count": float(repeated_results),
        "repeated_error_class_count": float(repeated_error_class),
        "edit_rejection_count": float(edit_rejections),
        "friction_score": float(friction_score),
    }


def mean(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else math.nan


def auroc(rows: list[dict[str, Any]], score_name: str) -> float:
    positive = [row[score_name] for row in rows if row["failed"]]
    negative = [row[score_name] for row in rows if not row["failed"]]
    if not positive or not negative:
        return math.nan
    wins = 0.0
    for pos in positive:
        for neg in negative:
            if pos > neg:
                wins += 1.0
            elif pos == neg:
                wins += 0.5
    return wins / (len(positive) * len(negative))


def fixed_budget_metrics(
    rows: list[dict[str, Any]], score_name: str, budget_fraction: float
) -> dict[str, float | int]:
    budget = max(1, math.ceil(len(rows) * budget_fraction))
    ranked = sorted(
        rows,
        key=lambda row: (-row[score_name], row["trace_id"]),
    )
    selected = ranked[:budget]
    failures = sum(1 for row in rows if row["failed"])
    selected_failures = sum(1 for row in selected if row["failed"])
    base_rate = failures / len(rows)
    precision = selected_failures / budget
    return {
        "budget_records": budget,
        "precision_failure_proxy": precision,
        "failure_recall": selected_failures / failures if failures else math.nan,
        "base_failure_rate": base_rate,
        "enrichment_percentage_points": 100.0 * (precision - base_rate),
        "auroc_failure_proxy": auroc(rows, score_name),
    }


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return math.nan
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def task_cluster_bootstrap(
    rows: list[dict[str, Any]],
    score_names: list[str],
    budget_fraction: float,
    replicates: int = 1000,
    seed: int = 20260730,
) -> dict[str, Any]:
    by_task: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_task[row["task_id"]].append(row)
    task_ids = sorted(by_task)
    rng = random.Random(seed)
    samples: dict[str, defaultdict[str, list[float]]] = {
        name: defaultdict(list) for name in score_names
    }
    paired: defaultdict[str, list[float]] = defaultdict(list)

    for replicate in range(replicates):
        resampled: list[dict[str, Any]] = []
        for slot in range(len(task_ids)):
            task_id = rng.choice(task_ids)
            for row in by_task[task_id]:
                copy = dict(row)
                copy["trace_id"] = f"{replicate}:{slot}:{row['trace_id']}"
                resampled.append(copy)
        metrics = {
            name: fixed_budget_metrics(resampled, name, budget_fraction)
            for name in score_names
        }
        for name, values in metrics.items():
            for metric in (
                "precision_failure_proxy",
                "enrichment_percentage_points",
                "auroc_failure_proxy",
            ):
                samples[name][metric].append(float(values[metric]))
        if len(score_names) == 2:
            left, right = score_names
            for metric in (
                "precision_failure_proxy",
                "enrichment_percentage_points",
                "auroc_failure_proxy",
            ):
                paired[metric].append(
                    float(metrics[left][metric]) - float(metrics[right][metric])
                )

    intervals = {}
    for name, metrics in samples.items():
        intervals[name] = {
            metric: {
                "lower_95": percentile(values, 0.025),
                "upper_95": percentile(values, 0.975),
            }
            for metric, values in metrics.items()
        }
    paired_intervals = {
        metric: {
            "left_minus_right": f"{score_names[0]} - {score_names[1]}",
            "lower_95": percentile(values, 0.025),
            "upper_95": percentile(values, 0.975),
        }
        for metric, values in paired.items()
    }
    return {
        "method": "task-cluster bootstrap",
        "replicates": replicates,
        "seed": seed,
        "intervals": intervals,
        "paired_difference_intervals": paired_intervals,
    }


def analyze(rows: list[dict[str, Any]], input_sha256: str) -> dict[str, Any]:
    analyzed: list[dict[str, Any]] = []
    loss_totals = Counter()
    task_outcomes: defaultdict[str, Counter[str]] = defaultdict(Counter)

    for row in rows:
        trace = canonicalize_nebius(row)
        signals = deterministic_signals(trace)
        failed = not trace["outcome"]["value"]
        analyzed.append(
            {
                "trace_id": trace["trace_id"],
                "task_id": trace["task"]["task_id"],
                "failed": failed,
                **signals,
            }
        )
        receipt = trace["loss_receipt"]
        loss_totals["source_events"] += receipt["source_event_count"]
        loss_totals["canonical_events"] += receipt["canonical_event_count"]
        loss_totals["silently_dropped_events"] += receipt[
            "silently_dropped_event_count"
        ]
        task_outcomes[str(trace["task"]["task_id"])][
            "failure" if failed else "success"
        ] += 1

    signal_names = [
        name
        for name in analyzed[0]
        if name not in {"trace_id", "task_id", "failed"}
    ]
    by_outcome = {
        signal: {
            "failure_mean": mean(
                row[signal] for row in analyzed if row["failed"]
            ),
            "success_mean": mean(
                row[signal] for row in analyzed if not row["failed"]
            ),
        }
        for signal in signal_names
    }
    matched_tasks = sum(
        1
        for counts in task_outcomes.values()
        if counts["failure"] > 0 and counts["success"] > 0
    )

    score_names = ["friction_score", "turn_count"]
    bootstrap = task_cluster_bootstrap(
        analyzed,
        score_names=score_names,
        budget_fraction=0.20,
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "study": "nebius-swe-agent-matched-outcome-proxy-pilot",
        "claims": {
            "supported": [
                "source turns can be preserved while reconstructed tool semantics remain explicit",
                "label-blind signals can be compared with an external outcome proxy within matched tasks",
            ],
            "not_supported": [
                "diagnostic informativeness",
                "decisive-step localization",
                "causal recovery",
                "person-level skill inference",
                "enterprise transfer",
            ],
        },
        "input": {
            "dataset_id": DATASET_ID,
            "dataset_revision": DATASET_REVISION,
            "sha256": input_sha256,
            "records": len(rows),
            "task_ids": len(task_outcomes),
            "matched_task_ids": matched_tasks,
            "successes": sum(1 for row in analyzed if not row["failed"]),
            "failures": sum(1 for row in analyzed if row["failed"]),
        },
        "canonicalization": {
            **loss_totals,
            "source_event_preservation_rate": (
                loss_totals["canonical_events"] / loss_totals["source_events"]
                if loss_totals["source_events"]
                else math.nan
            ),
            "tool_semantics_status": "reconstructed_from_chat_messages",
            "gate_passed": loss_totals["silently_dropped_events"] == 0
            and loss_totals["source_events"] == loss_totals["canonical_events"],
        },
        "fixed_review_budget_fraction": 0.20,
        "arms": {
            "length_heuristic": fixed_budget_metrics(
                analyzed, "turn_count", budget_fraction=0.20
            ),
            "deterministic_friction_score": fixed_budget_metrics(
                analyzed, "friction_score", budget_fraction=0.20
            ),
        },
        "uncertainty": bootstrap,
        "signal_means_by_external_outcome": by_outcome,
        "method_notes": [
            "Signals are computed without reading target/outcome.",
            "Failure is only an outcome proxy, not a gold informative-trace label.",
            "The sample is deliberately balanced and matched; prevalence is not estimated.",
            "Tool call/result kinds are reconstructed because the source is not OTel.",
            "No model API, embedding, or LLM judge is used in this pilot.",
        ],
    }


def load_jsonl(path: Path) -> tuple[list[dict[str, Any]], str]:
    raw = path.read_bytes()
    rows = [
        json.loads(line)
        for line in raw.decode("utf-8").splitlines()
        if line.strip()
    ]
    if not rows:
        raise ValueError("input contains no records")
    return rows, hashlib.sha256(raw).hexdigest()


def pilot(input_path: Path, output_path: Path | None) -> dict[str, Any]:
    rows, input_sha256 = load_jsonl(input_path)
    result = analyze(rows, input_sha256)
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if output_path:
        output_path.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    pilot_parser = subparsers.add_parser(
        "pilot", help="run canonicalization and deterministic signal pilot"
    )
    pilot_parser.add_argument("--input", type=Path, required=True)
    pilot_parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "pilot":
        pilot(args.input, args.output)
        return 0
    raise AssertionError(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
