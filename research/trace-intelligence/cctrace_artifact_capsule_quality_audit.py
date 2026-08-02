#!/usr/bin/env python3
"""Audit parameter-aware capsule outputs against source action invariants."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from cctrace_artifact_capsule_probe import source_payload
from cctrace_ssl_normalizer_probe import parse_episodes


SCHEMA_VERSION = "frankengate-cctrace-artifact-capsule-quality-audit-v1"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def extract_response(raw_path: Path) -> dict[str, Any]:
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    value = json.loads(str(raw.get("stdout", "")))
    if not isinstance(value, dict) or "logical" not in value:
        raise ValueError(f"capsule response not found: {raw_path}")
    return value


def run(source: Path, receipt: Path, raw_dir: Path, output: Path) -> dict[str, Any]:
    receipt_value = json.loads(receipt.read_text(encoding="utf-8"))
    all_episodes = parse_episodes(source)
    episodes = [episode for episode in all_episodes if 3 <= len(episode["actions"]) <= 12][: int(receipt_value["dataset"]["selected"])]
    rows: list[dict[str, Any]] = []
    for record in receipt_value.get("records", []):
        if record.get("status") != "ok":
            continue
        index = int(record["index"])
        value = extract_response(raw_dir / f"episode-{index:03d}-raw.json")
        expected = [str(action["name"]) for action in episodes[index]["actions"]]
        actions = [item for item in value.get("logical", {}).get("actions", []) if isinstance(item, dict)]
        resources = [str(item.get("resource", "")) for item in actions]
        expected_keys = [sorted(str(key) for key in action.get("input", {}).keys()) if isinstance(action.get("input"), dict) else [] for action in episodes[index]["actions"]]
        observed_keys = [sorted(str(key) for key in item.get("input_keys", [])) for item in actions]
        rows.append({
            "index": index,
            "tool_count": len(expected),
            "top_level_tool_order_exact": [str(name) for name in value.get("source_tool_names", [])] == expected,
            "per_action_resource_order_exact": resources == expected,
            "action_count_exact": len(actions) == len(expected),
            "input_keys_exact": observed_keys == expected_keys,
            "safe_template_count": sum(str(item.get("parameterization")) == "safe_template" for item in actions),
            "literal_only_count": sum(str(item.get("parameterization")) == "literal_only" for item in actions),
            "not_replayable_count": sum(str(item.get("parameterization")) == "not_replayable" for item in actions),
        })
    total_actions = max(1, sum(row["tool_count"] for row in rows))
    result = {
        "schema_version": SCHEMA_VERSION,
        "source": {"trace_source_sha256": file_hash(source), "capsule_receipt_sha256": file_hash(receipt), "raw_dir_external": True, "raw_content_committed": False},
        "aggregate": {
            "records_audited": len(rows),
            "top_level_tool_order_exact_rate": round(sum(row["top_level_tool_order_exact"] for row in rows) / len(rows), 6) if rows else 0.0,
            "per_action_resource_order_exact_rate": round(sum(row["per_action_resource_order_exact"] for row in rows) / len(rows), 6) if rows else 0.0,
            "action_count_exact_rate": round(sum(row["action_count_exact"] for row in rows) / len(rows), 6) if rows else 0.0,
            "input_keys_exact_rate": round(sum(row["input_keys_exact"] for row in rows) / len(rows), 6) if rows else 0.0,
            "safe_template_rate": round(sum(row["safe_template_count"] for row in rows) / total_actions, 6),
            "literal_only_rate": round(sum(row["literal_only_count"] for row in rows) / total_actions, 6),
            "not_replayable_rate": round(sum(row["not_replayable_count"] for row in rows) / total_actions, 6),
        },
        "records": rows,
        "claim_boundary": {"parameter_roundtrip_measured": True, "replay_executed": False, "artifact_correctness_measured": False, "reason": "Per-action key/resource round-trip and model classifications only; no command replay or user outcome."},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["aggregate"], sort_keys=True))
    return result


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
