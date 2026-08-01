#!/usr/bin/env python3
"""Audit recently acquired replay/diagnosis corpora without emitting raw data.

This is a fit/readiness audit, not a claim that a benchmark result transfers to
Frankengate.  It records which labels and replay hooks are actually present so
that a public corpus cannot accidentally be cited as enterprise causal
evidence.  The inputs are expected to be local checkouts of:

* patronus-ai/trail-benchmark
* letta-ai/recovery-bench (with Git LFS objects available)

The receipt contains counts, stable aggregate hashes, and explicit claim
boundaries only; it never copies prompts, commands, tool arguments, or trace
content.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


def _json_files(root: Path, pattern: str) -> List[Path]:
    return sorted(path for path in root.rglob(pattern) if path.is_file())


def _read_json(path: Path) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, type(exc).__name__
    if not isinstance(value, dict):
        return None, "not_object"
    return value, None


def _aggregate_hash(paths: Iterable[Path], root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
        digest.update(b"\n")
    return digest.hexdigest()


def _first_present(mapping: Dict[str, Any], names: Iterable[str]) -> bool:
    return any(name in mapping and mapping[name] not in (None, "") for name in names)


def audit_trail(root: Path) -> Dict[str, Any]:
    data_root = root / "benchmarking" / "data"
    annotation_roots = {
        "GAIA": root / "benchmarking" / "processed_annotations_gaia",
        "SWE Bench": root / "benchmarking" / "processed_annotations_swe_bench",
    }
    data_files: List[Path] = []
    by_split: Dict[str, List[Path]] = {}
    for split in ("GAIA", "SWE Bench"):
        files = _json_files(data_root / split, "*.json")
        by_split[split] = files
        data_files.extend(files)

    annotations: List[Path] = []
    for path in annotation_roots.values():
        annotations.extend(_json_files(path, "*.json"))

    trace_ids: List[str] = []
    project_ids: List[str] = []
    services: List[str] = []
    span_counts: List[int] = []
    body_keys: Counter[str] = Counter()
    status_codes: Counter[str] = Counter()
    has_principal = 0
    has_tenant = 0
    has_project = 0
    parse_errors: List[Dict[str, str]] = []

    for path in data_files:
        value, error = _read_json(path)
        if error:
            parse_errors.append({"file": str(path.relative_to(root)), "error": error})
            continue
        assert value is not None
        trace_ids.append(str(value.get("trace_id", "")))
        spans = value.get("spans") if isinstance(value.get("spans"), list) else []
        span_counts.append(len(spans))
        for span in spans:
            if not isinstance(span, dict):
                continue
            attrs = span.get("span_attributes")
            attrs = attrs if isinstance(attrs, dict) else {}
            resource = span.get("resource_attributes")
            resource = resource if isinstance(resource, dict) else {}
            project = attrs.get("pat.project.id") or attrs.get("project.id")
            service = resource.get("service.name") or span.get("service_name")
            if project:
                project_ids.append(str(project))
                has_project += 1
            if service:
                services.append(str(service))
            principal_names = (
                "user.id",
                "user_id",
                "principal.id",
                "principal_id",
                "tenant.user_id",
                "enduser.id",
            )
            tenant_names = ("tenant.id", "tenant_id", "org.id", "organization.id")
            if _first_present(attrs, principal_names) or _first_present(resource, principal_names):
                has_principal += 1
            if _first_present(attrs, tenant_names) or _first_present(resource, tenant_names):
                has_tenant += 1
            status_codes[str(span.get("status_code", "missing"))] += 1
            logs = span.get("logs") if isinstance(span.get("logs"), list) else []
            for log in logs:
                if isinstance(log, dict) and isinstance(log.get("body"), dict):
                    body_keys.update(str(key) for key in log["body"])

    categories: Counter[str] = Counter()
    impacts: Counter[str] = Counter()
    score_keys: Counter[str] = Counter()
    annotation_ids: List[str] = []
    annotation_errors: List[Dict[str, str]] = []
    for path in annotations:
        value, error = _read_json(path)
        if error:
            annotation_errors.append({"file": str(path.relative_to(root)), "error": error})
            continue
        assert value is not None
        annotation_ids.append(str(value.get("trace_id", "")))
        errors = value.get("errors") if isinstance(value.get("errors"), list) else []
        for item in errors:
            if not isinstance(item, dict):
                continue
            categories[str(item.get("category", "missing"))] += 1
            impacts[str(item.get("impact", "missing"))] += 1
        scores = value.get("scores") if isinstance(value.get("scores"), list) else []
        for score in scores:
            if isinstance(score, dict):
                score_keys.update(str(key) for key in score)

    return {
        "repository": "patronus-ai/trail-benchmark",
        "source_revision": _aggregate_hash(data_files + annotations, root),
        "data_files": len(data_files),
        "data_files_by_split": {split: len(files) for split, files in by_split.items()},
        "annotation_files": len(annotations),
        "valid_data_records": len(trace_ids),
        "valid_annotation_records": len(annotation_ids),
        "invalid_data_records": parse_errors,
        "invalid_annotation_records": annotation_errors,
        "unique_trace_ids": len({item for item in trace_ids if item}),
        "unique_annotation_trace_ids": len({item for item in annotation_ids if item}),
        "annotation_coverage": round(len(set(annotation_ids) & set(trace_ids)) / len(set(trace_ids)), 6)
        if trace_ids
        else 0.0,
        "unique_project_ids": len(set(project_ids)),
        "unique_service_names": len(set(services)),
        "spans_total": sum(span_counts),
        "span_count_mean": round(sum(span_counts) / len(span_counts), 6) if span_counts else 0.0,
        "principal_identity_span_count": has_principal,
        "tenant_identity_span_count": has_tenant,
        "project_metadata_span_count": has_project,
        "span_status_codes": dict(status_codes),
        "annotation_error_categories": dict(categories),
        "annotation_error_impacts": dict(impacts),
        "annotation_score_fields": sorted(score_keys),
        "observed_log_body_fields": sorted(body_keys),
        "fit": {
            "failure_diagnosis_calibration": bool(annotation_ids),
            "cross_user_transfer": False,
            "enterprise_causal_replay": False,
            "reason": "Annotated trace errors and scores exist, but principal identity, enterprise task intent, changed-system outcomes, and independent replay outcomes are absent.",
        },
    }


def _reward_for(result_path: Path) -> Optional[str]:
    reward_path = result_path.parent / "verifier" / "reward.txt"
    try:
        return reward_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def audit_recovery(root: Path) -> Dict[str, Any]:
    # The run-level aggregate is also named result.json; only count trial
    # receipts that have a sibling config.json and verifier directory.
    result_files = [
        path
        for path in _json_files(root, "result.json")
        if (path.parent / "config.json").is_file() and (path.parent / "verifier").is_dir()
    ]
    trajectory_files = _json_files(root, "trajectory.json")
    rewards: Counter[str] = Counter()
    tasks: List[str] = []
    model_names: List[str] = []
    agents: List[str] = []
    environments: List[str] = []
    schema_versions: List[str] = []
    agent_steps = 0
    tool_calls = 0
    user_steps = 0
    agent_trace_files = 0
    recovery_result_files = 0
    parse_errors: List[Dict[str, str]] = []

    for path in result_files:
        value, error = _read_json(path)
        if error:
            parse_errors.append({"file": str(path.relative_to(root)), "error": error})
            continue
        assert value is not None
        reward = _reward_for(path) or "missing"
        rewards[reward] += 1
        task_name = value.get("task_name")
        if task_name:
            tasks.append(str(task_name))
        model = value.get("agent_info", {}).get("model_info", {}).get("name")
        if model:
            model_names.append(str(model))
        agent = value.get("agent_info", {}).get("name")
        if agent:
            agents.append(str(agent))
        environment = value.get("config", {}).get("environment", {}).get("type")
        if environment:
            environments.append(str(environment))
        relative_parts = path.relative_to(root).parts
        run_root = relative_parts[0] if relative_parts else ""
        if run_root.lower().startswith("recovery-"):
            recovery_result_files += 1
        else:
            agent_trace_files += 1

    for path in trajectory_files:
        value, error = _read_json(path)
        if error:
            parse_errors.append({"file": str(path.relative_to(root)), "error": error})
            continue
        assert value is not None
        schema_versions.append(str(value.get("schema_version", "missing")))
        steps = value.get("steps") if isinstance(value.get("steps"), list) else []
        agent_steps += len(steps)
        user_steps += sum(1 for step in steps if isinstance(step, dict) and step.get("source") == "user")
        tool_calls += sum(
            len(step.get("tool_calls", []))
            for step in steps
            if isinstance(step, dict) and isinstance(step.get("tool_calls"), list)
        )

    initial_results = agent_trace_files
    failed = int(rewards.get("0", 0))
    successful = int(rewards.get("1", 0))
    return {
        "repository": "letta-ai/recovery-bench",
        "source_revision": _aggregate_hash(result_files + trajectory_files, root),
        "result_files": len(result_files),
        "trajectory_files": len(trajectory_files),
        "valid_result_or_trajectory_files": len(result_files) + len(trajectory_files) - len(parse_errors),
        "invalid_records": parse_errors,
        "unique_tasks": len(set(tasks)),
        "task_names_hash": hashlib.sha256("\n".join(sorted(set(tasks))).encode("utf-8")).hexdigest(),
        "reward_counts": dict(rewards),
        "initial_failure_count": failed,
        "initial_success_count": successful,
        "model_names": sorted(set(model_names)),
        "agent_names": sorted(set(agents)),
        "environment_types": sorted(set(environments)),
        "trajectory_schema_versions": sorted(set(schema_versions)),
        "agent_steps_total": agent_steps,
        "user_steps_total": user_steps,
        "tool_calls_total": tool_calls,
        "initial_result_files": initial_results,
        "recovery_result_files": recovery_result_files,
        "fit": {
            "failure_replay_fixture": failed > 0 and bool(trajectory_files),
            "recovery_outcome_present": recovery_result_files > 0,
            "cross_user_transfer": False,
            "enterprise_causal_replay": False,
            "reason": "The checkout contains initial Terminal-Bench trajectories and verifier rewards, but no recovery-agent intervention/results, principal identity, or enterprise task labels. It is a recovery fixture, not evidence of skill transfer.",
        },
    }


def audit(trail_root: Path, recovery_root: Path) -> Dict[str, Any]:
    trail = audit_trail(trail_root)
    recovery = audit_recovery(recovery_root)
    return {
        "schema": "frankengate.recent_replay_dataset_fit_audit.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {"trail_root": str(trail_root), "recovery_root": str(recovery_root)},
        "trail": trail,
        "recovery_bench": recovery,
        "release_decision": {
            "ready_for_enterprise_causal_skill_claim": False,
            "ready_for_independent_failure_diagnosis_calibration": bool(
                trail["fit"]["failure_diagnosis_calibration"]
            ),
            "ready_for_recovery_replay_baseline": bool(recovery["fit"]["failure_replay_fixture"]),
        "required_next_step": f"Run paired no-context/full-context/summary recovery agents on the {recovery['initial_failure_count']} failed tasks, preserve task-disjoint episodes, and score verifier reward plus repair regressions before comparing mined skills.",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trail-root", type=Path, required=True)
    parser.add_argument("--recovery-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = audit(args.trail_root.resolve(), args.recovery_root.resolve())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt["release_decision"], sort_keys=True))


if __name__ == "__main__":
    main()
