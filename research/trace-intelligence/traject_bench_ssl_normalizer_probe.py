#!/usr/bin/env python3
"""Probe frontier-grounded SSL-style normalization on public tool records.

This tests extraction/grounding feasibility, not retrieval or agent utility.
Raw prompts and model responses stay in an external directory.  The committed
receipt contains only hashes, counts, and verifier-friendly booleans.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


MODEL = "gpt-5.6-luna"
SCHEMA_VERSION = "frankengate-traject-bench-ssl-normalizer-probe-v1"
ACT_TYPES = ["READ", "CALL", "WRITE", "REPORT", "CHECK", "SCENE", "ACT", "END"]
OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["source_tool_name", "source_api_name", "source_domain_name", "source_parameter_names", "scheduling", "structural", "logical"],
    "properties": {
        "source_tool_name": {"type": "string"},
        "source_api_name": {"type": "string"},
        "source_domain_name": {"type": "string"},
        "source_parameter_names": {"type": "array", "items": {"type": "string"}},
        "scheduling": {
            "type": "object",
            "additionalProperties": False,
            "required": ["supported_intents", "evidence"],
            "properties": {
                "supported_intents": {"type": "array", "items": {"type": "string"}},
                "evidence": {"type": "array", "minItems": 1, "items": {"type": "string"}},
            },
        },
        "structural": {
            "type": "object",
            "additionalProperties": False,
            "required": ["scenes", "transitions", "evidence"],
            "properties": {
                "scenes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["name", "purpose", "evidence"],
                        "properties": {"name": {"type": "string"}, "purpose": {"type": "string"}, "evidence": {"type": "array", "minItems": 1, "items": {"type": "string"}}},
                    },
                },
                "transitions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["from", "to", "condition", "evidence"],
                        "properties": {"from": {"type": "string"}, "to": {"type": "string"}, "condition": {"type": "string"}, "evidence": {"type": "array", "minItems": 1, "items": {"type": "string"}}},
                    },
                },
                "evidence": {"type": "array", "minItems": 1, "items": {"type": "string"}},
            },
        },
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
                        "required": ["act_type", "resource", "effect", "evidence"],
                        "properties": {"act_type": {"type": "string", "enum": ACT_TYPES}, "resource": {"type": "string"}, "effect": {"type": "string"}, "evidence": {"type": "array", "minItems": 1, "items": {"type": "string"}}},
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


def source_payload(tool: dict[str, Any]) -> dict[str, Any]:
    return {
        "tool_name": str(tool.get("tool name", "")),
        "parent_tool_name": str(tool.get("parent tool name", "")),
        "parent_tool_description": str(tool.get("parent tool description", "")),
        "tool_description": str(tool.get("tool description", "")),
        "api_name": str(tool.get("API name", "")),
        "domain_name": str(tool.get("domain name", "")),
        "required_parameters": tool.get("required_parameters", []),
        "optional_parameters": tool.get("optional_parameters", []),
        "output_info": tool.get("output_info", {}),
        "connected_tool_names": [str(item.get("tool name", "")) for item in tool.get("connected tools", []) if isinstance(item, dict)],
    }


def source_text(tool: dict[str, Any]) -> str:
    payload = source_payload(tool)
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def select_tools(root: Path, per_domain: int) -> list[dict[str, Any]]:
    tools = json.loads((root / "tools" / "all_tools.json").read_text(encoding="utf-8"))
    by_domain: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen: set[str] = set()
    for tool in sorted(tools, key=lambda item: (str(item.get("domain name", "")), str(item.get("tool name", "")))):
        name = str(tool.get("tool name", ""))
        if not name or name in seen:
            continue
        seen.add(name)
        by_domain[str(tool.get("domain name", ""))].append(tool)
    selected: list[dict[str, Any]] = []
    for domain in sorted(by_domain):
        selected.extend(by_domain[domain][:per_domain])
    return selected


def prompt_for(tool: dict[str, Any]) -> str:
    payload = source_payload(tool)
    return (
        "Normalize this single tool record into a grounded Scheduling-Structural-Logical representation. "
        "Return only the required JSON schema. Every identifier must be copied exactly from DATA. "
        "Every evidence item must be an exact contiguous substring of DATA, including punctuation where possible. "
        "Do not invent scenes, transitions, effects, resources, aliases, or permissions. "
        "If the source does not support a claim, use an empty array for that section, but keep the required top-level evidence array with a source quote. "
        "Use READ/CALL/WRITE/REPORT/CHECK/SCENE/ACT/END conservatively; a tool invocation is usually CALL, and do not infer writes from prose alone. "
        "SCHEMA:\n" + json.dumps(OUTPUT_SCHEMA, sort_keys=True, separators=(",", ":")) + "\nDATA:\n" + json.dumps(payload, ensure_ascii=False, sort_keys=True)
    )


def call_frontier(prompt: str, raw_path: Path, timeout_seconds: int) -> tuple[dict[str, Any], float]:
    with tempfile.TemporaryDirectory(prefix="frankengate-ssl-normalizer-") as directory:
        root = Path(directory)
        schema = root / "schema.json"
        output = root / "output.json"
        schema.write_text(json.dumps(OUTPUT_SCHEMA), encoding="utf-8")
        command = [
            "codex", "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
            "--skip-git-repo-check", "-s", "read-only", "-m", MODEL,
            "--output-schema", str(schema), "--output-last-message", str(output),
        ]
        started = time.perf_counter()
        completed = subprocess.run(command, input=prompt, text=True, capture_output=True, timeout=timeout_seconds, cwd="/private/tmp", check=False)
        elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)
        raw_path.write_text(json.dumps({"returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}, ensure_ascii=False), encoding="utf-8")
        if completed.returncode != 0 or not output.exists():
            raise RuntimeError(f"frontier call failed: {completed.stderr[-1000:]}")
        value = json.loads(output.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("normalizer response is not an object")
    return value, elapsed_ms


def evidence_items(value: dict[str, Any]) -> list[str]:
    items: list[str] = []
    scheduling = value.get("scheduling", {})
    structural = value.get("structural", {})
    logical = value.get("logical", {})
    for field in (scheduling, structural, logical):
        if isinstance(field, dict):
            items.extend(item for item in field.get("evidence", []) if isinstance(item, str))
    for scene in structural.get("scenes", []) if isinstance(structural, dict) else []:
        if isinstance(scene, dict):
            items.extend(item for item in scene.get("evidence", []) if isinstance(item, str))
    for transition in structural.get("transitions", []) if isinstance(structural, dict) else []:
        if isinstance(transition, dict):
            items.extend(item for item in transition.get("evidence", []) if isinstance(item, str))
    for action in logical.get("actions", []) if isinstance(logical, dict) else []:
        if isinstance(action, dict):
            items.extend(item for item in action.get("evidence", []) if isinstance(item, str))
    return items


def grounding_metrics(tool: dict[str, Any], value: dict[str, Any]) -> dict[str, Any]:
    source = source_text(tool).casefold()
    identifiers = {
        "source_tool_name_exact": value.get("source_tool_name") == str(tool.get("tool name", "")),
        "source_api_name_exact": value.get("source_api_name") == str(tool.get("API name", "")),
        "source_domain_name_exact": value.get("source_domain_name") == str(tool.get("domain name", "")),
    }
    expected_params = {str(item.get("name", "")) for field in ("required_parameters", "optional_parameters") for item in tool.get(field, []) if isinstance(item, dict)}
    actual_params = {str(item) for item in value.get("source_parameter_names", [])}
    identifiers["source_parameters_subset"] = actual_params <= expected_params
    evidence = evidence_items(value)
    grounded = [item for item in evidence if item.casefold() in source]
    return {
        **identifiers,
        "identifier_fidelity": all(identifiers.values()),
        "evidence_count": len(evidence),
        "grounded_evidence_count": len(grounded),
        "all_evidence_grounded": bool(evidence) and len(grounded) == len(evidence),
        "scene_count": len(value.get("structural", {}).get("scenes", [])),
        "action_count": len(value.get("logical", {}).get("actions", [])),
    }


def run(root: Path, raw_dir: Path, output: Path, per_domain: int, timeout_seconds: int) -> dict[str, Any]:
    selected = select_tools(root, per_domain)
    raw_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for index, tool in enumerate(selected):
        prompt = prompt_for(tool)
        prompt_path = raw_dir / f"tool-{index:03d}-prompt.json"
        raw_path = raw_dir / f"tool-{index:03d}-raw.json"
        prompt_path.write_text(json.dumps({"prompt": prompt}, ensure_ascii=False), encoding="utf-8")
        base = {"index": index, "domain": str(tool.get("domain name", "")), "source_sha256": stable_hash(source_payload(tool)), "prompt_sha256": file_hash(prompt_path)}
        try:
            value, elapsed_ms = call_frontier(prompt, raw_path, timeout_seconds)
            metrics = grounding_metrics(tool, value)
            records.append({**base, "status": "ok", "elapsed_ms": elapsed_ms, "response_sha256": stable_hash(value), **metrics})
        except Exception as exc:
            records.append({**base, "status": "error", "error_type": type(exc).__name__, "raw_sha256": file_hash(raw_path) if raw_path.exists() else None})
    ok = [record for record in records if record["status"] == "ok"]
    result = {
        "schema_version": SCHEMA_VERSION,
        "dataset": {"root_name": root.name, "tool_count": len(selected), "per_domain": per_domain, "source_sha256": file_hash(root / "tools" / "all_tools.json"), "raw_content_committed": False},
        "protocol": {"model": MODEL, "normalization_schema": "SSL-shaped with exact evidence quotes", "raw_prompts_responses_external": True, "enterprise_quality_measured": False, "retrieval_measured": False, "agent_utility_measured": False},
        "aggregate": {
            "selected": len(selected),
            "completed": len(ok),
            "failures": len(records) - len(ok),
            "identifier_fidelity_rate": round(sum(bool(record.get("identifier_fidelity")) for record in ok) / len(ok), 6) if ok else 0.0,
            "all_evidence_grounded_rate": round(sum(bool(record.get("all_evidence_grounded")) for record in ok) / len(ok), 6) if ok else 0.0,
            "evidence_grounding_rate": round(sum(record.get("grounded_evidence_count", 0) for record in ok) / max(1, sum(record.get("evidence_count", 0) for record in ok)), 6),
            "mean_scene_count": round(sum(record.get("scene_count", 0) for record in ok) / len(ok), 6) if ok else 0.0,
            "mean_action_count": round(sum(record.get("action_count", 0) for record in ok) / len(ok), 6) if ok else 0.0,
            "mean_elapsed_ms": round(sum(record.get("elapsed_ms", 0.0) for record in ok) / len(ok), 3) if ok else 0.0,
        },
        "records": records,
        "claim_boundary": {"grounding_probe_measured": True, "retrieval_lift_measured": False, "semantic_alias_quality_measured": False, "risk_quality_measured": False, "skill_or_artifact_utility_measured": False, "reason": "Small public tool sample; exact evidence-substring checks are a mechanical grounding proxy, not human adjudication or enterprise outcomes."},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result["aggregate"], sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--per-domain", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=int, default=240)
    args = parser.parse_args()
    run(args.root, args.raw_dir, args.output, args.per_domain, args.timeout_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
