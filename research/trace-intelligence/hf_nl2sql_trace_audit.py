#!/usr/bin/env python3
"""Audit pinned Hugging Face NL2SQL traces without emitting trace content.

The audit intentionally separates:

* a recorded action/observation corpus;
* a gold-linked retrospective corpus;
* an environment that can be reconstructed and rerun; and
* a self-contained replay snapshot.

Those are materially different evidence classes.  Output is aggregate-only:
prompts, SQL, tool arguments, observations, task identifiers, and trace
identifiers are never emitted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "hf-nl2sql-trace-audit-result-v1"
ENGINE_VERSION = "hf-nl2sql-trace-audit-v1"


class AuditError(ValueError):
    """Raised when a pinned input fails structural or hash validation."""


def stable_json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AuditError(f"cannot load {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise AuditError(f"{path}: expected a JSON object")
    return value


def _load_jsonl(path: Path) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    malformed = 0
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise AuditError(f"cannot read {path}: {exc}") from exc
    for line in lines:
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if not isinstance(value, dict):
            malformed += 1
            continue
        rows.append(value)
    return rows, malformed


def _attribute_value(raw: Any) -> Any:
    if not isinstance(raw, dict):
        return None
    for key in (
        "stringValue",
        "intValue",
        "doubleValue",
        "boolValue",
        "bytesValue",
        "arrayValue",
        "kvlistValue",
    ):
        if key in raw:
            return raw[key]
    return None


def _attributes(span: dict[str, Any]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    raw_attributes = span.get("attributes", [])
    if not isinstance(raw_attributes, list):
        return values
    for raw in raw_attributes:
        if not isinstance(raw, dict) or not isinstance(raw.get("key"), str):
            continue
        values[raw["key"]] = _attribute_value(raw.get("value"))
    return values


def _base_task_id(metadata: dict[str, Any]) -> str | None:
    value = metadata.get("base_task_id", metadata.get("task_id"))
    if not isinstance(value, str) or not value:
        return None
    return value.split("#", 1)[0]


def _load_tasks(
    root: Path,
    split: str,
) -> tuple[list[dict[str, Any]], int]:
    return _load_jsonl(root / f"{split}.jsonl")


def _task_ids(rows: list[dict[str, Any]]) -> set[str]:
    return {
        value
        for row in rows
        for value in [row.get("task_id")]
        if isinstance(value, str) and value
    }


def _dimension_counts(
    rows: list[dict[str, Any]],
    key: str,
) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        data = row.get("data", {})
        if isinstance(data, dict) and isinstance(data.get(key), str):
            counts[data[key]] += 1
    return dict(sorted(counts.items()))


def _verify_files(
    root: Path,
    manifest: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    receipts: dict[str, dict[str, Any]] = {}
    files = manifest.get("audit_files")
    if not isinstance(files, dict) or not files:
        raise AuditError("manifest audit_files must be a non-empty object")
    for logical_name, specification in files.items():
        if not isinstance(specification, dict):
            raise AuditError(f"audit_files.{logical_name} must be an object")
        relative_path = specification.get("relative_path")
        expected_sha256 = specification.get("sha256")
        if not isinstance(relative_path, str) or not isinstance(expected_sha256, str):
            raise AuditError(
                f"audit_files.{logical_name} requires relative_path and sha256"
            )
        path = root / relative_path
        actual_sha256 = sha256_path(path)
        if actual_sha256 != expected_sha256:
            raise AuditError(
                f"{path}: sha256 {actual_sha256} != pinned {expected_sha256}"
            )
        receipts[logical_name] = {
            "relative_path": relative_path,
            "sha256": actual_sha256,
            "bytes": path.stat().st_size,
        }
    return receipts


def audit_corpus(
    *,
    name: str,
    root: Path,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    receipts = _verify_files(root, manifest)
    train_rows, malformed_train = _load_tasks(root, "train")
    test_rows, malformed_test = _load_tasks(root, "test")
    spans, malformed_spans = _load_jsonl(root / "traces.otel.jsonl")

    train_ids = _task_ids(train_rows)
    test_ids = _task_ids(test_rows)
    operations: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    models: Counter[str] = Counter()
    rewards: list[float] = []
    captured_base_tasks: set[str] = set()
    captured_splits: Counter[str] = Counter()
    per_trace_operations: dict[str, Counter[str]] = defaultdict(Counter)
    span_ids: set[str] = set()
    duplicate_span_ids = 0
    metadata_records = 0
    prompts = 0
    tool_arguments = 0
    tool_results = 0
    nonempty_parent_ids = 0
    status_error_tool_results = 0
    start_values: list[int] = []
    end_values: list[int] = []

    for span in spans:
        trace_id = span.get("traceId")
        span_id = span.get("spanId")
        if isinstance(span_id, str):
            if span_id in span_ids:
                duplicate_span_ids += 1
            span_ids.add(span_id)
        if span.get("parentSpanId"):
            nonempty_parent_ids += 1
        status = span.get("status", {})
        status_code = (
            status.get("code")
            if isinstance(status, dict) and isinstance(status.get("code"), str)
            else "MISSING"
        )
        statuses[status_code] += 1
        for key, destination in (
            ("startTimeUnixNano", start_values),
            ("endTimeUnixNano", end_values),
        ):
            value = span.get(key)
            if isinstance(value, int):
                destination.append(value)

        attributes = _attributes(span)
        operation = attributes.get("gen_ai.operation.name")
        if isinstance(operation, str):
            operations[operation] += 1
            if isinstance(trace_id, str):
                per_trace_operations[trace_id][operation] += 1
        if "gen_ai.prompt" in attributes:
            prompts += 1
        if "gen_ai.tool.call.arguments" in attributes:
            tool_arguments += 1
        if "gen_ai.tool.message" in attributes:
            tool_results += 1
            if status_code == "STATUS_CODE_ERROR":
                status_error_tool_results += 1

        raw_metadata = attributes.get("wmh.trace.metadata")
        if isinstance(raw_metadata, str):
            metadata_records += 1
            try:
                metadata = json.loads(raw_metadata)
            except json.JSONDecodeError as exc:
                raise AuditError("wmh.trace.metadata contains malformed JSON") from exc
            if not isinstance(metadata, dict):
                raise AuditError("wmh.trace.metadata must decode to an object")
            model = metadata.get("model")
            if isinstance(model, str):
                models[model] += 1
            reward = metadata.get("reward")
            if isinstance(reward, (int, float)) and not isinstance(reward, bool):
                rewards.append(float(reward))
            base_task_id = _base_task_id(metadata)
            if base_task_id:
                captured_base_tasks.add(base_task_id)
            split = metadata.get("split")
            if isinstance(split, str):
                captured_splits[split] += 1

    balanced_traces = sum(
        counts.get("chat", 0) == counts.get("execute_tool", 0)
        and counts.get("chat", 0) > 0
        for counts in per_trace_operations.values()
    )
    binary_passes = sum(reward == 1.0 for reward in rewards)
    binary_failures = sum(reward == 0.0 for reward in rewards)
    max_timestamp = max(end_values) if end_values else None
    real_wall_clock_available = bool(
        max_timestamp is not None and max_timestamp >= 1_000_000_000_000_000
    )
    dimension_key = manifest.get("task_dimension_key")
    dimensions = (
        _dimension_counts(train_rows + test_rows, dimension_key)
        if isinstance(dimension_key, str)
        else {}
    )

    return {
        "dataset_id": manifest["dataset_id"],
        "dataset_revision": manifest["dataset_revision"],
        "license": manifest["license"],
        "source_adapter": manifest["source_adapter"],
        "input_receipts": receipts,
        "task_inventory": {
            "train_tasks": len(train_rows),
            "test_tasks": len(test_rows),
            "train_test_id_overlap": len(train_ids.intersection(test_ids)),
            "malformed_task_rows": malformed_train + malformed_test,
            "dimension_key": dimension_key,
            "dimension_counts": dimensions,
        },
        "trace_inventory": {
            "spans": len(spans),
            "malformed_spans": malformed_spans,
            "distinct_traces": len(per_trace_operations),
            "environment_transitions": operations.get("execute_tool", 0),
            "operations": dict(sorted(operations.items())),
            "status_codes": dict(sorted(statuses.items())),
            "status_error_tool_results": status_error_tool_results,
            "duplicate_span_ids": duplicate_span_ids,
            "metadata_records": metadata_records,
            "prompts_preserved": prompts,
            "tool_arguments_preserved": tool_arguments,
            "tool_results_preserved": tool_results,
            "full_assistant_narrative_field_observed": False,
            "captured_base_tasks": len(captured_base_tasks),
            "captured_train_tasks": len(captured_base_tasks.intersection(train_ids)),
            "captured_test_tasks": len(captured_base_tasks.intersection(test_ids)),
            "uncaptured_train_tasks": len(train_ids.difference(captured_base_tasks)),
            "captured_splits": dict(sorted(captured_splits.items())),
            "models": dict(sorted(models.items())),
            "reward_records": len(rewards),
            "mean_reward": round(sum(rewards) / len(rewards), 6) if rewards else None,
            "reward_exact_one": binary_passes,
            "reward_exact_zero": binary_failures,
        },
        "otel_loss_receipt": {
            "nonempty_parent_span_ids": nonempty_parent_ids,
            "all_spans_are_roots": nonempty_parent_ids == 0,
            "balanced_action_observation_traces": balanced_traces,
            "real_wall_clock_timestamps_available": real_wall_clock_available,
            "maximum_end_time_unix_nano": max_timestamp,
            "sequence_basis": (
                "synthetic ordinal timestamps within each trace; no parent edges"
                if not real_wall_clock_available and nonempty_parent_ids == 0
                else "inspect source"
            ),
            "latency_analysis_supported": real_wall_clock_available,
            "full_conversation_reconstruction_supported": False,
        },
        "replay_classification": manifest["replay_classification"],
        "claim_boundary": manifest["claim_boundary"],
    }


def build_result(
    *,
    bird_root: Path,
    bird_manifest: Path,
    crmarena_root: Path,
    crmarena_manifest: Path,
) -> dict[str, Any]:
    bird = audit_corpus(
        name="bird_sql",
        root=bird_root,
        manifest=_load_json(bird_manifest),
    )
    crmarena = audit_corpus(
        name="crmarena",
        root=crmarena_root,
        manifest=_load_json(crmarena_manifest),
    )
    result = {
        "schema_version": SCHEMA_VERSION,
        "engine_version": ENGINE_VERSION,
        "corpora": {
            "bird_sql": bird,
            "crmarena": crmarena,
        },
        "comparative_decision": {
            "primary_trace_mining_corpus": "bird_sql",
            "primary_enterprise_analytics_control": "crmarena",
            "primary_immediate_postgresql_causal_runner": "defog_sql_eval",
            "why_not_one_corpus": [
                "BIRD-SQL supplies multi-schema real action/observation traces and reconstructable SQLite replay",
                "CRMArena supplies realistic enterprise CRM analytics but only one org and non-commercial rights",
                "Defog supplies locally executable PostgreSQL task families but not natural agent traces",
            ],
            "candidate_skill_split_rule": (
                "partition by database/schema family before any candidate generation; "
                "withhold both tasks and traces for selection and test families"
            ),
            "unsupported_claims": [
                "production-user representativeness",
                "full OTel causal or latency fidelity",
                "person-level SQL skill inference",
                "commercial training rights for CRMArena",
                "Aurora compatibility from SQLite replay",
            ],
        },
    }
    result["content_sha256"] = hashlib.sha256(
        stable_json(result).encode("utf-8")
    ).hexdigest()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bird-root", type=Path, required=True)
    parser.add_argument("--bird-manifest", type=Path, required=True)
    parser.add_argument("--crmarena-root", type=Path, required=True)
    parser.add_argument("--crmarena-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = build_result(
        bird_root=args.bird_root,
        bird_manifest=args.bird_manifest,
        crmarena_root=args.crmarena_root,
        crmarena_manifest=args.crmarena_manifest,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
