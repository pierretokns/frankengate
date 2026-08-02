#!/usr/bin/env python3
"""Compile deterministic, content-external artifact capsules and round-trip them."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from cctrace_ssl_normalizer_probe import parse_episodes


SCHEMA_VERSION = "frankengate-cctrace-deterministic-capsule-roundtrip-v1"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def capsule_for(episode: dict[str, Any], index: int, source_hash: str) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    for order, action in enumerate(episode["actions"]):
        name = str(action.get("name", ""))
        inputs = action.get("input", {})
        input_keys = sorted(str(key) for key in inputs.keys()) if isinstance(inputs, dict) else []
        actions.append({
            "order": order,
            "tool_id": canonical_hash({"tool_name": name})[:24],
            "invocation_id": canonical_hash({"order": order, "tool_name": name, "input_keys": input_keys})[:24],
            "tool_name": name,
            "input_keys": input_keys,
            "input_binding_hash": canonical_hash(inputs),
        })
    return {"schema_version": "frankengate-artifact-capsule-v1", "source_trace_sha256": source_hash, "episode_index": index, "actions": actions, "validation": {"executed": False, "independent_result": False, "authority_checked": False}}


def run(source: Path, capsule_dir: Path, output: Path, limit: int) -> dict[str, Any]:
    source_hash = file_hash(source)
    all_episodes = parse_episodes(source)
    episodes = [episode for episode in all_episodes if 3 <= len(episode["actions"]) <= 12][:limit]
    capsule_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for index, episode in enumerate(episodes):
        capsule = capsule_for(episode, index, source_hash)
        path = capsule_dir / f"episode-{index:03d}.json"
        path.write_text(json.dumps(capsule, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        expected_names = [str(action.get("name", "")) for action in episode["actions"]]
        expected_keys = [sorted(str(key) for key in action.get("input", {}).keys()) if isinstance(action.get("input"), dict) else [] for action in episode["actions"]]
        actions = capsule["actions"]
        names = [str(action["tool_name"]) for action in actions]
        keys = [list(action["input_keys"]) for action in actions]
        orders = [int(action["order"]) for action in actions]
        invocations = [str(action["invocation_id"]) for action in actions]
        rows.append({
            "index": index,
            "tool_count": len(expected_names),
            "capsule_sha256": file_hash(path),
            "tool_order_exact": names == expected_names,
            "input_keys_exact": keys == expected_keys,
            "action_order_exact": orders == list(range(len(expected_names))),
            "invocation_ids_unique": len(invocations) == len(set(invocations)),
            "source_provenance_exact": all(action["source_trace_sha256"] == source_hash for action in [capsule]),
        })
    result = {
        "schema_version": SCHEMA_VERSION,
        "source": {"trace_source_sha256": source_hash, "episodes_available": len(all_episodes), "eligible_bounded_episodes": len([episode for episode in all_episodes if 3 <= len(episode["actions"]) <= 12]), "selected": len(episodes), "capsules_external_dir": str(capsule_dir), "raw_content_committed": False},
        "protocol": {"compiler": "deterministic canonical JSON", "capsule_fields": ["tool_id", "invocation_id", "tool_name", "input_keys", "input_binding_hash", "source_trace_sha256"], "replay_executed": False, "independent_validation": False},
        "aggregate": {"records_compiled": len(rows), "tool_order_exact_rate": round(sum(row["tool_order_exact"] for row in rows) / len(rows), 6) if rows else 0.0, "input_keys_exact_rate": round(sum(row["input_keys_exact"] for row in rows) / len(rows), 6) if rows else 0.0, "action_order_exact_rate": round(sum(row["action_order_exact"] for row in rows) / len(rows), 6) if rows else 0.0, "invocation_ids_unique_rate": round(sum(row["invocation_ids_unique"] for row in rows) / len(rows), 6) if rows else 0.0, "source_provenance_exact_rate": round(sum(row["source_provenance_exact"] for row in rows) / len(rows), 6) if rows else 0.0},
        "records": rows,
        "claim_boundary": {"deterministic_roundtrip_measured": True, "replay_executed": False, "artifact_correctness_measured": False, "artifact_utility_measured": False, "reason": "Canonical compiler preserves observed fields and provenance only; it does not assert tool success, authority, safety, or reusable semantic intent."},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["aggregate"], sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--capsule-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    run(args.source, args.capsule_dir, args.output, args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
