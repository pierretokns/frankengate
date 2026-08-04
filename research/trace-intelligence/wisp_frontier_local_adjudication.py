#!/usr/bin/env python3
"""Compare frontier and local-model trace insight adjudication on one Wisp packet.

This is a model-agreement and structured-output study, not a correctness
benchmark. Both models see the same compact, blinded candidate-local evidence
and use the pinned Wisp label contract. The local labels are the first
``rubric_first`` pass from the existing stability receipt; no model is treated
as ground truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-wisp-frontier-local-adjudication-v1"
FIELDS = ("cause", "evidence_strength", "outcome", "productive_exploration", "relation", "usefulness")
OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["decisions"],
    "properties": {
        "decisions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["blind_id", "labels", "evidence_refs"],
                "properties": {
                    "blind_id": {"type": "string"},
                    "labels": {
                        "type": "object",
                        "additionalProperties": False,
                        "properties": {
                            "cause": {"type": "string"},
                            "evidence_strength": {"type": "string"},
                            "outcome": {"type": "string"},
                            "productive_exploration": {"type": "string"},
                            "relation": {"type": "string"},
                            "usefulness": {"type": "string"},
                        },
                        "required": ["cause", "evidence_strength", "outcome", "productive_exploration", "relation", "usefulness"],
                    },
                    "evidence_refs": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
                },
            },
        }
    },
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def stable_hash(value: Any) -> str:
    return sha256_bytes(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode())


def _compact_payload(payload: Any, limit: int = 1800) -> str:
    text = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)
    return text[:limit]


def compact_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "blind_id": candidate["blind_id"],
        "controlled_tool_family": candidate["controlled_tool_family"],
        "context": [
            {"kind": event.get("kind"), "evidence_ref": event.get("evidence_ref"), "payload": _compact_payload(event.get("payload"))}
            for event in candidate.get("context", [])
        ],
    }


def _load_common(packet_path: Path, local_raw_path: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, str]], dict[str, list[str]]]:
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    local_rows = [json.loads(line) for line in local_raw_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    local_by_id: dict[str, dict[str, str]] = {}
    for row in local_rows:
        if row.get("pass_id") != "rubric_first" or row.get("status") != "valid":
            continue
        local_by_id.setdefault(row["blind_id"], {field: row["labels"][field]["label"] for field in FIELDS})
    candidates_by_id = {candidate["blind_id"]: candidate for candidate in packet["candidates"]}
    selected_ids = list(local_by_id)[:6]
    if len(selected_ids) < 6 or any(identifier not in candidates_by_id for identifier in selected_ids):
        raise ValueError("pinned local receipt does not cover six packet candidates")
    selected = [candidates_by_id[identifier] for identifier in selected_ids]
    contract = packet["label_contract"]
    return selected, local_by_id, contract


def _prompt(candidates: list[dict[str, Any]], contract: dict[str, list[str]]) -> str:
    visible = [compact_candidate(candidate) for candidate in candidates]
    return (
        "You are a blinded trace-review adjudicator. Apply the supplied label "
        "contract only to the candidate-local evidence. Do not infer hidden user "
        "intent, do not cite outside sources, and do not invent evidence refs. "
        "Return one decision for every blind_id. Each labels object must contain "
        "all six fields and each evidence_refs list must contain only refs present "
        "in that candidate. If the evidence is insufficient, choose the contract's "
        "insufficient_evidence label.\n\nCONTRACT:\n"
        + json.dumps(contract, sort_keys=True, separators=(",", ":"))
        + "\nSCHEMA:\n"
        + json.dumps(OUTPUT_SCHEMA, sort_keys=True, separators=(",", ":"))
        + "\nCANDIDATES:\n"
        + json.dumps(visible, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    )


def _call(prompt: str, model: str, raw_path: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="frankengate-wisp-frontier-local-") as directory:
        root = Path(directory)
        schema_path = root / "schema.json"
        output_path = root / "output.json"
        schema_path.write_text(json.dumps(OUTPUT_SCHEMA), encoding="utf-8")
        command = [
            "codex", "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
            "--skip-git-repo-check", "-s", "read-only", "-m", model,
            "--output-schema", str(schema_path), "--output-last-message", str(output_path),
        ]
        completed = subprocess.run(command, input=prompt, text=True, capture_output=True, timeout=600, cwd="/private/tmp", check=False)
        raw = {"returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}
        if completed.returncode != 0 or not output_path.exists():
            raw_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
            raise RuntimeError(f"frontier call failed: {completed.stderr[-1000:]}")
        structured = json.loads(output_path.read_text(encoding="utf-8"))
        raw["structured_output"] = structured
        raw_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return structured


def _validate_frontier(value: dict[str, Any], candidates: list[dict[str, Any]], contract: dict[str, list[str]]) -> dict[str, dict[str, Any]]:
    decisions = value.get("decisions")
    expected = {candidate["blind_id"] for candidate in candidates}
    if not isinstance(decisions, list) or {item.get("blind_id") for item in decisions} != expected or len(decisions) != len(expected):
        raise ValueError("frontier did not cover every candidate exactly once")
    by_id: dict[str, dict[str, Any]] = {}
    candidates_by_id = {candidate["blind_id"]: candidate for candidate in candidates}
    for item in decisions:
        blind_id = item["blind_id"]
        candidate = candidates_by_id[blind_id]
        labels = item.get("labels")
        if not isinstance(labels, dict) or set(labels) != set(FIELDS):
            raise ValueError(f"label field mismatch: {blind_id}")
        valid_refs = {event.get("evidence_ref") for event in candidate.get("context", [])}
        refs = item.get("evidence_refs", [])
        if not set(refs) <= valid_refs:
            raise ValueError(f"evidence reference escaped candidate: {blind_id}")
        for field in FIELDS:
            if labels[field] not in contract[field]:
                raise ValueError(f"invalid label: {blind_id}/{field}")
        by_id[blind_id] = {"labels": labels, "evidence_refs": refs}
    return by_id


def run(packet: Path, local_raw: Path, output: Path, raw_dir: Path, *, model: str) -> dict[str, Any]:
    candidates, local_labels, contract = _load_common(packet, local_raw)
    prompt = _prompt(candidates, contract)
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / "frontier.json"
    frontier = _call(prompt, model, raw_path)
    frontier_labels = _validate_frontier(frontier, candidates, contract)
    field_agreement: dict[str, float] = {}
    for field in FIELDS:
        field_agreement[field] = round(sum(frontier_labels[identifier]["labels"][field] == local_labels[identifier][field] for identifier in local_labels) / len(local_labels), 6)
    all_field = round(sum(all(frontier_labels[identifier]["labels"][field] == local_labels[identifier][field] for field in FIELDS) for identifier in local_labels) / len(local_labels), 6)
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "source": {"packet_sha256": sha256_bytes(packet.read_bytes()), "local_raw_sha256": sha256_bytes(local_raw.read_bytes()), "candidate_count": len(candidates), "raw_content_committed": False},
        "protocol": {"model": model, "local_label_pass": "rubric_first", "same_label_contract": True, "frontier_sees_local_labels": False, "raw_model_output_external": True},
        "candidates": [{"blind_id": candidate["blind_id"], "candidate_context_sha256": stable_hash(compact_candidate(candidate))} for candidate in candidates],
        "agreement": {"field": field_agreement, "all_fields_per_candidate": all_field},
        "frontier_output": {"valid": True, "evidence_refs_candidate_local": True, "raw_sha256": sha256_bytes(raw_path.read_bytes()), "prompt_sha256": stable_hash(prompt)},
        "claim_boundary": "Frontier-vs-local model agreement and structured-output study on six public Wisp recovery candidates. Neither model is ground truth; it does not establish insight correctness, human agreement, causal diagnosis, or enterprise utility.",
    }
    receipt["result_sha256"] = stable_hash(receipt)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "agreement": receipt["agreement"], "result_sha256": receipt["result_sha256"]}, sort_keys=True))
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--local-raw", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--model", default="gpt-5.6-luna")
    args = parser.parse_args()
    run(args.packet, args.local_raw, args.output, args.raw_dir, model=args.model)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
