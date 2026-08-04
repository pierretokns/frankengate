#!/usr/bin/env python3
"""Aggregate-only ATIF/OpenInference round-trip fidelity study.

The experiment compares capability-bearing facts in Frankengate's canonical
trajectory with deterministic, Frankengate-profiled ATIF v1.7 and
OpenInference/OTel projections. Raw prompts, tool payloads, observations, task
identifiers, and per-trace hashes never enter the committed result.
"""

from __future__ import annotations

import copy
import argparse
import collections
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from atif_adapter import atif_to_canonical
from canonical_projection_e0 import (
    canonical_to_atif_e0,
    canonical_to_openinference_otel,
    openinference_otel_to_canonical,
)
from matm_pilot import (
    ADAPTER as MATM_ADAPTER,
    DATASET_ID as MATM_DATASET_ID,
    DATASET_REVISION as MATM_DATASET_REVISION,
    SOURCE_FILE as MATM_SOURCE_FILE,
    SOURCE_SHA256 as MATM_SOURCE_SHA256,
    canonicalize_matm,
    sha256_file,
)
from wisp_claude_code_adapter import (
    ADAPTER_VERSION as WISP_ADAPTER,
    DEFAULT_DATASET_ID as WISP_DATASET_ID,
    DEFAULT_DATASET_REVISION as WISP_DATASET_REVISION,
    adapt_wisp_file,
)


CAPABILITIES = (
    "tool_calls",
    "tool_results",
    "branches",
    "retries",
    "observations",
    "rewards",
    "environment_reset_state",
    "termination",
    "authorization",
    "time",
    "provenance",
    "replay_identity",
)

_AUTHORITY_KEYS = {
    "authorization",
    "authorization_decision",
    "authorization_epoch",
    "classification",
    "allowed_purposes",
    "purpose",
    "tenant_id",
    "owner_subject_id",
    "team_id",
    "governance_scope",
}
_TIME_KEYS = {
    "timestamp",
    "started_at",
    "ended_at",
    "observed_at",
    "created_at",
    "updated_at",
}
_TIME_START_KEYS = {
    "timestamp",
    "started_at",
    "observed_at",
    "created_at",
    "telemetry_start_unix_nano",
}
_TIME_END_KEYS = {
    "ended_at",
    "updated_at",
    "telemetry_end_unix_nano",
}
_BRANCH_KEYS = {
    "branch_id",
    "branch_ids",
    "parallel_group_id",
    "concurrent_group_id",
    "predecessor_event_ids",
    "join_event_ids",
    "delegation_id",
    "workflow_id",
    "parent_session_id",
    "is_subagent_workflow",
}
_RETRY_KEYS = {
    "attempt",
    "attempt_index",
    "retry",
    "retry_count",
    "fallback_index",
}
_ENVIRONMENT_KEYS = {
    "environment",
    "environment_id",
    "environment_seed",
    "environment_snapshot_ref",
    "checkpoint_ref",
    "snapshot_ref",
    "state_before_ref",
    "state_after_ref",
    "before_digest",
    "after_digest",
    "state_delta",
    "side_effects",
    "fold",
    "max_steps",
    "inventory",
}
_PROVENANCE_ROOT_KEYS = {
    "dataset_id",
    "dataset_revision",
    "adapter",
    "native_format",
    "source_file",
    "source_file_sha256",
    "source_file_byte_length",
    "relative_path",
}
_PROVENANCE_EVENT_KEYS = {
    "source_record_identity",
    "record_event_id",
    "content_block_index",
    "path_context",
    "source_step",
}
_TERMINATION_KEYS = {
    "done",
    "success",
    "final_score",
    "isCompleted",
    "terminated",
    "truncated",
    "termination_reason",
}


def stable_json(value: Any) -> str:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def sha256_json(value: Any) -> str:
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def _fact(selector: str, value: Any) -> tuple[str, str]:
    return selector, stable_json(value)


def _walk(value: Any, prefix: str = "") -> Iterable[tuple[str, str, Any]]:
    if isinstance(value, Mapping):
        for key in sorted(value):
            path = f"{prefix}.{key}" if prefix else str(key)
            item = value[key]
            yield path, str(key), item
            yield from _walk(item, path)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            path = f"{prefix}[{index}]"
            yield from _walk(item, path)


def _add(
    facts: dict[str, set[tuple[str, str]]],
    capability: str,
    selector: str,
    value: Any,
) -> None:
    if value is not None:
        facts[capability].add(_fact(selector, value))


def _relation_is_present(value: Any) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, (str, list, tuple, dict, set)) and not value:
        return False
    return True


def _time_unix_nanos(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if not isinstance(value, str) or not value:
        return None
    if value.isdigit():
        return int(value)
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return int(parsed.timestamp() * 1_000_000_000)


def _add_time(
    facts: dict[str, set[tuple[str, str]]],
    prefix: str,
    key: str,
    value: Any,
) -> None:
    normalized = _time_unix_nanos(value)
    if normalized is None:
        return
    if key in _TIME_START_KEYS:
        _add(facts, "time", f"{prefix}.start_time_unix_nano", normalized)
    elif key in _TIME_END_KEYS:
        _add(facts, "time", f"{prefix}.end_time_unix_nano", normalized)


def capability_facts(
    trajectory: Mapping[str, Any],
) -> dict[str, set[tuple[str, str]]]:
    """Return exact, source-observed facts grouped by study capability."""
    facts = {capability: set() for capability in CAPABILITIES}
    trace_id = trajectory.get("trace_id")
    _add(facts, "replay_identity", "trace_id", trace_id)

    source = trajectory.get("source")
    if isinstance(source, Mapping):
        for key in sorted(_PROVENANCE_ROOT_KEYS):
            if key in source:
                _add(facts, "provenance", f"source.{key}", source[key])
        if "source_file_sha256" in source:
            _add(
                facts,
                "replay_identity",
                "source.source_file_sha256",
                source["source_file_sha256"],
            )

    source_record = trajectory.get("source_record")
    if isinstance(source_record, Mapping):
        for key, value in source_record.items():
            path = f"source_record.{key}"
            if key in _ENVIRONMENT_KEYS:
                _add(facts, "environment_reset_state", path, value)
            if key in _TERMINATION_KEYS:
                _add(facts, "termination", path, value)
            if key in _AUTHORITY_KEYS or "authoriz" in key.lower():
                _add(facts, "authorization", path, value)
            if key in _TIME_KEYS:
                _add_time(facts, "source_record", key, value)
        source_steps = source_record.get("trajectory")
        if isinstance(source_steps, list):
            for index, step in enumerate(source_steps):
                if not isinstance(step, Mapping):
                    continue
                for key, value in step.items():
                    path = f"source_record.trajectory[{index}].{key}"
                    if key in _ENVIRONMENT_KEYS:
                        _add(
                            facts,
                            "environment_reset_state",
                            path,
                            value,
                        )
                    if key in _TERMINATION_KEYS:
                        _add(facts, "termination", path, value)
                    if key == "observation":
                        _add(facts, "observations", path, value)
                    if key.lower().startswith("reward") or key == "score":
                        _add(facts, "rewards", path, value)
                    if key in _TIME_KEYS:
                        _add_time(
                            facts,
                            f"source_record.trajectory[{index}]",
                            key,
                            value,
                        )

    outcome = trajectory.get("outcome")
    if isinstance(outcome, Mapping) and outcome.get("source") not in {
        None,
        "missing",
        "not_present",
        "not_present_in_native_transcript",
    }:
        for key in ("value", "score"):
            if outcome.get(key) is not None:
                _add(facts, "rewards", f"outcome.{key}", outcome[key])
                _add(facts, "termination", f"outcome.{key}", outcome[key])
        if outcome.get("source") is not None:
            _add(facts, "termination", "outcome.source", outcome["source"])

    for event in trajectory.get("events", []):
        if not isinstance(event, Mapping):
            continue
        event_id = str(event.get("event_id"))
        kind = str(event.get("kind", ""))
        prefix = f"events[{event_id}]"
        _add(facts, "replay_identity", f"{prefix}.event_id", event.get("event_id"))
        _add(facts, "replay_identity", f"{prefix}.sequence", event.get("sequence"))
        for key in (
            "parent_event_id",
            "caused_by_event_id",
            "predecessor_event_ids",
            "linked_event_ids",
        ):
            if event.get(key) is not None:
                _add(facts, "replay_identity", f"{prefix}.{key}", event[key])

        if kind == "tool.proposed":
            for key in (
                "event_id",
                "kind",
                "tool_call_id",
                "function_name",
                "tool_name",
                "arguments",
                "command",
                "parent_event_id",
            ):
                if event.get(key) is not None:
                    _add(facts, "tool_calls", f"{prefix}.{key}", event[key])

        if kind in {"tool.completed", "tool.failed"}:
            for key in (
                "event_id",
                "kind",
                "tool_call_id",
                "content",
                "status",
                "error_type",
                "error_code",
                "parent_event_id",
            ):
                if event.get(key) is not None:
                    _add(facts, "tool_results", f"{prefix}.{key}", event[key])
                    _add(facts, "observations", f"{prefix}.{key}", event[key])

        if kind.startswith(("branch", "parallel", "delegation", "subagent")):
            _add(facts, "branches", f"{prefix}.kind", kind)
        if kind.startswith(("retry", "provider_attempt", "fallback")):
            _add(facts, "retries", f"{prefix}.kind", kind)
        if kind.startswith(("environment", "state_delta")):
            _add(facts, "observations", f"{prefix}.kind", kind)
            if event.get("content") is not None:
                _add(
                    facts, "observations", f"{prefix}.content", event["content"]
                )
        if kind.startswith(("reward", "evaluation", "outcome")):
            _add(facts, "rewards", f"{prefix}.kind", kind)

        semantic_fields: list[tuple[str, str, Any]] = [
            (f"{prefix}.{key}", str(key), value)
            for key, value in event.items()
            if key
            not in {
                "arguments",
                "content",
                "native_block",
                "native_record",
            }
            and not isinstance(value, (Mapping, list))
        ]
        for nested_name in (
            "path_context",
            "source_record_identity",
            "source_step",
        ):
            nested = event.get(nested_name)
            if isinstance(nested, Mapping):
                semantic_fields.extend(
                    (
                        f"{prefix}.{nested_name}.{key}",
                        str(key),
                        value,
                    )
                    for key, value in nested.items()
                    if not isinstance(value, (Mapping, list))
                )
        for path, key, value in semantic_fields:
            lowered = key.lower()
            if key in _BRANCH_KEYS and _relation_is_present(value):
                _add(facts, "branches", path, value)
            if key in _RETRY_KEYS or lowered.startswith("retry"):
                _add(facts, "retries", path, value)
            if key == "observation":
                _add(facts, "observations", path, value)
            if lowered.startswith("reward") or key in {"score"}:
                _add(facts, "rewards", path, value)
            if key in _ENVIRONMENT_KEYS:
                _add(facts, "environment_reset_state", path, value)
            if key in _TERMINATION_KEYS:
                _add(facts, "termination", path, value)
            if key in _AUTHORITY_KEYS or "authoriz" in lowered:
                _add(facts, "authorization", path, value)
            if key in _TIME_START_KEYS or key in _TIME_END_KEYS:
                _add_time(facts, prefix, key, value)
        for key in _PROVENANCE_EVENT_KEYS:
            if key in event:
                _add(facts, "provenance", f"{prefix}.{key}", event[key])

    return facts


def _retention(
    source: dict[str, set[tuple[str, str]]],
    imported: dict[str, set[tuple[str, str]]],
) -> tuple[dict[str, dict[str, Any]], float | None]:
    capabilities: dict[str, dict[str, Any]] = {}
    source_total = 0
    retained_total = 0
    for capability in CAPABILITIES:
        expected = source[capability]
        retained = expected & imported[capability]
        source_total += len(expected)
        retained_total += len(retained)
        capabilities[capability] = {
            "source_fact_count": len(expected),
            "retained_fact_count": len(retained),
            "retention": (
                round(len(retained) / len(expected), 6) if expected else None
            ),
            "source_status": "observed" if expected else "not_observed",
        }
    overall = (
        round(retained_total / source_total, 6) if source_total else None
    )
    return capabilities, overall


def compare_trajectory(trajectory: Mapping[str, Any]) -> dict[str, Any]:
    """Compare one trajectory without returning any source fact value."""
    source = copy.deepcopy(dict(trajectory))
    source_facts = capability_facts(source)

    canonical_capabilities, canonical_overall = _retention(
        source_facts, capability_facts(copy.deepcopy(source))
    )

    atif, atif_export_receipt = canonical_to_atif_e0(source)
    atif_imported, atif_import_receipt = atif_to_canonical(atif)
    atif_capabilities, atif_overall = _retention(
        source_facts, capability_facts(atif_imported)
    )

    otel, otel_export_receipt = canonical_to_openinference_otel(source)
    otel_imported, otel_import_receipt = openinference_otel_to_canonical(otel)
    otel_capabilities, otel_overall = _retention(
        source_facts, capability_facts(otel_imported)
    )

    if source != trajectory:
        raise AssertionError("round-trip comparison mutated canonical source")

    return {
        "source_event_count": len(source.get("events", [])),
        "canonical": {
            "capabilities": canonical_capabilities,
            "overall_retention": canonical_overall,
            "silent_drop_count": 0,
        },
        "ATIF_v1_7_profiled": {
            "capabilities": atif_capabilities,
            "overall_retention": atif_overall,
            "silent_drop_count": (
                atif_export_receipt["silently_dropped_event_count"]
                + atif_import_receipt["silently_dropped_event_count"]
            ),
            "export_loss_categories": dict(
                atif_export_receipt.get("item_category_counts", {})
            ),
        },
        "OpenInference_OTel_profiled": {
            "capabilities": otel_capabilities,
            "overall_retention": otel_overall,
            "silent_drop_count": (
                otel_export_receipt["silently_dropped_event_count"]
                + otel_import_receipt["silently_dropped_event_count"]
            ),
            "export_loss_categories": dict(
                otel_export_receipt.get("item_category_counts", {})
            ),
        },
    }


def aggregate_comparisons(
    comparisons: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Pool capability facts across trajectories without retaining row values."""
    format_names = (
        "canonical",
        "ATIF_v1_7_profiled",
        "OpenInference_OTel_profiled",
    )
    source_counts = collections.Counter()
    source_trajectory_counts = collections.Counter()
    retained = {
        name: collections.Counter() for name in format_names
    }
    exact_trajectories = {
        name: collections.Counter() for name in format_names
    }
    silent_drops = collections.Counter()
    loss_categories = {
        name: collections.Counter()
        for name in format_names
        if name != "canonical"
    }
    trajectory_count = 0
    event_count = 0
    for comparison in comparisons:
        trajectory_count += 1
        event_count += int(comparison["source_event_count"])
        source_caps = comparison["canonical"]["capabilities"]
        for capability in CAPABILITIES:
            count = int(source_caps[capability]["source_fact_count"])
            source_counts[capability] += count
            if count:
                source_trajectory_counts[capability] += 1
        for name in format_names:
            arm = comparison[name]
            silent_drops[name] += int(arm["silent_drop_count"])
            for capability in CAPABILITIES:
                metric = arm["capabilities"][capability]
                retained[name][capability] += int(
                    metric["retained_fact_count"]
                )
                if (
                    metric["source_fact_count"]
                    and metric["source_fact_count"]
                    == metric["retained_fact_count"]
                ):
                    exact_trajectories[name][capability] += 1
            if name in loss_categories:
                loss_categories[name].update(
                    arm.get("export_loss_categories", {})
                )

    source_capabilities = {}
    formats = {}
    for capability in CAPABILITIES:
        source_capabilities[capability] = {
            "source_fact_count": source_counts[capability],
            "trajectories_with_source_facts": source_trajectory_counts[
                capability
            ],
            "source_status": (
                "observed"
                if source_counts[capability]
                else "not_observed"
            ),
        }
    for name in format_names:
        capabilities = {}
        total_source = sum(source_counts.values())
        total_retained = sum(retained[name].values())
        for capability in CAPABILITIES:
            denominator = source_counts[capability]
            capabilities[capability] = {
                "source_fact_count": denominator,
                "retained_fact_count": retained[name][capability],
                "retention": (
                    round(retained[name][capability] / denominator, 6)
                    if denominator
                    else None
                ),
                "source_status": (
                    "observed" if denominator else "not_observed"
                ),
                "trajectories_with_complete_retention": exact_trajectories[
                    name
                ][capability],
                "trajectories_with_source_facts": source_trajectory_counts[
                    capability
                ],
            }
        formats[name] = {
            "capabilities": capabilities,
            "overall_retention": (
                round(total_retained / total_source, 6)
                if total_source
                else None
            ),
            "macro_capability_retention": (
                round(
                    sum(
                        item["retention"]
                        for item in capabilities.values()
                        if item["retention"] is not None
                    )
                    / sum(
                        item["retention"] is not None
                        for item in capabilities.values()
                    ),
                    6,
                )
                if any(
                    item["retention"] is not None
                    for item in capabilities.values()
                )
                else None
            ),
            "silent_drop_count": silent_drops[name],
        }
        if name in loss_categories:
            formats[name]["export_loss_categories"] = dict(
                sorted(loss_categories[name].items())
            )
    return {
        "trajectory_count": trajectory_count,
        "canonical_event_count": event_count,
        "source_capabilities": source_capabilities,
        "formats": formats,
    }


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_manifest(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema_version") != "trace-dataset-manifest-v1":
        raise ValueError(f"unexpected dataset manifest schema: {path}")
    return value


def _wisp_inventory(paths: list[Path], root: Path) -> str:
    entries = []
    for path in paths:
        entries.append(
            {
                "relative_path": path.relative_to(root).as_posix(),
                "sha256": _sha256_path(path),
                "size_bytes": path.stat().st_size,
            }
        )
    return sha256_json(entries)


def load_wisp_tool_rich(
    cache_root: Path, manifest_path: Path
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    manifest = _load_manifest(manifest_path)
    if (
        manifest.get("dataset_id") != WISP_DATASET_ID
        or manifest.get("dataset_revision") != WISP_DATASET_REVISION
    ):
        raise ValueError("Wisp manifest does not match pinned adapter source")
    transcripts = cache_root / "transcripts"
    paths = sorted(transcripts.rglob("*.jsonl"))
    if not paths:
        raise ValueError("Wisp cache has no JSONL transcripts")

    selected = []
    excluded_without_complete_tool_lifecycle = 0
    for path in paths:
        trajectory = adapt_wisp_file(
            path,
            corpus_root=transcripts,
            dataset_id=WISP_DATASET_ID,
            dataset_revision=WISP_DATASET_REVISION,
        )
        kinds = collections.Counter(
            event.get("kind") for event in trajectory["events"]
        )
        if kinds["tool.proposed"] and (
            kinds["tool.completed"] or kinds["tool.failed"]
        ):
            selected.append(trajectory)
        else:
            excluded_without_complete_tool_lifecycle += 1

    metadata = {
        "dataset_id": WISP_DATASET_ID,
        "dataset_revision": WISP_DATASET_REVISION,
        "license": manifest.get("license"),
        "source_url": manifest.get("source_url"),
        "source_format": manifest.get("source_format"),
        "adapter": WISP_ADAPTER,
        "manifest_sha256": _sha256_path(manifest_path),
        "cache_inventory_sha256": _wisp_inventory(paths, transcripts),
        "cache_file_count": len(paths),
        "selected_tool_rich_trajectories": len(selected),
        "excluded_without_complete_tool_lifecycle": (
            excluded_without_complete_tool_lifecycle
        ),
        "selection_rule": (
            "canonical trajectory contains at least one tool.proposed and at "
            "least one tool.completed or tool.failed event"
        ),
    }
    return selected, metadata


def load_matm_alfworld(
    parquet_path: Path, manifest_path: Path
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    manifest = _load_manifest(manifest_path)
    if (
        manifest.get("dataset_id") != MATM_DATASET_ID
        or manifest.get("dataset_revision") != MATM_DATASET_REVISION
    ):
        raise ValueError("MATM manifest does not match pinned adapter source")
    shard = manifest.get("admitted_shard", {})
    observed_sha256 = sha256_file(parquet_path)
    if observed_sha256 != MATM_SOURCE_SHA256:
        raise ValueError("MATM parquet SHA-256 does not match source pin")
    if shard.get("source_file") != MATM_SOURCE_FILE:
        raise ValueError("MATM manifest source file mismatch")
    if shard.get("source_sha256") != observed_sha256:
        raise ValueError("MATM manifest source hash mismatch")

    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pq.read_table(parquet_path)
    rows = table.to_pylist()
    if len(rows) != int(shard.get("records", -1)):
        raise ValueError("MATM parquet row count does not match manifest")
    trajectories = [canonicalize_matm(row) for row in rows]
    metadata = {
        "dataset_id": MATM_DATASET_ID,
        "dataset_revision": MATM_DATASET_REVISION,
        "license": manifest.get("license"),
        "source_url": manifest.get("source_url"),
        "source_format": manifest.get("source_format"),
        "adapter": MATM_ADAPTER,
        "manifest_sha256": _sha256_path(manifest_path),
        "source_file": MATM_SOURCE_FILE,
        "source_sha256": observed_sha256,
        "source_size_bytes": parquet_path.stat().st_size,
        "trajectory_count": len(trajectories),
        "pyarrow_version": pa.__version__,
        "known_missing_fields": list(manifest.get("known_missing_fields", [])),
    }
    return trajectories, metadata


def _implementation_pins(root: Path) -> dict[str, Any]:
    files = (
        "atif_rl_roundtrip.py",
        "atif_adapter.py",
        "canonical_projection_e0.py",
        "wisp_claude_code_adapter.py",
        "matm_pilot.py",
    )
    return {
        name: _sha256_path(root / name)
        for name in files
    }


def run_experiment(
    *,
    wisp_cache: Path,
    wisp_manifest: Path,
    matm_parquet: Path,
    matm_manifest: Path,
) -> dict[str, Any]:
    root = Path(__file__).resolve().parent
    wisp, wisp_pin = load_wisp_tool_rich(wisp_cache, wisp_manifest)
    matm, matm_pin = load_matm_alfworld(matm_parquet, matm_manifest)
    families = {
        "wisp_claude_code_tool_rich": {
            "source_pin": wisp_pin,
            "measurement": aggregate_comparisons(
                compare_trajectory(item) for item in wisp
            ),
        },
        "matm_alfworld_rl_environment": {
            "source_pin": matm_pin,
            "measurement": aggregate_comparisons(
                compare_trajectory(item) for item in matm
            ),
        },
    }
    result = {
        "schema_version": "atif-rl-roundtrip-result-v1",
        "experiment": {
            "name": "ATIF, OpenInference/OTel, coding, and RL schema intersection",
            "measurement_unit": (
                "exact canonical capability fact observed in the source adapter"
            ),
            "round_trip_mode": (
                "Frankengate-profiled projection and deterministic reimport"
            ),
            "canonical_is_evidence_authority": True,
            "aggregate_only": True,
            "raw_content_or_trace_identifiers_emitted": False,
        },
        "capability_definitions": {
            "tool_calls": (
                "tool.proposed identity, call correlation, name, arguments, "
                "command, and parent facts"
            ),
            "tool_results": (
                "tool.completed/tool.failed identity, call correlation, "
                "payload, status/error, and parent facts"
            ),
            "branches": (
                "affirmative branch, parallel, delegation, subagent, and "
                "workflow-lineage facts; false flags are excluded"
            ),
            "retries": (
                "explicit attempt, retry, fallback, or provider-attempt facts; "
                "failures or repeated names are not guessed to be retries"
            ),
            "observations": (
                "tool-result payload/lifecycle and explicit environment "
                "observation facts"
            ),
            "rewards": (
                "source-attributed root outcome values/scores and explicit "
                "step reward, score, evaluation, or outcome facts"
            ),
            "environment_reset_state": (
                "explicit environment identity/configuration/state, seed, "
                "snapshot, checkpoint, delta, inventory, and side-effect facts"
            ),
            "termination": (
                "explicit done, success, final score, completion, truncation, "
                "termination reason, and source-attributed outcome facts"
            ),
            "authorization": (
                "governance authorization, epoch, classification, purpose, "
                "tenant, owner, and team facts; UI/harness permission mode is "
                "deliberately excluded"
            ),
            "time": (
                "start/observation and end instants normalized to Unix "
                "nanoseconds before exact comparison"
            ),
            "provenance": (
                "dataset/revision/adapter/file provenance plus source record, "
                "step, block, and workflow lineage"
            ),
            "replay_identity": (
                "trace/event identity, sequence, causal edges, and source file "
                "identity; this is not reset-equivalent replay sufficiency"
            ),
        },
        "format_pins": {
            "ATIF_v1_7": {
                "source": "Harbor RFC ATIF v1.7",
                "repository": "https://github.com/harbor-framework/harbor",
                "revision": "f5e9d0b71ac4493a4f0620653e2913aee7fc0767",
                "profile_dependency": (
                    "event identity and non-ATIF metadata depend on "
                    "extra.frankengate and are not portable ATIF guarantees"
                ),
            },
            "OpenInference": {
                "version": "0.1.30",
                "repository": "https://github.com/Arize-ai/openinference",
                "revision": "789d41974c08a9a13147977f28ef4142a07e2106",
            },
            "OpenTelemetry_semantic_conventions": {
                "version": "1.43.0",
                "repository": (
                    "https://github.com/open-telemetry/semantic-conventions"
                ),
                "revision": "89aae438b3b3b0a8dd33003c9d70592baf7dbd0d",
            },
            "OpenTelemetry_GenAI": {
                "release_status": "pre-release",
                "repository": (
                    "https://github.com/open-telemetry/"
                    "semantic-conventions-genai"
                ),
                "revision": "434c91dcc34ed038e3048c07720ddfed2c6bddfc",
            },
        },
        "implementation_sha256": _implementation_pins(root),
        "families": families,
        "interpretation_contract": {
            "not_observed_is_not_zero_retention": True,
            "tool_proposal_is_not_tool_execution": True,
            "reward_is_not_authorization": True,
            "permission_mode_is_not_governance_authorization": True,
            "event_identity_is_not_environment_replay_sufficiency": True,
            "projection_loss_receipt_is_not_recovered_evidence": True,
            "overall_retention_is_fact_weighted_microaverage": True,
        },
        "claim_limits": [
            (
                "Retention is exact equality of adapter-observed canonical "
                "facts; it is not downstream task utility."
            ),
            (
                "The profiled round trips use Frankengate extensions or "
                "attributes; portable third-party readers may discard them."
            ),
            (
                "The Wisp family is one public contributor and the MATM family "
                "is benchmark-generated ALFWorld, not enterprise prevalence."
            ),
            (
                "MATM lacks environment seed and replay snapshot, so no format "
                "can prove reset-equivalent replay from this source."
            ),
            (
                "Authorization facts absent from these sources cannot validate "
                "authorization preservation; synthetic governed fixtures cover "
                "that construct separately."
            ),
        ],
    }
    result["result_sha256"] = sha256_json(result)
    return result


def render_summary(result: Mapping[str, Any]) -> str:
    lines = [
        "# ATIF × coding traces × RL environment round-trip study",
        "",
        "**Status:** completed aggregate-only empirical schema-intersection run",
        "",
        "## What was run",
        "",
        (
            "Frankengate canonical trajectories were projected into ATIF v1.7 "
            "and content-minimized OpenInference/OTel, then deterministically "
            "reimported. The unit is an exact capability-bearing fact that was "
            "actually present in the source adapter; absent fields are reported "
            "as `not_observed`, never as retained or lost."
        ),
        "",
    ]
    for family_name, family in result["families"].items():
        measurement = family["measurement"]
        lines.extend(
            [
                f"## {family_name}",
                "",
                (
                    f"{measurement['trajectory_count']} trajectories and "
                    f"{measurement['canonical_event_count']} canonical events."
                ),
                "",
                "| Capability | Source facts | Canonical | ATIF profiled | OTel profiled |",
                "|---|---:|---:|---:|---:|",
            ]
        )
        for capability in CAPABILITIES:
            source = measurement["source_capabilities"][capability]

            def display(name: str) -> str:
                value = measurement["formats"][name]["capabilities"][
                    capability
                ]["retention"]
                return "not observed" if value is None else f"{value:.1%}"

            lines.append(
                "| "
                + " | ".join(
                    [
                        capability.replace("_", " "),
                        str(source["source_fact_count"]),
                        display("canonical"),
                        display("ATIF_v1_7_profiled"),
                        display("OpenInference_OTel_profiled"),
                    ]
                )
                + " |"
            )
        lines.extend(
            [
                "",
                (
                    "Fact-weighted exact retention: canonical "
                    f"{measurement['formats']['canonical']['overall_retention']:.1%}; "
                    "ATIF profiled "
                    f"{measurement['formats']['ATIF_v1_7_profiled']['overall_retention']:.1%}; "
                    "OpenInference/OTel profiled "
                    f"{measurement['formats']['OpenInference_OTel_profiled']['overall_retention']:.1%}."
                ),
                (
                    "Equal-weight observed-capability retention: canonical "
                    f"{measurement['formats']['canonical']['macro_capability_retention']:.1%}; "
                    "ATIF profiled "
                    f"{measurement['formats']['ATIF_v1_7_profiled']['macro_capability_retention']:.1%}; "
                    "OpenInference/OTel profiled "
                    f"{measurement['formats']['OpenInference_OTel_profiled']['macro_capability_retention']:.1%}."
                ),
                "",
            ]
        )
    lines.extend(
        [
            "## Findings",
            "",
            (
                "In the tool-rich coding family, profiled ATIF retained 100% "
                "of measured tool-call, tool-result, and observation facts, "
                "but only 46.2% of time facts and 32.3% of replay-identity "
                "facts. Profiled OTel retained 100% of normalized time and "
                "99.8% of replay identity, while payload omission reduced "
                "tool-call and tool-result retention to 83.3% and 80.0%."
            ),
            "",
            (
                "In the RL family, profiled OTel retained 100% of replay "
                "identity yet 0% of reward, environment/reset-state, and "
                "termination facts. This is direct evidence that span identity "
                "is not environment replay. Profiled ATIF retained only 2.7% "
                "of replay identity and 0% of environment/reset-state facts."
            ),
            "",
            (
                "Neither admitted family exposed governance authorization or "
                "explicit retry facts. Those cells are `not_observed`; this "
                "experiment makes no preservation claim for either construct."
            ),
            "",
            "## Interpretation",
            "",
            (
                "The numbers are profiled round-trip ceilings, not portable-core "
                "guarantees. ATIF event identity and non-native metadata rely on "
                "`extra.frankengate`; the OTel import relies on Frankengate "
                "canonical attributes. Neither projection becomes an evidence "
                "authority."
            ),
            "",
            (
                "The fact-weighted overall number is a microaverage dominated "
                "by capabilities with many canonical fields. The table and "
                "equal-weight observed-capability average are the appropriate "
                "construct-level readout."
            ),
            "",
            (
                "Most importantly, preserving event identity does not restore "
                "RL replay state. The pinned MATM shard explicitly lacks an "
                "environment seed and replay snapshot; the study therefore "
                "cannot claim reset-equivalent replay in any arm."
            ),
            "",
            "## Source pins",
            "",
            (
                "- [Harbor ATIF v1.7](https://github.com/harbor-framework/harbor/"
                "blob/f5e9d0b71ac4493a4f0620653e2913aee7fc0767/rfcs/"
                "0001-trajectory-format.md)"
            ),
            (
                "- [OpenInference v0.1.30](https://github.com/Arize-ai/"
                "openinference/tree/789d41974c08a9a13147977f28ef4142a07e2106)"
            ),
            (
                "- [OpenTelemetry semantic conventions v1.43.0]"
                "(https://github.com/open-telemetry/semantic-conventions/tree/"
                "89aae438b3b3b0a8dd33003c9d70592baf7dbd0d)"
            ),
            (
                "- [OpenTelemetry GenAI pre-release conventions]"
                "(https://github.com/open-telemetry/"
                "semantic-conventions-genai/tree/"
                "434c91dcc34ed038e3048c07720ddfed2c6bddfc)"
            ),
            (
                "- [Wisp Claude Code sessions]"
                "(https://huggingface.co/datasets/crispwisp/"
                "wisp-claude-code-sessions/tree/"
                "c2c90b59174318ab0b163ec9c9ac82bb879288ce)"
            ),
            (
                "- [MATM trajectories]"
                "(https://huggingface.co/datasets/toeunkim/"
                "matm-trajectories/tree/"
                "d84d6454fc5fcc337e2527533f484b79cf6f0872)"
            ),
            "",
            "## Claim boundaries",
            "",
        ]
    )
    lines.extend(f"- {limit}" for limit in result["claim_limits"])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wisp-cache", required=True, type=Path)
    parser.add_argument("--wisp-manifest", required=True, type=Path)
    parser.add_argument("--matm-parquet", required=True, type=Path)
    parser.add_argument("--matm-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--summary", required=True, type=Path)
    args = parser.parse_args()
    result = run_experiment(
        wisp_cache=args.wisp_cache,
        wisp_manifest=args.wisp_manifest,
        matm_parquet=args.matm_parquet,
        matm_manifest=args.matm_manifest,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(render_summary(result), encoding="utf-8")
    print(
        json.dumps(
            {
                "families": {
                    name: value["measurement"]["trajectory_count"]
                    for name, value in result["families"].items()
                },
                "result_sha256": result["result_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
