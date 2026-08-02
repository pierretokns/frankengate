#!/usr/bin/env python3
"""Measure whether prior successful tool artifacts predict later outcomes.

This is a temporal, content-minimized benchmark over paired Claude
``tool_use``/``tool_result`` events.  Prior-success sets are frozen at the
start of each session, so within-session repetition cannot leak into the
prediction.  Only counts and hashes are emitted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from claude_history_tool_artifact_miner import digest, manifest, normalize


SCHEMA_VERSION = "frankengate-claude-history-tool-artifact-temporal-v1"


def parse_sessions(root: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    sessions: list[dict[str, Any]] = []
    parse_errors = 0
    missing_timestamps = 0
    for path in sorted(root.rglob("*.jsonl")):
        project = path.parent.name
        uses: list[tuple[str, str, bool]] = []
        timestamps: list[str] = []
        statuses: dict[str, bool] = {}
        try:
            with path.open(encoding="utf-8", errors="ignore") as handle:
                for line in handle:
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        parse_errors += 1
                        continue
                    if isinstance(record, dict) and isinstance(record.get("timestamp"), str):
                        timestamps.append(record["timestamp"])
                    message = record.get("message") if isinstance(record, dict) else None
                    content = message.get("content") if isinstance(message, dict) else None
                    if not isinstance(content, list):
                        continue
                    for item in content:
                        if not isinstance(item, dict):
                            continue
                        if item.get("type") == "tool_use" and item.get("id"):
                            tool_name = str(item.get("name") or "<missing>").lower()
                            normalized_input = normalize(item.get("input"))
                            fingerprint = digest({"tool": tool_name, "input": normalized_input})
                            keyshape = digest({"tool": tool_name, "input_keys": sorted(normalized_input) if isinstance(normalized_input, dict) else []})
                            uses.append((str(item["id"]), fingerprint, keyshape))
                        elif item.get("type") == "tool_result" and item.get("tool_use_id"):
                            statuses[str(item["tool_use_id"])] = bool(item.get("is_error", False))
        except OSError:
            continue
        paired = [(fingerprint, keyshape, failed) for tool_id, fingerprint, keyshape in uses if (tool_id in statuses) for failed in (statuses[tool_id],)]
        if not paired:
            continue
        start = min(timestamps) if timestamps else ""
        if not start:
            missing_timestamps += 1
        sessions.append(
            {
                "path": str(path),
                "project": project,
                "project_hash": digest(project),
                "start": start,
                "calls": paired,
            }
        )
    sessions.sort(key=lambda row: (row["start"], row["path"]))
    return sessions, {"parse_error_count": parse_errors, "missing_timestamp_session_count": missing_timestamps}


def bucket() -> dict[str, int]:
    return {"uses": 0, "successes": 0, "errors": 0}


def add(bucket_value: dict[str, int], failed: bool) -> None:
    bucket_value["uses"] += 1
    bucket_value["errors" if failed else "successes"] += 1


def summarize(value: dict[str, int]) -> dict[str, Any]:
    return {
        **value,
        "success_rate": round(value["successes"] / value["uses"], 6) if value["uses"] else 0.0,
    }


def run(root: Path, output: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    file_count, byte_count, manifest_hash = manifest(root)
    sessions, parse_stats = parse_sessions(root)
    global_success: set[str] = set()
    project_success: dict[str, set[str]] = defaultdict(set)
    global_keyshape_success: set[str] = set()
    project_keyshape_success: dict[str, set[str]] = defaultdict(set)
    buckets: dict[str, dict[str, int]] = defaultdict(bucket)
    parameter_buckets: dict[str, dict[str, int]] = defaultdict(bucket)
    session_artifacts: Counter[str] = Counter()
    first_success_rank: dict[str, int] = {}
    call_index = 0

    for session in sessions:
        project = session["project"]
        project_seen = project_success[project]
        for fingerprint, keyshape, failed in session["calls"]:
            call_index += 1
            same_prior = fingerprint in project_seen
            any_prior = fingerprint in global_success
            if same_prior:
                category = "prior_same_project_success"
            elif any_prior:
                category = "prior_other_project_success_only"
            else:
                category = "no_prior_success"
            add(buckets[category], failed)
            if keyshape in project_keyshape_success[project]:
                parameter_category = "parameter_same_project_success"
            elif keyshape in global_keyshape_success:
                parameter_category = "parameter_other_project_success_only"
            else:
                parameter_category = "no_prior_keyshape_success"
            add(parameter_buckets[parameter_category], failed)
            session_artifacts[fingerprint] += 1
            if not failed and fingerprint not in first_success_rank:
                first_success_rank[fingerprint] = call_index
        # Freeze priors at the session boundary; no within-session leakage.
        for fingerprint, keyshape, failed in session["calls"]:
            if not failed:
                global_success.add(fingerprint)
                project_seen.add(fingerprint)
                global_keyshape_success.add(keyshape)
                project_keyshape_success[project].add(keyshape)

    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "root_name": root.name,
            "file_count": file_count,
            "byte_count": byte_count,
            "manifest_sha256": manifest_hash,
            "session_count": len(sessions),
            "raw_content_committed": False,
        },
        "protocol": {
            "ordering": "session start timestamp, then path; missing timestamps use deterministic path order",
            "prior_freeze": "prior success sets updated only after each session completes",
            "identity": "strict tool name plus normalized input; paths, UUIDs, and multi-digit numbers canonicalized",
            "outcome": "explicit tool_result is_error flag",
        },
        "coverage": {
            **parse_stats,
            "paired_call_count": sum(value["uses"] for value in buckets.values()),
            "distinct_artifact_count": len(session_artifacts),
            "distinct_successful_artifact_count": len(global_success),
            "distinct_keyshape_count": len(global_keyshape_success),
        },
        "buckets": {name: summarize(value) for name, value in sorted(buckets.items())},
        "parameter_buckets": {name: summarize(value) for name, value in sorted(parameter_buckets.items())},
        "comparison": {
            "same_project_lift_vs_no_prior": round(
                (buckets["prior_same_project_success"]["successes"] / buckets["prior_same_project_success"]["uses"])
                - (buckets["no_prior_success"]["successes"] / buckets["no_prior_success"]["uses"]),
                6,
            ) if buckets["prior_same_project_success"]["uses"] and buckets["no_prior_success"]["uses"] else 0.0,
            "other_project_lift_vs_no_prior": round(
                (buckets["prior_other_project_success_only"]["successes"] / buckets["prior_other_project_success_only"]["uses"])
                - (buckets["no_prior_success"]["successes"] / buckets["no_prior_success"]["uses"]),
                6,
            ) if buckets["prior_other_project_success_only"]["uses"] and buckets["no_prior_success"]["uses"] else 0.0,
            "parameter_same_project_lift_vs_no_prior_keyshape": round(
                (parameter_buckets["parameter_same_project_success"]["successes"] / parameter_buckets["parameter_same_project_success"]["uses"])
                - (parameter_buckets["no_prior_keyshape_success"]["successes"] / parameter_buckets["no_prior_keyshape_success"]["uses"]),
                6,
            ) if parameter_buckets["parameter_same_project_success"]["uses"] and parameter_buckets["no_prior_keyshape_success"]["uses"] else 0.0,
            "parameter_other_project_lift_vs_no_prior_keyshape": round(
                (parameter_buckets["parameter_other_project_success_only"]["successes"] / parameter_buckets["parameter_other_project_success_only"]["uses"])
                - (parameter_buckets["no_prior_keyshape_success"]["successes"] / parameter_buckets["no_prior_keyshape_success"]["uses"]),
                6,
            ) if parameter_buckets["parameter_other_project_success_only"]["uses"] and parameter_buckets["no_prior_keyshape_success"]["uses"] else 0.0,
        },
        "claim_boundary": {
            "semantic_correctness": False,
            "safety": False,
            "causal_user_benefit": False,
            "reason": "Observed tool success is a process outcome only; this temporal association does not establish semantic intent, safety, optimality, or causal artifact utility.",
        },
    }
    result["result_sha256"] = digest(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"coverage": result["coverage"], "buckets": result["buckets"], "comparison": result["comparison"]}, sort_keys=True))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.input, args.output)
