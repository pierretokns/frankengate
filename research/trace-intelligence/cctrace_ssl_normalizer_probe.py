#!/usr/bin/env python3
"""Probe grounded SSL-style normalization on a public Claude Code session."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from traject_bench_ssl_trace_normalizer_probe import OUTPUT_SCHEMA, call_frontier


SCHEMA_VERSION = "frankengate-cctrace-ssl-normalizer-probe-v1"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def text_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    values: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "text" and isinstance(item.get("text"), str):
            values.append(item["text"])
    return "\n".join(values)


def parse_episodes(path: Path) -> list[dict[str, Any]]:
    episodes: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        message = row.get("message") if isinstance(row, dict) else None
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if message.get("role") == "user":
            prompt = text_content(content)
            if prompt:
                if current is not None:
                    episodes.append(current)
                current = {"prompt": prompt, "actions": [], "results": [], "assistant_text": []}
            elif current is not None and isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "tool_result":
                        current["results"].append({"tool_use_id": str(item.get("tool_use_id", "")), "content": str(item.get("content", ""))[:1000]})
        elif message.get("role") == "assistant" and current is not None and isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "text" and isinstance(item.get("text"), str):
                    current["assistant_text"].append(item["text"][:1000])
                elif item.get("type") == "tool_use":
                    current["actions"].append({"name": str(item.get("name", "")), "input": item.get("input", {}), "id": str(item.get("id", ""))})
    if current is not None:
        episodes.append(current)
    return [episode for episode in episodes if len(episode["actions"]) >= 2]


def source_payload(episode: dict[str, Any]) -> dict[str, Any]:
    return {
        "trace_kind": "claude_code",
        "user_prompt": episode["prompt"][:3000],
        "ordered_actions": [
            {"order": index, "tool_name": action["name"], "input_keys": sorted(str(key) for key in action["input"].keys()) if isinstance(action.get("input"), dict) else []}
            for index, action in enumerate(episode["actions"])
        ],
        "tool_results": episode["results"][:20],
        "assistant_text": episode["assistant_text"][:5],
    }


def prompt_for(episode: dict[str, Any]) -> str:
    payload = source_payload(episode)
    return (
        "Normalize this real Claude Code trace episode into a grounded Scheduling-Structural-Logical representation. "
        "Return only the JSON schema. Copy every tool name in ordered_actions exactly and preserve order in source_tool_names. "
        "Emit exactly one logical action for each ordered action, with order 0..N-1 and resource equal to the exact tool name. "
        "Use scenes for supported phases such as inspection, editing, execution, verification, or recovery only when the trace supports them. "
        "Every evidence item must be an exact contiguous substring of DATA. Do not infer success, security, permissions, or user intent beyond the source. "
        "Use CALL for tool invocation; use READ/WRITE/CHECK/REPORT only when the tool name, inputs, or result supports it. "
        "SCHEMA:\n" + json.dumps(OUTPUT_SCHEMA, sort_keys=True, separators=(",", ":")) + "\nDATA:\n" + json.dumps(payload, ensure_ascii=False, sort_keys=True)
    )


def evidence_items(value: dict[str, Any]) -> list[str]:
    items: list[str] = []
    structural = value.get("structural", {})
    logical = value.get("logical", {})
    for field in (structural, logical):
        if isinstance(field, dict):
            items.extend(item for item in field.get("evidence", []) if isinstance(item, str))
    if isinstance(structural, dict):
        for scene in structural.get("scenes", []):
            if isinstance(scene, dict):
                items.extend(item for item in scene.get("evidence", []) if isinstance(item, str))
        for transition in structural.get("transitions", []):
            if isinstance(transition, dict):
                items.extend(item for item in transition.get("evidence", []) if isinstance(item, str))
    if isinstance(logical, dict):
        for action in logical.get("actions", []):
            if isinstance(action, dict):
                items.extend(item for item in action.get("evidence", []) if isinstance(item, str))
    return items


def metrics(episode: dict[str, Any], value: dict[str, Any]) -> dict[str, Any]:
    source = json.dumps(source_payload(episode), ensure_ascii=False, sort_keys=True).casefold()
    names = [str(action["name"]) for action in episode["actions"]]
    actual_names = [str(name) for name in value.get("source_tool_names", [])]
    actions = value.get("logical", {}).get("actions", [])
    orders = [int(action.get("order", -1)) for action in actions if isinstance(action, dict)]
    resources = [str(action.get("resource", "")) for action in actions if isinstance(action, dict)]
    evidence = evidence_items(value)
    grounded = [item for item in evidence if item.casefold() in source]
    return {
        "tool_names_exact_order": actual_names == names,
        "logical_action_count_exact": len(actions) == len(names),
        "logical_orders_exact": orders == list(range(len(names))),
        "logical_resources_exact_order": resources == names,
        "identifier_fidelity": actual_names == names and resources == names,
        "evidence_count": len(evidence),
        "grounded_evidence_count": len(grounded),
        "all_evidence_grounded": bool(evidence) and len(grounded) == len(evidence),
        "scene_count": len(value.get("structural", {}).get("scenes", [])),
        "transition_count": len(value.get("structural", {}).get("transitions", [])),
        "action_count": len(actions),
    }


def run(input_path: Path, raw_dir: Path, output: Path, limit: int, timeout_seconds: int) -> dict[str, Any]:
    all_episodes = parse_episodes(input_path)
    # A single 49-tool planning episode would dominate prompt size and latency.
    # Bound the unit to ordinary task episodes while preserving the full trace
    # corpus count in the receipt.
    eligible_episodes = [episode for episode in all_episodes if 3 <= len(episode["actions"]) <= 12]
    episodes = eligible_episodes[:limit]
    raw_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for index, episode in enumerate(episodes):
        prompt = prompt_for(episode)
        prompt_path = raw_dir / f"episode-{index:03d}-prompt.json"
        raw_path = raw_dir / f"episode-{index:03d}-raw.json"
        prompt_path.write_text(json.dumps({"prompt": prompt}, ensure_ascii=False), encoding="utf-8")
        base = {"index": index, "tool_count": len(episode["actions"]), "source_sha256": stable_hash(source_payload(episode)), "prompt_sha256": file_hash(prompt_path)}
        try:
            value, elapsed_ms = call_frontier(prompt, raw_path, timeout_seconds)
            records.append({**base, "status": "ok", "elapsed_ms": elapsed_ms, "response_sha256": stable_hash(value), **metrics(episode, value)})
        except Exception as exc:
            records.append({**base, "status": "error", "error_type": type(exc).__name__, "raw_sha256": file_hash(raw_path) if raw_path.exists() else None})
    ok = [record for record in records if record["status"] == "ok"]
    def rate(field: str) -> float:
        return round(sum(bool(record.get(field)) for record in ok) / len(ok), 6) if ok else 0.0
    result = {
        "schema_version": SCHEMA_VERSION,
        "dataset": {"source_path": str(input_path), "source_sha256": file_hash(input_path), "episodes_available": len(all_episodes), "eligible_bounded_episodes": len(eligible_episodes), "selected": len(episodes), "action_count_bound": [3, 12], "license_manifest": "MIT cctrace portable session", "raw_content_committed": False},
        "protocol": {"model": "gpt-5.6-luna", "normalization_schema": "SSL-shaped with exact tool order and evidence quotes", "raw_prompts_responses_external": True, "retrieval_measured": False, "enterprise_quality_measured": False, "agent_utility_measured": False},
        "aggregate": {"selected": len(episodes), "completed": len(ok), "failures": len(records) - len(ok), "tool_names_exact_order_rate": rate("tool_names_exact_order"), "logical_action_count_exact_rate": rate("logical_action_count_exact"), "logical_orders_exact_rate": rate("logical_orders_exact"), "logical_resources_exact_order_rate": rate("logical_resources_exact_order"), "identifier_fidelity_rate": rate("identifier_fidelity"), "all_evidence_grounded_rate": rate("all_evidence_grounded"), "evidence_grounding_rate": round(sum(record.get("grounded_evidence_count", 0) for record in ok) / max(1, sum(record.get("evidence_count", 0) for record in ok)), 6), "mean_scene_count": round(sum(record.get("scene_count", 0) for record in ok) / len(ok), 6) if ok else 0.0, "mean_transition_count": round(sum(record.get("transition_count", 0) for record in ok) / len(ok), 6) if ok else 0.0, "mean_action_count": round(sum(record.get("action_count", 0) for record in ok) / len(ok), 6) if ok else 0.0, "mean_elapsed_ms": round(sum(record.get("elapsed_ms", 0.0) for record in ok) / len(ok), 3) if ok else 0.0},
        "records": records,
        "claim_boundary": {"grounded_real_trace_normalization_measured": True, "retrieval_lift_measured": False, "semantic_alias_quality_measured": False, "skill_or_artifact_utility_measured": False, "reason": "One MIT-licensed public Claude session; exact order/evidence checks are mechanical proxies and do not establish user intent, correctness, or enterprise transfer."},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["aggregate"], sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--timeout-seconds", type=int, default=240)
    args = parser.parse_args()
    run(args.input, args.raw_dir, args.output, args.limit, args.timeout_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
