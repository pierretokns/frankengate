#!/usr/bin/env python3
"""Evaluate tool-artifact priors under a frozen chronological holdout.

The temporal benchmark updates priors after every session.  This companion
probe is deliberately stricter: the first chronological half is the only
training history, and every call in the second half is scored without updating
the prior sets.  It measures drift/transfer rather than cumulative reuse.

Only aggregate counts, timestamps, and hashes are emitted; no trace content,
tool arguments, paths, or result text are written.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from claude_history_tool_artifact_miner import digest, manifest
from claude_history_tool_artifact_temporal_benchmark import parse_sessions, tool_category


SCHEMA_VERSION = "frankengate-claude-history-tool-artifact-drift-v1"


def bucket() -> dict[str, int]:
    return {"uses": 0, "successes": 0, "errors": 0}


def add(value: dict[str, int], failed: bool) -> None:
    value["uses"] += 1
    value["errors" if failed else "successes"] += 1


def summarize(value: dict[str, int]) -> dict[str, Any]:
    return {
        **value,
        "success_rate": round(value["successes"] / value["uses"], 6) if value["uses"] else 0.0,
    }


def rate(value: dict[str, int]) -> float:
    return value["successes"] / value["uses"] if value["uses"] else 0.0


def classify(
    fingerprint: str,
    project: str,
    global_success: set[str],
    project_success: dict[str, set[str]],
    no_prior: str,
    same_project: str,
    other_project: str,
) -> str:
    if fingerprint in project_success[project]:
        return same_project
    if fingerprint in global_success:
        return other_project
    return no_prior


def run(root: Path, output: Path) -> dict[str, Any]:
    root = root.resolve(strict=True)
    file_count, byte_count, manifest_hash = manifest(root)
    sessions, parse_stats = parse_sessions(root)
    split = max(1, len(sessions) // 2)
    early = sessions[:split]
    late = sessions[split:]

    exact_global: set[str] = set()
    exact_project: dict[str, set[str]] = defaultdict(set)
    shape_global: set[str] = set()
    shape_project: dict[str, set[str]] = defaultdict(set)
    for session in early:
        project = session["project"]
        for fingerprint, keyshape, failed, _category in session["calls"]:
            if failed:
                continue
            exact_global.add(fingerprint)
            exact_project[project].add(fingerprint)
            shape_global.add(keyshape)
            shape_project[project].add(keyshape)

    exact_buckets: dict[str, dict[str, int]] = defaultdict(bucket)
    shape_buckets: dict[str, dict[str, int]] = defaultdict(bucket)
    category_buckets: dict[str, dict[str, dict[str, int]]] = defaultdict(lambda: defaultdict(bucket))
    shape_category_buckets: dict[str, dict[str, dict[str, int]]] = defaultdict(lambda: defaultdict(bucket))
    category_counts: Counter[str] = Counter()

    for session in late:
        project = session["project"]
        for fingerprint, keyshape, failed, category in session["calls"]:
            exact_class = classify(
                fingerprint,
                project,
                exact_global,
                exact_project,
                "no_early_prior_success",
                "early_same_project_success",
                "early_other_project_success_only",
            )
            shape_class = classify(
                keyshape,
                project,
                shape_global,
                shape_project,
                "no_early_prior_keyshape_success",
                "early_same_project_keyshape_success",
                "early_other_project_keyshape_success_only",
            )
            add(exact_buckets[exact_class], failed)
            add(shape_buckets[shape_class], failed)
            add(category_buckets[category][exact_class], failed)
            add(shape_category_buckets[category][shape_class], failed)
            category_counts[category] += 1

    exact_baseline = exact_buckets["no_early_prior_success"]
    shape_baseline = shape_buckets["no_early_prior_keyshape_success"]
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "root_name": root.name,
            "file_count": file_count,
            "byte_count": byte_count,
            "manifest_sha256": manifest_hash,
            "session_count": len(sessions),
            "early_session_count": len(early),
            "late_session_count": len(late),
            "early_start": early[0]["start"] if early else "",
            "cutoff_start": late[0]["start"] if late else "",
            "late_end": late[-1]["start"] if late else "",
            "raw_content_committed": False,
        },
        "protocol": {
            "split": "chronological session half; early sessions build priors, late sessions are frozen evaluation",
            "ordering": "recorded session timestamp, then path",
            "identity": "strict tool name plus normalized input; parameterized control uses tool name plus input-key set",
            "outcome": "explicit tool_result is_error flag",
            "late_priors_updated": False,
        },
        "coverage": {
            **parse_stats,
            "early_paired_call_count": sum(len(session["calls"]) for session in early),
            "late_paired_call_count": sum(len(session["calls"]) for session in late),
            "early_successful_exact_count": len(exact_global),
            "early_successful_keyshape_count": len(shape_global),
        },
        "exact_buckets": {name: summarize(value) for name, value in sorted(exact_buckets.items())},
        "parameterized_buckets": {name: summarize(value) for name, value in sorted(shape_buckets.items())},
        "category_buckets": {
            category: {
                "call_count": category_counts[category],
                "exact": {name: summarize(value) for name, value in sorted(values.items())},
                "parameterized": {name: summarize(value) for name, value in sorted(shape_category_buckets[category].items())},
            }
            for category, values in sorted(category_buckets.items())
        },
        "comparison": {
            "early_same_project_lift_vs_no_early_prior": round(
                rate(exact_buckets["early_same_project_success"]) - rate(exact_baseline), 6
            ),
            "early_other_project_lift_vs_no_early_prior": round(
                rate(exact_buckets["early_other_project_success_only"]) - rate(exact_baseline), 6
            ),
            "early_same_project_keyshape_lift_vs_no_early_prior_keyshape": round(
                rate(shape_buckets["early_same_project_keyshape_success"]) - rate(shape_baseline), 6
            ),
            "early_other_project_keyshape_lift_vs_no_early_prior_keyshape": round(
                rate(shape_buckets["early_other_project_keyshape_success_only"]) - rate(shape_baseline), 6
            ),
        },
        "claim_boundary": {
            "semantic_correctness": False,
            "safety": False,
            "causal_user_benefit": False,
            "reason": "A frozen chronological association measures drift and transfer of observed process success, not semantic intent, safety, optimality, or causal artifact utility.",
        },
    }
    result["result_sha256"] = digest(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"coverage": result["coverage"], "exact_buckets": result["exact_buckets"], "parameterized_buckets": result["parameterized_buckets"], "comparison": result["comparison"]}, sort_keys=True))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.input, args.output)
