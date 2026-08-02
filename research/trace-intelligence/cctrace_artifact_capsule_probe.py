#!/usr/bin/env python3
"""Probe parameter-aware artifact extraction from real coding traces."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from cctrace_ssl_normalizer_probe import parse_episodes


MODEL = "gpt-5.6-luna"
SCHEMA_VERSION = "frankengate-cctrace-artifact-capsule-probe-v1"
PARAM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["source_tool_names", "logical"],
    "properties": {
        "source_tool_names": {"type": "array", "items": {"type": "string"}},
        "logical": {
            "type": "object",
            "additionalProperties": False,
            "required": ["actions", "evidence"],
            "properties": {
                "actions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["order", "resource", "act_type", "input_keys", "parameterization", "template", "evidence"],
                        "properties": {
                            "order": {"type": "integer", "minimum": 0},
                            "resource": {"type": "string"},
                            "act_type": {"type": "string", "enum": ["READ", "CALL", "WRITE", "REPORT", "CHECK", "ACT"]},
                            "input_keys": {"type": "array", "items": {"type": "string"}},
                            "parameterization": {"type": "string", "enum": ["safe_template", "literal_only", "not_replayable", "unknown"]},
                            "template": {"type": "string"},
                            "evidence": {"type": "array", "minItems": 1, "items": {"type": "string"}},
                        },
                    },
                },
                "evidence": {"type": "array", "minItems": 1, "items": {"type": "string"}},
            },
        },
    },
}


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def source_payload(episode: dict[str, Any]) -> dict[str, Any]:
    actions = []
    for index, action in enumerate(episode["actions"]):
        value = action.get("input", {})
        actions.append({
            "order": index,
            "tool_name": str(action.get("name", "")),
            "input_keys": sorted(str(key) for key in value.keys()) if isinstance(value, dict) else [],
            "input_shape": type(value).__name__,
            "input_preview": json.dumps(value, ensure_ascii=False, sort_keys=True)[:1200],
        })
    return {"user_prompt": episode["prompt"][:3000], "ordered_actions": actions, "tool_results": episode["results"][:20], "assistant_text": episode["assistant_text"][:5]}


def prompt_for(episode: dict[str, Any]) -> str:
    payload = source_payload(episode)
    return (
        "Extract artifact-capsule metadata from this real coding trace. Return only the JSON schema. "
        "Preserve every tool name and action order exactly. For each action, copy input_keys exactly from ordered_actions. "
        "A safe_template is allowed only when the source supports replacing values without changing the operation; otherwise use literal_only, not_replayable, or unknown. "
        "Do not invent parameters, side effects, authorization, success, or replay safety. A template may use placeholders such as <value>, but it must preserve the operation shape and be grounded in the source. "
        "Every evidence item must be an exact contiguous substring of DATA. "
        "SCHEMA:\n" + json.dumps(PARAM_SCHEMA, sort_keys=True, separators=(",", ":")) + "\nDATA:\n" + json.dumps(payload, ensure_ascii=False, sort_keys=True)
    )


def call_frontier(prompt: str, raw_path: Path, timeout_seconds: int) -> tuple[dict[str, Any], float]:
    with tempfile.TemporaryDirectory(prefix="frankengate-artifact-capsule-") as directory:
        root = Path(directory)
        schema = root / "schema.json"
        output = root / "output.json"
        schema.write_text(json.dumps(PARAM_SCHEMA), encoding="utf-8")
        command = ["codex", "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules", "--skip-git-repo-check", "-s", "read-only", "-m", MODEL, "--output-schema", str(schema), "--output-last-message", str(output)]
        started = time.perf_counter()
        completed = subprocess.run(command, input=prompt, text=True, capture_output=True, timeout=timeout_seconds, cwd="/private/tmp", check=False)
        elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)
        raw_path.write_text(json.dumps({"returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}, ensure_ascii=False), encoding="utf-8")
        if completed.returncode != 0 or not output.exists():
            raise RuntimeError(f"frontier call failed: {completed.stderr[-1000:]}")
        value = json.loads(output.read_text(encoding="utf-8"))
    return value, elapsed_ms


def evidence_items(value: dict[str, Any]) -> list[str]:
    items: list[str] = []
    logical = value.get("logical", {})
    if isinstance(logical, dict):
        items.extend(item for item in logical.get("evidence", []) if isinstance(item, str))
        for action in logical.get("actions", []):
            if isinstance(action, dict):
                items.extend(item for item in action.get("evidence", []) if isinstance(item, str))
    return items


def metrics(episode: dict[str, Any], value: dict[str, Any]) -> dict[str, Any]:
    source = json.dumps(source_payload(episode), ensure_ascii=False, sort_keys=True).casefold()
    expected = [action for action in source_payload(episode)["ordered_actions"]]
    actions = [item for item in value.get("logical", {}).get("actions", []) if isinstance(item, dict)]
    names = [str(item.get("tool_name", "")) for item in expected]
    actual_names = [str(item) for item in value.get("source_tool_names", [])]
    key_fidelity: list[bool] = []
    template_grounded: list[bool] = []
    for index, action in enumerate(actions):
        if index >= len(expected):
            continue
        key_fidelity.append(sorted(str(key) for key in action.get("input_keys", [])) == expected[index]["input_keys"])
        template = str(action.get("template", ""))
        template_grounded.append(not template or template.casefold() in source)
    evidence = evidence_items(value)
    grounded = [item for item in evidence if item.casefold() in source]
    parameterizations = [str(action.get("parameterization", "unknown")) for action in actions]
    return {
        "tool_names_exact_order": actual_names == names,
        "action_count_exact": len(actions) == len(expected),
        "input_key_fidelity": sum(key_fidelity) / len(expected) if expected else 0.0,
        "template_grounding_rate": sum(template_grounded) / len(template_grounded) if template_grounded else 0.0,
        "safe_template_count": parameterizations.count("safe_template"),
        "literal_only_count": parameterizations.count("literal_only"),
        "not_replayable_count": parameterizations.count("not_replayable"),
        "evidence_count": len(evidence),
        "grounded_evidence_count": len(grounded),
        "all_evidence_grounded": bool(evidence) and len(grounded) == len(evidence),
    }


def run(input_path: Path, raw_dir: Path, output: Path, limit: int, timeout_seconds: int) -> dict[str, Any]:
    all_episodes = parse_episodes(input_path)
    episodes = [episode for episode in all_episodes if 3 <= len(episode["actions"]) <= 12][:limit]
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
    total_actions = max(1, sum(record.get("tool_count", 0) for record in ok))
    result = {
        "schema_version": SCHEMA_VERSION,
        "dataset": {"source_path": str(input_path), "source_sha256": file_hash(input_path), "episodes_available": len(all_episodes), "eligible_bounded_episodes": len([episode for episode in all_episodes if 3 <= len(episode["actions"]) <= 12]), "selected": len(episodes), "raw_content_committed": False},
        "protocol": {"model": MODEL, "normalization_schema": "parameter-aware artifact capsule with exact input-key evidence", "raw_prompts_responses_external": True, "replay_executed": False, "artifact_utility_measured": False, "enterprise_quality_measured": False},
        "aggregate": {"selected": len(episodes), "completed": len(ok), "failures": len(records) - len(ok), "tool_names_exact_order_rate": rate("tool_names_exact_order"), "action_count_exact_rate": rate("action_count_exact"), "input_key_fidelity": round(sum(record.get("input_key_fidelity", 0.0) * record.get("tool_count", 0) for record in ok) / total_actions, 6), "template_grounding_rate": round(sum(record.get("template_grounding_rate", 0.0) * record.get("tool_count", 0) for record in ok) / total_actions, 6), "all_evidence_grounded_rate": rate("all_evidence_grounded"), "evidence_grounding_rate": round(sum(record.get("grounded_evidence_count", 0) for record in ok) / max(1, sum(record.get("evidence_count", 0) for record in ok)), 6), "safe_template_rate": round(sum(record.get("safe_template_count", 0) for record in ok) / total_actions, 6), "literal_only_rate": round(sum(record.get("literal_only_count", 0) for record in ok) / total_actions, 6), "not_replayable_rate": round(sum(record.get("not_replayable_count", 0) for record in ok) / total_actions, 6), "mean_elapsed_ms": round(sum(record.get("elapsed_ms", 0.0) for record in ok) / len(ok), 3) if ok else 0.0},
        "records": records,
        "claim_boundary": {"parameter_extraction_measured": True, "replay_executed": False, "artifact_utility_measured": False, "semantic_alias_quality_measured": False, "reason": "One public session and model-proposed templates; input-key fidelity and evidence checks are mechanical, not replay or user-utility evidence."},
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
