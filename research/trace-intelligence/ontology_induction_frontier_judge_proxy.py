#!/usr/bin/env python3
"""Silver-label evidence judge for the ontology frontier proxy.

The judge is a separate frontier pass over the source excerpt and the proposed
graph.  Its labels are not ground truth; the receipt exists to quantify
unsupported-edge risk before any human/adjudicated ontology study.
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


SCHEMA_VERSION = "frankengate-ontology-induction-frontier-judge-proxy-v1"
MODEL = "gpt-5.6-luna"
DECISIONS = ["supported", "unsupported", "unclear"]


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def load_documents(root: Path, limit: int) -> list[str]:
    texts: list[str] = []
    for path in sorted(root.rglob("*.jsonl")):
        if path.name == "history.jsonl":
            continue
        parts: list[str] = []
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
                        parts.append(content)
                    elif isinstance(content, list):
                        parts.extend(str(block.get("text", "")) for block in content if isinstance(block, dict) and block.get("type") == "text")
                elif isinstance(item, dict) and isinstance(item.get("content"), str):
                    parts.append(item["content"])
        except OSError:
            continue
        text = "\n".join(item for item in parts if item).strip()
        if text:
            texts.append(text[:9000])
        if len(texts) >= limit:
            break
    return texts


def schema() -> dict[str, Any]:
    item = {"type": "object", "additionalProperties": False, "required": ["item", "decision", "evidence"], "properties": {"item": {"type": "string"}, "decision": {"type": "string", "enum": DECISIONS}, "evidence": {"type": "array", "minItems": 1, "items": {"type": "string"}}}}
    return {"type": "object", "additionalProperties": False, "required": ["entities", "relations"], "properties": {"entities": {"type": "array", "items": item}, "relations": {"type": "array", "items": item}}}


def prompt_for(source: str, proposal: dict[str, Any]) -> str:
    return (
        "Judge whether each proposed entity and relation is supported by DATA. "
        "Use supported only when the text directly supports the item; use unsupported when it contradicts or is invented; use unclear when evidence is insufficient. "
        "Return exactly one JSON object matching SCHEMA. Every evidence item must be an exact contiguous substring of DATA. "
        "Do not use general world knowledge.\nSCHEMA=" + json.dumps(schema(), sort_keys=True, separators=(",", ":")) +
        "\nDATA=" + source + "\nPROPOSAL=" + json.dumps(proposal, ensure_ascii=False, sort_keys=True)
    )


def call(prompt: str, raw_path: Path, timeout: int) -> tuple[dict[str, Any], float]:
    with tempfile.TemporaryDirectory(prefix="frankengate-ontology-judge-") as directory:
        root = Path(directory)
        schema_path = root / "schema.json"
        output_path = root / "output.json"
        schema_path.write_text(json.dumps(schema()), encoding="utf-8")
        command = ["codex", "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules", "--skip-git-repo-check", "-s", "read-only", "-m", MODEL, "--output-schema", str(schema_path), "--output-last-message", str(output_path)]
        started = time.perf_counter()
        completed = subprocess.run(command, input=prompt, text=True, capture_output=True, timeout=timeout, cwd="/private/tmp", check=False)
        elapsed_ms = round((time.perf_counter() - started) * 1000.0, 3)
        raw: dict[str, Any] = {"returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}
        if completed.returncode != 0 or not output_path.exists():
            raw_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
            raise RuntimeError("judge call failed")
        value = json.loads(output_path.read_text(encoding="utf-8"))
        raw["structured_output"] = value
        raw_path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    return value, elapsed_ms


def summarize(value: dict[str, Any], source: str) -> dict[str, Any]:
    items = [item for field in ("entities", "relations") for item in value.get(field, []) if isinstance(item, dict)]
    counts = {decision: 0 for decision in DECISIONS}
    grounded = 0
    evidence_count = 0
    for item in items:
        decision = str(item.get("decision"))
        if decision in counts:
            counts[decision] += 1
        evidence = [str(text) for text in item.get("evidence", [])]
        evidence_count += len(evidence)
        grounded += sum(text in source for text in evidence)
    total = len(items)
    return {"items": total, **{f"{decision}_count": counts[decision] for decision in DECISIONS}, "supported_rate": round(counts["supported"] / total, 6) if total else 0.0, "unsupported_rate": round(counts["unsupported"] / total, 6) if total else 0.0, "unclear_rate": round(counts["unclear"] / total, 6) if total else 0.0, "judge_evidence_grounding_rate": round(grounded / evidence_count, 6) if evidence_count else 0.0}


def run(root: Path, proposal_raw: Path, raw_dir: Path, output: Path, limit: int, timeout: int) -> dict[str, Any]:
    sources = load_documents(root, limit)
    raw_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    for case, source in enumerate(sources):
        for arm in ("goi_proposal", "ontogpt_population"):
            candidate_path = proposal_raw / f"case-{case:03d}-{arm}.json"
            candidate = json.loads(candidate_path.read_text(encoding="utf-8")).get("structured_output")
            if not isinstance(candidate, dict):
                records.append({"case": case, "arm": arm, "status": "missing_proposal"})
                continue
            prompt = prompt_for(source, candidate)
            raw_path = raw_dir / f"case-{case:03d}-{arm}.json"
            base = {"case": case, "arm": arm, "source_sha256": digest(source), "proposal_sha256": digest(candidate), "prompt_sha256": digest(prompt)}
            try:
                value, elapsed_ms = call(prompt, raw_path, timeout)
                records.append({**base, "status": "ok", "response_sha256": digest(value), "elapsed_ms": elapsed_ms, **summarize(value, source)})
            except Exception as exc:
                records.append({**base, "status": "error", "error_type": type(exc).__name__})
    arms: dict[str, Any] = {}
    for arm in ("goi_proposal", "ontogpt_population"):
        rows = [record for record in records if record.get("arm") == arm and record.get("status") == "ok"]
        arms[arm] = {"completed": len(rows), "failures": sum(record.get("arm") == arm and record.get("status") != "ok" for record in records), "items": sum(record.get("items", 0) for record in rows), "supported_rate": round(sum(record.get("supported_rate", 0.0) * record.get("items", 0) for record in rows) / max(1, sum(record.get("items", 0) for record in rows)), 6), "unsupported_rate": round(sum(record.get("unsupported_rate", 0.0) * record.get("items", 0) for record in rows) / max(1, sum(record.get("items", 0) for record in rows)), 6), "unclear_rate": round(sum(record.get("unclear_rate", 0.0) * record.get("items", 0) for record in rows) / max(1, sum(record.get("items", 0) for record in rows)), 6), "mean_elapsed_ms": round(sum(record.get("elapsed_ms", 0.0) for record in rows) / len(rows), 3) if rows else 0.0}
    result: dict[str, Any] = {"schema_version": SCHEMA_VERSION, "dataset": {"root_uri": "external://fable-5-traces", "documents": len(sources), "raw_content_committed": False}, "protocol": {"judge_model": MODEL, "proposal_raw_external_only": True, "judge_labels_are_silver": True}, "arms": arms, "records": records, "claim_boundary": {"silver_support_judgment_measured": True, "ontology_correctness_established": False, "human_adjudication_established": False, "replay_utility_established": False, "reason": "The judge is a second frontier pass over public trace excerpts; it is not an independent human or outcome label."}}
    result["result_sha256"] = digest(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"dataset": result["dataset"], "arms": arms}, sort_keys=True))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--proposal-raw", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args()
    run(args.root, args.proposal_raw, args.raw_dir, args.output, args.limit, args.timeout)
