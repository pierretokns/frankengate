#!/usr/bin/env python3
"""Audit TRAJECT-Bench structure without invoking models or tools.

The benchmark is useful for conformance and trajectory-metric work, but its
published records are generated benchmark trajectories rather than consented
enterprise user histories. This audit emits only aggregate structure counts and
hashes so we can record what it can and cannot support.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-traject-bench-structural-audit-v1"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def _rows(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _param_completeness(tool: dict[str, Any]) -> tuple[int, int]:
    present = 0
    total = 0
    for key in ("required parameters", "optional parameters"):
        values = tool.get(key) or []
        if not isinstance(values, list):
            continue
        for item in values:
            if not isinstance(item, dict):
                continue
            total += 1
            if item.get("value") not in (None, ""):
                present += 1
    return present, total


def _tool_list(row: dict[str, Any]) -> list[dict[str, Any]]:
    value = row.get("tool list", row.get("tool_list", []))
    return value if isinstance(value, list) else []


def _tool_succeeded(tool: dict[str, Any]) -> bool:
    status = str(tool.get("execution_status", "")).casefold()
    if status:
        return status in {"success", "succeeded", "ok"}
    output = tool.get("executed_output")
    if output in (None, ""):
        return False
    return not str(output).lstrip().startswith("ERROR:") and "please upgrade your subscription" not in str(output).casefold()


def audit(root: Path) -> dict[str, Any]:
    files = sorted(root.glob("parallel/*/*.json")) + sorted(root.glob("sequential/*/*.json"))
    file_counts: Counter[str] = Counter()
    domain_counts: Counter[str] = Counter()
    trajectory_counts: Counter[str] = Counter()
    query_counts: Counter[str] = Counter()
    tool_count_mismatches = 0
    successful_count_mismatches = 0
    executable_counts: Counter[str] = Counter()
    records = 0
    tools = 0
    tools_with_output = 0
    duplicate_tool_lists = 0
    parameter_total = 0
    parameter_present = 0
    connected_tools = 0
    sequential_records = 0
    parallel_records = 0

    for path in files:
        kind = "sequential" if "/sequential/" in str(path) else "parallel"
        rows = _rows(path)
        file_counts[kind] += len(rows)
        for row in rows:
            records += 1
            domain = str(row.get("domain") or path.parent.name)
            domain_counts[domain] += 1
            trajectory = str(row.get("trajectory_type") or kind)
            trajectory_counts[trajectory] += 1
            query_counts["hard" if "hard" in path.name else "simple" if "simple" in path.name else "unspecified"] += 1
            if kind == "sequential":
                sequential_records += 1
                executable_counts[str(bool(row.get("executable")))] += 1
                if row.get("connected tools"):
                    connected_tools += 1
            else:
                parallel_records += 1
            tool_list = _tool_list(row)
            tools += len(tool_list)
            reported = row.get("tool count")
            if reported is not None and int(reported) != len(tool_list):
                tool_count_mismatches += 1
            if len({str(item.get("tool name")) for item in tool_list if isinstance(item, dict)}) != len(tool_list):
                duplicate_tool_lists += 1
            for tool in tool_list:
                if not isinstance(tool, dict):
                    continue
                output = tool.get("executed_output")
                if output not in (None, ""):
                    tools_with_output += 1
                present, total = _param_completeness(tool)
                parameter_present += present
                parameter_total += total
            if kind == "sequential" and row.get("num_tools_used") is not None and int(row["num_tools_used"]) != len(tool_list):
                tool_count_mismatches += 1
            if kind == "sequential" and row.get("num_successful_tools") is not None:
                successful = sum(_tool_succeeded(tool) for tool in tool_list if isinstance(tool, dict))
                if int(row["num_successful_tools"]) != successful:
                    successful_count_mismatches += 1

    hashes = [file_sha256(path) for path in files]
    return {
        "schema_version": SCHEMA_VERSION,
        "source": {"root_name": root.name, "file_count": len(files), "files_sha256": stable_hash(sorted(hashes)), "raw_content_committed": False},
        "records": records,
        "parallel_records": parallel_records,
        "sequential_records": sequential_records,
        "tool_invocations_described": tools,
        "tools_with_nonempty_executed_output": tools_with_output,
        "parameter_values_present": parameter_present,
        "parameter_values_total": parameter_total,
        "tool_count_mismatches": tool_count_mismatches,
        "successful_tool_count_mismatches": successful_count_mismatches,
        "duplicate_tool_list_records": duplicate_tool_lists,
        "sequential_records_with_connected_tools": connected_tools,
        "file_record_counts": dict(sorted(file_counts.items())),
        "domain_counts": dict(sorted(domain_counts.items())),
        "trajectory_type_counts": dict(sorted(trajectory_counts.items())),
        "query_variant_counts": dict(sorted(query_counts.items())),
        "sequential_executable_counts": dict(sorted(executable_counts.items())),
        "claim_boundary": {
            "deterministic_structure_audited": True,
            "model_quality_measured": False,
            "agent_intervention_measured": False,
            "enterprise_user_behavior_measured": False,
            "reason": "TRAJECT-Bench records are benchmark trajectories with tool definitions and reference paths; they do not provide consented principals, production outcomes, or changed-system replay.",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("records", "parallel_records", "sequential_records", "tool_invocations_described", "tool_count_mismatches", "successful_tool_count_mismatches")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
