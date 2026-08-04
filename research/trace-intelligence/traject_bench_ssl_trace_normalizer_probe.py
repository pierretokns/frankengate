#!/usr/bin/env python3
"""Probe grounded SSL-style normalization on multi-tool trajectories."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import time
from collections import defaultdict
from pathlib import Path
from typing import Any


MODEL = "gpt-5.6-luna"
SCHEMA_VERSION = "frankengate-traject-bench-ssl-trace-normalizer-probe-v1"
ACT_TYPES = ["READ", "CALL", "WRITE", "REPORT", "CHECK", "SCENE", "ACT", "END"]
OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["trajectory_type", "source_tool_names", "structural", "logical"],
    "properties": {
        "trajectory_type": {"type": "string"},
        "source_tool_names": {"type": "array", "items": {"type": "string"}},
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
                        "required": ["name", "action_orders", "evidence"],
                        "properties": {"name": {"type": "string"}, "action_orders": {"type": "array", "items": {"type": "integer", "minimum": 0}}, "evidence": {"type": "array", "minItems": 1, "items": {"type": "string"}}},
                    },
                },
                "transitions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["from_scene", "to_scene", "relation", "evidence"],
                        "properties": {"from_scene": {"type": "string"}, "to_scene": {"type": "string"}, "relation": {"type": "string"}, "evidence": {"type": "array", "minItems": 1, "items": {"type": "string"}}},
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
                        "required": ["order", "act_type", "resource", "effect", "evidence"],
                        "properties": {"order": {"type": "integer", "minimum": 0}, "act_type": {"type": "string", "enum": ACT_TYPES}, "resource": {"type": "string"}, "effect": {"type": "string"}, "evidence": {"type": "array", "minItems": 1, "items": {"type": "string"}}},
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


def tool_list(row: dict[str, Any]) -> list[dict[str, Any]]:
    value = row.get("tool list", row.get("tool_list", []))
    return value if isinstance(value, list) else []


def source_payload(row: dict[str, Any]) -> dict[str, Any]:
    tools = []
    for item in tool_list(row):
        tools.append({
            "tool_name": str(item.get("tool name", "")),
            "tool_description": str(item.get("tool description", "")),
            "required_parameters": item.get("required parameters", []),
            "optional_parameters": item.get("optional parameters", []),
            "executed_output": str(item.get("executed_output", ""))[:1200],
        })
    return {
        "query": str(row.get("query", "")),
        "trajectory_type": str(row.get("trajectory_type", "")),
        "tool_count": int(row.get("tool count", len(tools)) or len(tools)),
        "tools": tools,
        "final_answer": str(row.get("final_answer", ""))[:1200],
    }


def select_rows(root: Path) -> list[tuple[str, str, dict[str, Any]]]:
    selected: list[tuple[str, str, dict[str, Any]]] = []
    for kind in ("parallel", "sequential"):
        by_domain: dict[str, list[Path]] = defaultdict(list)
        pattern = "hard_ver.json" if kind == "parallel" else "traj_query.json"
        for path in sorted(root.glob(f"{kind}/*/{pattern}")):
            by_domain[path.parent.name].append(path)
        for domain in sorted(by_domain):
            chosen: dict[str, Any] | None = None
            path_used: Path | None = None
            for path in by_domain[domain]:
                for row in json.loads(path.read_text(encoding="utf-8")):
                    if len(tool_list(row)) >= 2:
                        chosen = dict(row)
                        if not chosen.get("trajectory_type"):
                            chosen["trajectory_type"] = kind
                        path_used = path
                        break
                if chosen is not None:
                    break
            if chosen is not None and path_used is not None:
                selected.append((kind, domain, chosen))
    return selected


def prompt_for(row: dict[str, Any]) -> str:
    payload = source_payload(row)
    return (
        "Normalize this complete multi-tool trajectory into a grounded Scheduling-Structural-Logical representation. "
        "Return only the JSON schema. Copy every tool name in TOOLS exactly and preserve its original order in source_tool_names. "
        "Emit exactly one logical action for every tool, with order 0..N-1 and resource equal to the exact tool name. "
        "Use scenes to group actions only when the query, trajectory_type, tool descriptions, or outputs support the grouping; do not invent hidden steps. "
        "Every evidence item must be an exact contiguous substring of DATA. Use an empty transitions array when no transition is explicitly supported. "
        "The trajectory_type is metadata, not proof of semantic parallelism; do not infer permissions, success, or writes unless the source states them. "
        "Use CALL for ordinary tool invocation and READ/WRITE/CHECK/REPORT only when the source supports that effect. "
        "SCHEMA:\n" + json.dumps(OUTPUT_SCHEMA, sort_keys=True, separators=(",", ":")) + "\nDATA:\n" + json.dumps(payload, ensure_ascii=False, sort_keys=True)
    )


def call_frontier(prompt: str, raw_path: Path, timeout_seconds: int) -> tuple[dict[str, Any], float]:
    with tempfile.TemporaryDirectory(prefix="frankengate-ssl-trace-normalizer-") as directory:
        root = Path(directory)
        schema = root / "schema.json"
        output = root / "output.json"
        schema.write_text(json.dumps(OUTPUT_SCHEMA), encoding="utf-8")
        command = ["codex", "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules", "--skip-git-repo-check", "-s", "read-only", "-m", MODEL, "--output-schema", str(schema), "--output-last-message", str(output)]
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


def grounding_metrics(row: dict[str, Any], value: dict[str, Any]) -> dict[str, Any]:
    payload = source_payload(row)
    source = json.dumps(payload, ensure_ascii=False, sort_keys=True).casefold()
    names = [str(item.get("tool_name", "")) for item in payload["tools"]]
    actual_names = [str(item) for item in value.get("source_tool_names", [])]
    logical_actions = value.get("logical", {}).get("actions", [])
    orders = [int(action.get("order", -1)) for action in logical_actions if isinstance(action, dict)]
    resources = [str(action.get("resource", "")) for action in logical_actions if isinstance(action, dict)]
    evidence = evidence_items(value)
    grounded = [item for item in evidence if item.casefold() in source]
    return {
        "trajectory_type_exact": value.get("trajectory_type") == str(row.get("trajectory_type", "")),
        "tool_names_exact_order": actual_names == names,
        "logical_action_count_exact": len(logical_actions) == len(names),
        "logical_orders_exact": orders == list(range(len(names))),
        "logical_resources_exact_order": resources == names,
        "identifier_fidelity": actual_names == names and resources == names,
        "evidence_count": len(evidence),
        "grounded_evidence_count": len(grounded),
        "all_evidence_grounded": bool(evidence) and len(grounded) == len(evidence),
        "scene_count": len(value.get("structural", {}).get("scenes", [])),
        "transition_count": len(value.get("structural", {}).get("transitions", [])),
        "action_count": len(logical_actions),
    }


def run(root: Path, raw_dir: Path, output: Path, timeout_seconds: int) -> dict[str, Any]:
    selected = select_rows(root)
    raw_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for index, (kind, domain, row) in enumerate(selected):
        prompt = prompt_for(row)
        prompt_path = raw_dir / f"trajectory-{index:03d}-prompt.json"
        raw_path = raw_dir / f"trajectory-{index:03d}-raw.json"
        prompt_path.write_text(json.dumps({"prompt": prompt}, ensure_ascii=False), encoding="utf-8")
        base = {"index": index, "kind": kind, "domain": domain, "tool_count": len(tool_list(row)), "source_sha256": stable_hash(source_payload(row)), "prompt_sha256": file_hash(prompt_path)}
        try:
            value, elapsed_ms = call_frontier(prompt, raw_path, timeout_seconds)
            records.append({**base, "status": "ok", "elapsed_ms": elapsed_ms, "response_sha256": stable_hash(value), **grounding_metrics(row, value)})
        except Exception as exc:
            records.append({**base, "status": "error", "error_type": type(exc).__name__, "raw_sha256": file_hash(raw_path) if raw_path.exists() else None})
    ok = [record for record in records if record["status"] == "ok"]
    def rate(field: str) -> float:
        return round(sum(bool(record.get(field)) for record in ok) / len(ok), 6) if ok else 0.0
    result = {
        "schema_version": SCHEMA_VERSION,
        "dataset": {"root_name": root.name, "selected": len(selected), "source_files_sha256": hashlib.sha256(json.dumps(sorted(str(path) + file_hash(path) for path in root.glob("parallel/*/hard_ver.json")) + sorted(str(path) + file_hash(path) for path in root.glob("sequential/*/hard_ver.json"))).encode()).hexdigest(), "raw_content_committed": False},
        "protocol": {"model": MODEL, "sample": "one multi-tool hard trajectory per domain for parallel and sequential", "normalization_schema": "SSL-shaped with exact tool order and evidence quotes", "raw_prompts_responses_external": True, "retrieval_measured": False, "enterprise_quality_measured": False, "agent_utility_measured": False},
        "aggregate": {
            "selected": len(selected), "completed": len(ok), "failures": len(records) - len(ok),
            "trajectory_type_exact_rate": rate("trajectory_type_exact"), "tool_names_exact_order_rate": rate("tool_names_exact_order"), "logical_action_count_exact_rate": rate("logical_action_count_exact"), "logical_orders_exact_rate": rate("logical_orders_exact"), "logical_resources_exact_order_rate": rate("logical_resources_exact_order"), "identifier_fidelity_rate": rate("identifier_fidelity"), "all_evidence_grounded_rate": rate("all_evidence_grounded"), "evidence_grounding_rate": round(sum(record.get("grounded_evidence_count", 0) for record in ok) / max(1, sum(record.get("evidence_count", 0) for record in ok)), 6), "mean_scene_count": round(sum(record.get("scene_count", 0) for record in ok) / len(ok), 6) if ok else 0.0, "mean_transition_count": round(sum(record.get("transition_count", 0) for record in ok) / len(ok), 6) if ok else 0.0, "mean_action_count": round(sum(record.get("action_count", 0) for record in ok) / len(ok), 6) if ok else 0.0, "mean_elapsed_ms": round(sum(record.get("elapsed_ms", 0.0) for record in ok) / len(ok), 3) if ok else 0.0,
        },
        "records": records,
        "claim_boundary": {"grounded_multi_tool_normalization_measured": True, "retrieval_lift_measured": False, "semantic_alias_quality_measured": False, "skill_or_artifact_utility_measured": False, "reason": "Small public multi-tool sample; exact-order and evidence-substring checks are mechanical proxies, not human semantic labels or enterprise outcomes."},
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
    parser.add_argument("--timeout-seconds", type=int, default=240)
    args = parser.parse_args()
    run(args.root, args.raw_dir, args.output, args.timeout_seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
