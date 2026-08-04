#!/usr/bin/env python3
"""Frontier-adjudicated pilot for cross-user task-equivalence candidates.

This is a silver-label probe: Luna labels pairs of session summaries, with two
independent calls per pair. It measures whether candidate generation produces
reviewable cross-user matches; it does not establish ground truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import subprocess
import tempfile
import time
from collections import Counter
from pathlib import Path


LABELS = {"same_task", "related_task", "different", "unclear"}
STOP = {"the", "and", "for", "with", "that", "this", "from", "have", "has", "are", "was", "were", "you", "your", "can", "not", "but", "what", "how", "please", "use", "using", "into", "then", "than", "only", "also", "its", "a", "an", "to", "of", "in", "on", "is", "be", "as", "or", "it", "do", "does", "i", "we"}

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["label", "confidence", "reason"],
    "properties": {
        "label": {"type": "string", "enum": sorted(LABELS)},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "reason": {"type": "string"},
    },
}


def clean_text(text: str) -> str:
    """Remove harness boilerplate that would create false semantic matches."""
    for tag in ("local-command-caveat", "system-reminder", "task-notification"):
        text = re.sub(rf"<{tag}>.*?</{tag}>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]{1,120}>", " ", text)
    lines = []
    for line in text.splitlines():
        lower = line.lower()
        if "read the output file to retrieve" in lower:
            continue
        if "request interrupted by user" in lower:
            continue
        if "task-id" in lower or "output-file" in lower or "<status>" in lower:
            continue
        lines.append(line)
    text = "\n".join(lines)
    text = re.sub(r"/private/tmp/[^\s]+", " ", text)
    text = re.sub(r"/user_[a-z0-9_-]+", " ", text, flags=re.I)
    text = re.sub(r"\b[0-9a-f]{8}-[0-9a-f-]{27,}\b", " ", text, flags=re.I)
    return " ".join(text.split())


def terms(text: str) -> set[str]:
    text = clean_text(text)
    return {w for w in re.findall(r"[a-z][a-z0-9_./:-]{2,}", text.lower()) if w not in STOP and not re.fullmatch(r"[0-9a-f]{8,}", w)}


def cosine(a: set[str], b: set[str]) -> float:
    return len(a & b) / math.sqrt(len(a) * len(b)) if a and b else 0.0


def load(path: Path, owner: str) -> list[dict]:
    rows = []
    for line in path.open(encoding="utf-8", errors="ignore"):
        try: session = json.loads(line)
        except json.JSONDecodeError: continue
        prompts = []
        tools = Counter()
        for message in session.get("messages", []):
            if not isinstance(message, dict): continue
            if message.get("role") == "user" and isinstance(message.get("content"), str) and len(prompts) < 3:
                prompts.append(clean_text(message["content"])[:1200])
            if message.get("role") == "assistant":
                for call in message.get("tool_uses", []):
                    if isinstance(call, dict): tools[str(call.get("tool", "<missing>"))] += 1
        text = "\n".join(prompts)
        if not text.strip(): continue
        rows.append({
            "owner": owner,
            "id": str(session.get("session_id", len(rows))),
            "summary": text,
            "terms": terms(text),
            "tools": set(tools),
        })
    return rows


def parse_output(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8").strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start: raise ValueError("no JSON in Luna output")
    value = json.loads(raw[start:end + 1])
    if value.get("label") not in LABELS: raise ValueError("invalid label")
    confidence = float(value.get("confidence"))
    if not 0 <= confidence <= 1: raise ValueError("invalid confidence")
    return {"label": value["label"], "confidence": confidence, "output_sha256": hashlib.sha256(raw.encode()).hexdigest()}


def ask(pair: tuple[dict, dict], model: str, timeout: int, seed: int) -> dict:
    left, right = pair
    prompt = (
        "You are adjudicating whether two anonymized coding-agent sessions concern the same underlying task. "
        "Use only the summaries and tool categories. Same_task means substantially the same concrete task; "
        "related_task means the same broader work but different concrete task; different means unrelated; "
        "unclear means insufficient evidence. Do not infer identity, employer, or user skill. Return JSON only.\n\n"
        + json.dumps(SCHEMA, sort_keys=True) + "\n\nSESSION A:\n" + left["summary"]
        + "\n\nTOOLS A:\n" + ", ".join(sorted(left["tools"]))
        + "\n\nSESSION B:\n" + right["summary"]
        + "\n\nTOOLS B:\n" + ", ".join(sorted(right["tools"]))
        + "\n\nPILOT SEED:\n" + str(seed)
    )
    with tempfile.TemporaryDirectory(prefix="frankengate-luna-adjudication-") as directory:
        root = Path(directory)
        schema = root / "schema.json"
        output = root / "output.json"
        schema.write_text(json.dumps(SCHEMA), encoding="utf-8")
        started = time.perf_counter()
        completed = subprocess.run([
            "codex", "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
            "--skip-git-repo-check", "-s", "read-only", "-m", model,
            "--output-schema", str(schema), "--output-last-message", str(output),
        ], input=prompt, text=True, capture_output=True, timeout=timeout, cwd="/private/tmp", check=False)
        elapsed_ms = (time.perf_counter() - started) * 1000
        if completed.returncode != 0 or not output.exists():
            return {"error": f"exit_{completed.returncode}", "elapsed_ms": elapsed_ms}
        try: parsed = parse_output(output)
        except Exception as exc: return {"error": type(exc).__name__, "elapsed_ms": elapsed_ms}
        parsed["elapsed_ms"] = elapsed_ms
        return parsed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", action="append", required=True, metavar="OWNER=PATH")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--pairs", type=int, default=8)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--seed", type=int, default=840001)
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    datasets = []
    for spec in args.dataset:
        owner, filename = spec.split("=", 1)
        datasets.append(load(Path(filename), owner))
    if len(datasets) != 2: raise SystemExit("exactly two datasets required")
    left, right = datasets
    candidates = []
    for a in left:
        for b in right:
            candidates.append((cosine(a["terms"], b["terms"]), a, b))
    candidates.sort(key=lambda row: (row[0], row[1]["id"], row[2]["id"]))
    n = min(args.pairs, len(candidates))
    # Half high lexical candidates, half low/near-negative candidates.
    selected = candidates[-(n // 2):] + candidates[: n - (n // 2)]
    selected.sort(key=lambda row: (row[1]["id"], row[2]["id"]))
    rows = []
    for index, (lexical, a, b) in enumerate(selected):
        tool_jaccard = len(a["tools"] & b["tools"]) / len(a["tools"] | b["tools"]) if (a["tools"] | b["tools"]) else 0.0
        calls = []
        for repeat in range(args.repeats):
            result = ask((a, b), args.model, args.timeout, args.seed + index * 100 + repeat)
            calls.append(result)
        valid = [call for call in calls if "label" in call]
        labels = [call["label"] for call in valid]
        rows.append({
            "pair_index": index,
            "lexical_cosine": lexical,
            "tool_name_jaccard": tool_jaccard,
            "a_session_hash": hashlib.sha256(a["id"].encode()).hexdigest(),
            "b_session_hash": hashlib.sha256(b["id"].encode()).hexdigest(),
            "calls": calls,
            "agreement": len(set(labels)) == 1 if labels else False,
        })
    valid_calls = [call for row in rows for call in row["calls"] if "label" in call]
    result = {
        "schema": "dataclaw-cross-user-luna-adjudication-v1",
        "model": args.model,
        "pair_count": len(rows),
        "repeats_per_pair": args.repeats,
        "valid_call_count": len(valid_calls),
        "total_elapsed_ms": sum(call.get("elapsed_ms", 0) for row in rows for call in row["calls"]),
        "pair_agreement_count": sum(1 for row in rows if row["agreement"]),
        "rows": rows,
        "claim_boundary": "Silver frontier labels only; no independent task-equivalence ground truth or user-skill claim.",
        "content_policy": "Session IDs are hashed; summaries and model reasons are not emitted.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: result[k] for k in ("pair_count", "repeats_per_pair", "valid_call_count", "pair_agreement_count", "total_elapsed_ms", "claim_boundary")}, indent=2))


if __name__ == "__main__":
    main()
