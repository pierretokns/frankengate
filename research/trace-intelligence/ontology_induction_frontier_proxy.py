#!/usr/bin/env python3
"""Compare schema-free and starter-schema ontology extraction on public traces.

This is a frontier-model *mechanics* proxy.  Source text and model responses
are written only to an external raw directory; the committed receipt contains
hashes and structural/evidence-grounding metrics.  No metric here establishes
ontology correctness, alias truth, authority, or replay utility.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-ontology-induction-frontier-proxy-v1"
MODEL = "gpt-5.6-luna"
STARTER_TYPES = ["system", "repository", "tool", "file", "metric", "task", "person", "service"]
STARTER_RELATIONS = ["owns", "uses", "depends_on", "produces", "located_in", "measures", "part_of", "replaces"]


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_documents(root: Path, limit: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*.jsonl")):
        if path.name == "history.jsonl":
            continue
        texts: list[str] = []
        try:
            for line in path.read_bytes().splitlines():
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                message = item.get("message") if isinstance(item, dict) else None
                if isinstance(message, dict):
                    content = message.get("content")
                    if isinstance(content, str):
                        texts.append(content)
                    elif isinstance(content, list):
                        texts.extend(str(block.get("text", "")) for block in content if isinstance(block, dict) and block.get("type") == "text")
                elif isinstance(item, dict) and isinstance(item.get("content"), str):
                    texts.append(item["content"])
        except OSError:
            continue
        text = "\n".join(part for part in texts if part).strip()
        if text:
            rows.append({"path_hash": hashlib.sha256(str(path.relative_to(root)).encode()).hexdigest(), "text": text[:9000]})
        if len(rows) >= limit:
            break
    return rows


def schema_for(arm: str) -> dict[str, Any]:
    entity_types = STARTER_TYPES if arm == "ontogpt_population" else ["entity", "system", "repository", "tool", "file", "metric", "task", "person", "service", "concept", "unknown"]
    relation_types = STARTER_RELATIONS if arm == "ontogpt_population" else ["owns", "uses", "depends_on", "produces", "located_in", "measures", "part_of", "replaces", "related_to", "unknown"]
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["entities", "relations", "constraints"],
        "properties": {
            "entities": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["mention", "type", "canonical_id", "evidence"], "properties": {"mention": {"type": "string"}, "type": {"type": "string", "enum": entity_types}, "canonical_id": {"type": "string"}, "evidence": {"type": "array", "minItems": 1, "items": {"type": "string"}}}}},
            "relations": {"type": "array", "items": {"type": "object", "additionalProperties": False, "required": ["subject", "relation", "object", "evidence"], "properties": {"subject": {"type": "string"}, "relation": {"type": "string", "enum": relation_types}, "object": {"type": "string"}, "evidence": {"type": "array", "minItems": 1, "items": {"type": "string"}}}}},
            "constraints": {"type": "array", "items": {"type": "string"}},
        },
    }


def prompt_for(text: str, arm: str) -> str:
    if arm == "ontogpt_population":
        instruction = (
            "Populate only this starter schema. Do not invent a new class or relation type. "
            f"Allowed entity types: {STARTER_TYPES}. Allowed relation types: {STARTER_RELATIONS}. "
            "Use unknown or omit an item when the text does not support it."
        )
    else:
        instruction = (
            "Propose a small typed ontology from this trace excerpt. Keep uncertain concepts as unknown; "
            "do not infer ownership, authority, temporal validity, or equivalence without evidence."
        )
    return (
        "Return exactly one JSON object matching SCHEMA. Every evidence string must be an exact contiguous substring of DATA. "
        "Canonical IDs must be local stable labels, not claims of enterprise identity. " + instruction + "\n"
        "SCHEMA=" + json.dumps(schema_for(arm), sort_keys=True, separators=(",", ":")) + "\nDATA=" + text
    )


def call_frontier(prompt: str, raw_path: Path, arm: str, timeout: int) -> tuple[dict[str, Any], float]:
    with tempfile.TemporaryDirectory(prefix="frankengate-ontology-frontier-") as directory:
        root = Path(directory)
        schema_path = root / "schema.json"
        output_path = root / "output.json"
        schema_path.write_text(json.dumps(schema_for(arm)), encoding="utf-8")
        command = ["codex", "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules", "--skip-git-repo-check", "-s", "read-only", "-m", MODEL, "--output-schema", str(schema_path), "--output-last-message", str(output_path)]
        started = time.perf_counter()
        completed = subprocess.run(command, input=prompt, text=True, capture_output=True, timeout=timeout, cwd="/private/tmp", check=False)
        elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)
        raw_payload = {"returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}
        raw_path.write_text(json.dumps(raw_payload, ensure_ascii=False), encoding="utf-8")
        if completed.returncode != 0 or not output_path.exists():
            raise RuntimeError("frontier call failed")
        value = json.loads(output_path.read_text(encoding="utf-8"))
        # Structured responses remain in the caller-selected external scratch
        # directory for repeatability/consistency analysis; receipts never
        # include raw entities, relations, evidence, or source text.
        raw_payload["structured_output"] = value
        raw_path.write_text(json.dumps(raw_payload, ensure_ascii=False), encoding="utf-8")
    return value, elapsed_ms


def grounded(value: dict[str, Any], source: str) -> tuple[int, int]:
    evidence: list[str] = []
    for entity in value.get("entities", []):
        evidence.extend(str(item) for item in entity.get("evidence", []))
    for relation in value.get("relations", []):
        evidence.extend(str(item) for item in relation.get("evidence", []))
    return sum(item in source for item in evidence), len(evidence)


def run(root: Path, raw_dir: Path, output: Path, limit: int, timeout: int) -> dict[str, Any]:
    docs = load_documents(root, limit)
    raw_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for index, document in enumerate(docs):
        for arm in ("goi_proposal", "ontogpt_population"):
            prompt = prompt_for(document["text"], arm)
            raw_path = raw_dir / f"case-{index:03d}-{arm}.json"
            base = {"case": index, "arm": arm, "source_sha256": digest(document["text"]), "prompt_sha256": digest(prompt)}
            try:
                value, elapsed_ms = call_frontier(prompt, raw_path, arm, timeout)
                grounded_count, evidence_count = grounded(value, document["text"])
                records.append({**base, "status": "ok", "response_sha256": digest(value), "entity_count": len(value.get("entities", [])), "relation_count": len(value.get("relations", [])), "constraint_count": len(value.get("constraints", [])), "evidence_count": evidence_count, "grounded_evidence_count": grounded_count, "evidence_grounding_rate": round(grounded_count / evidence_count, 6) if evidence_count else 0.0, "elapsed_ms": elapsed_ms})
            except Exception as exc:
                records.append({**base, "status": "error", "error_type": type(exc).__name__, "raw_sha256": file_hash(raw_path) if raw_path.exists() else None})
    by_arm: dict[str, list[dict[str, Any]]] = {"goi_proposal": [], "ontogpt_population": []}
    for record in records:
        if record["status"] == "ok":
            by_arm[record["arm"]].append(record)
    arms: dict[str, Any] = {}
    for arm, rows in by_arm.items():
        arms[arm] = {"completed": len(rows), "failures": sum(record["arm"] == arm and record["status"] == "error" for record in records), "mean_entities": round(sum(record["entity_count"] for record in rows) / len(rows), 3) if rows else 0.0, "mean_relations": round(sum(record["relation_count"] for record in rows) / len(rows), 3) if rows else 0.0, "mean_evidence_grounding_rate": round(sum(record["evidence_grounding_rate"] for record in rows) / len(rows), 6) if rows else 0.0, "mean_elapsed_ms": round(sum(record["elapsed_ms"] for record in rows) / len(rows), 3) if rows else 0.0}
    result: dict[str, Any] = {"schema_version": SCHEMA_VERSION, "dataset": {"root_uri": "external://fable-5-traces", "documents": len(docs), "source_hashes_only": True, "raw_content_committed": False}, "protocol": {"model": MODEL, "arms": ["goi_proposal", "ontogpt_population"], "starter_schema_types": STARTER_TYPES, "starter_schema_relations": STARTER_RELATIONS, "raw_prompts_responses_external": True}, "arms": arms, "records": [{key: value for key, value in record.items() if key not in {"error_type", "error_message"}} for record in records], "claim_boundary": {"structured_extraction_measured": True, "ontology_correctness_established": False, "alias_quality_established": False, "authority_or_temporal_validity_established": False, "replay_utility_established": False, "reason": "Public trace excerpts and model-proposed structures have no independent ontology labels, principal/authority labels, temporal ground truth, or changed-system outcomes."}}
    result["result_sha256"] = digest(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"dataset": result["dataset"], "arms": arms}, sort_keys=True))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args()
    run(args.root, args.raw_dir, args.output, args.limit, args.timeout)
