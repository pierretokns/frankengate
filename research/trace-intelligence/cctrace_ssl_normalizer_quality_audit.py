#!/usr/bin/env python3
"""Audit normalized cctrace outputs against deterministic source invariants."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from cctrace_ssl_normalizer_probe import parse_episodes


SCHEMA_VERSION = "frankengate-cctrace-ssl-normalizer-quality-audit-v1"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def extract_response(raw_path: Path) -> dict[str, Any]:
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    stdout = str(raw.get("stdout", ""))
    decoder = json.JSONDecoder()
    # Codex emits the final JSON object between a `codex` marker and the token
    # diagnostic. Try every object boundary and select the normalized schema.
    starts = [0] + [match.start() + 1 for match in re.finditer(r"\n\{", stdout)]
    for start in starts:
        try:
            value, _ = decoder.raw_decode(stdout[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and "source_tool_names" in value and "logical" in value:
            return value
    raise ValueError(f"normalized response not found: {raw_path}")


def expected_act_type(tool_name: str) -> str:
    name = tool_name.casefold()
    if name in {"read", "grep", "glob", "ls", "search"}:
        return "READ"
    if name in {"edit", "write", "notebookedit", "multiedit"}:
        return "WRITE"
    return "CALL"


def audit_record(episode: dict[str, Any], value: dict[str, Any]) -> dict[str, Any]:
    names = [str(action["name"]) for action in episode["actions"]]
    actions = [item for item in value.get("logical", {}).get("actions", []) if isinstance(item, dict)]
    orders = [int(item.get("order", -1)) for item in actions]
    scene_orders: list[int] = []
    scene_names: list[str] = []
    for scene in value.get("structural", {}).get("scenes", []):
        if not isinstance(scene, dict):
            continue
        scene_names.append(str(scene.get("name", "")))
        scene_orders.extend(int(order) for order in scene.get("action_orders", []) if isinstance(order, int))
    transitions = [item for item in value.get("structural", {}).get("transitions", []) if isinstance(item, dict)]
    valid_transition_refs = all(str(item.get("from_scene", "")) in scene_names and str(item.get("to_scene", "")) in scene_names for item in transitions)
    expected = [expected_act_type(name) for name in names]
    observed = [str(item.get("act_type", "")) for item in actions]
    return {
        "tool_count": len(names),
        "action_count": len(actions),
        "action_order_exact": orders == list(range(len(names))),
        "action_type_accuracy": sum(left == right for left, right in zip(observed, expected)) / len(names) if names else 0.0,
        "scene_action_coverage": len(set(scene_orders) & set(range(len(names)))) / len(names) if names else 0.0,
        "scene_duplicate_order_count": len(scene_orders) - len(set(scene_orders)),
        "scene_count": len(scene_names),
        "transition_count": len(transitions),
        "transition_refs_valid": valid_transition_refs,
        "all_actions_in_scene": set(scene_orders) >= set(range(len(names))),
    }


def run(source: Path, receipt: Path, raw_dir: Path, output: Path) -> dict[str, Any]:
    result = json.loads(receipt.read_text(encoding="utf-8"))
    episodes = [episode for episode in parse_episodes(source) if 3 <= len(episode["actions"]) <= 12][: int(result["dataset"]["selected"])]
    rows: list[dict[str, Any]] = []
    for record in result.get("records", []):
        if record.get("status") != "ok":
            continue
        index = int(record["index"])
        value = extract_response(raw_dir / f"episode-{index:03d}-raw.json")
        audit = audit_record(episodes[index], value)
        rows.append({"index": index, **audit})
    metric_fields = ("action_order_exact", "transition_refs_valid", "all_actions_in_scene")
    aggregate = {
        "records_audited": len(rows),
        "action_order_exact_rate": round(sum(bool(row["action_order_exact"]) for row in rows) / len(rows), 6) if rows else 0.0,
        "action_type_accuracy": round(sum(float(row["action_type_accuracy"]) * row["tool_count"] for row in rows) / max(1, sum(row["tool_count"] for row in rows)), 6),
        "mean_scene_action_coverage": round(sum(float(row["scene_action_coverage"]) for row in rows) / len(rows), 6) if rows else 0.0,
        "all_actions_in_scene_rate": round(sum(bool(row["all_actions_in_scene"]) for row in rows) / len(rows), 6) if rows else 0.0,
        "transition_refs_valid_rate": round(sum(bool(row["transition_refs_valid"]) for row in rows) / len(rows), 6) if rows else 0.0,
        "mean_scene_duplicate_order_count": round(sum(int(row["scene_duplicate_order_count"]) for row in rows) / len(rows), 6) if rows else 0.0,
    }
    output_value = {
        "schema_version": SCHEMA_VERSION,
        "source": {"trace_source_sha256": file_hash(source), "normalizer_receipt_sha256": file_hash(receipt), "raw_dir_external": True, "raw_content_committed": False},
        "protocol": {"expected_act_type_mapping": "Read/Grep/Glob/LS/Search=READ; Edit/Write/NotebookEdit/MultiEdit=WRITE; other observed tool names=CALL", "checks": ["action order", "tool-effect type", "scene coverage", "transition references"]},
        "aggregate": aggregate,
        "records": rows,
        "claim_boundary": {"deterministic_structure_quality_measured": True, "human_semantic_quality_measured": False, "task_correctness_measured": False, "skill_or_artifact_utility_measured": False, "reason": "Source invariants and conservative tool-name mapping only; no human labels or independent task outcome."},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(output_value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(aggregate, sort_keys=True))
    return output_value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.source, args.receipt, args.raw_dir, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
