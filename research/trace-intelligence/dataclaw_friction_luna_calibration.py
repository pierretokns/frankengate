#!/usr/bin/env python3
"""Calibrate deterministic friction/re-prompt signals with frontier silver labels."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import time
from pathlib import Path

from dataclaw_cross_user_luna_adjudication import clean_text

LABELS = {"friction", "productive_iteration", "unclear"}
SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["label", "confidence", "reason"],
    "properties": {
        "label": {"type": "string", "enum": sorted(LABELS)},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "reason": {"type": "string"},
    },
}
FRICTION_RE = re.compile(r"\b(?:error|errors|failed|failure|failing|broken|bug|wrong|still|retry|again|doesn['’]?t|does not|not working|isn['’]?t|is not|revert|regression|crash|misunderstood|not what|actually|instead)\b", re.I)


def load(path: Path) -> list[dict]:
    candidates = []
    for line in path.open(encoding="utf-8", errors="ignore"):
        try: session = json.loads(line)
        except json.JSONDecodeError: continue
        previous = ""
        for index, message in enumerate(session.get("messages", [])):
            if not isinstance(message, dict) or message.get("role") != "user": continue
            content = message.get("content")
            if not isinstance(content, str): continue
            current = clean_text(content)
            if len(current) < 8: previous = current; continue
            detector = bool(FRICTION_RE.search(current))
            overlap = 0.0
            if previous:
                a = set(re.findall(r"[a-z][a-z0-9_./:-]{2,}", previous.lower()))
                b = set(re.findall(r"[a-z][a-z0-9_./:-]{2,}", current.lower()))
                overlap = len(a & b) / len(a | b) if a and b else 0.0
            candidates.append({
                "session_id": str(session.get("session_id", "")), "project": str(session.get("project", "<missing>")),
                "message_index": index, "text": current[:1400], "previous": previous[:700],
                "detector_friction": detector, "detector_reprompt": overlap >= 0.45,
            })
            previous = current
    return candidates


def ask(row: dict, model: str, timeout: int) -> dict:
    prompt = (
        "Classify the current coding-agent user message. `friction` requires evidence of a failed, wrong, broken, or unwanted result. "
        "`productive_iteration` is a normal next instruction or clarification without evidence of failure. `unclear` means insufficient context. "
        "Do not infer the user's skill or identity. Return JSON only.\n\n" + json.dumps(SCHEMA, sort_keys=True)
        + "\nPREVIOUS USER MESSAGE:\n" + row["previous"] + "\nCURRENT USER MESSAGE:\n" + row["text"]
    )
    with tempfile.TemporaryDirectory(prefix="frankengate-friction-luna-") as directory:
        root = Path(directory); schema = root / "schema.json"; output = root / "output.json"
        schema.write_text(json.dumps(SCHEMA), encoding="utf-8")
        started = time.perf_counter()
        proc = subprocess.run([
            "codex", "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules", "--skip-git-repo-check",
            "-s", "read-only", "-m", model, "--output-schema", str(schema), "--output-last-message", str(output),
        ], input=prompt, text=True, capture_output=True, timeout=timeout, cwd="/private/tmp", check=False)
        elapsed_ms = (time.perf_counter() - started) * 1000
        if proc.returncode != 0 or not output.exists(): return {"error": f"exit_{proc.returncode}", "elapsed_ms": elapsed_ms}
        raw = output.read_text(encoding="utf-8").strip(); start, end = raw.find("{"), raw.rfind("}")
        try:
            value = json.loads(raw[start:end + 1]); label = value["label"]; confidence = float(value["confidence"])
            if label not in LABELS or not 0 <= confidence <= 1: raise ValueError("invalid label")
        except Exception as exc: return {"error": type(exc).__name__, "elapsed_ms": elapsed_ms}
        return {"label": label, "confidence": confidence, "elapsed_ms": elapsed_ms, "output_sha256": hashlib.sha256(raw.encode()).hexdigest()}


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--input", type=Path, required=True); parser.add_argument("--out", type=Path, required=True); parser.add_argument("--model", default="gpt-5.6-luna"); parser.add_argument("--rows", type=int, default=8); parser.add_argument("--repeats", type=int, default=2); parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args(); candidates = load(args.input)
    friction = [r for r in candidates if r["detector_friction"]]; reprompt = [r for r in candidates if r["detector_reprompt"] and not r["detector_friction"]]; neutral = [r for r in candidates if not r["detector_friction"] and not r["detector_reprompt"]]
    selected = friction[: max(1, args.rows // 2)] + reprompt[: max(1, args.rows // 4)] + neutral[: max(1, args.rows - (args.rows // 2) - (args.rows // 4))]
    rows = []
    for index, row in enumerate(selected[:args.rows]):
        calls = [ask(row, args.model, args.timeout) for _ in range(args.repeats)]
        labels = [c["label"] for c in calls if "label" in c]
        rows.append({"row_index": index, "session_hash": hashlib.sha256(row["session_id"].encode()).hexdigest(), "project_hash": hashlib.sha256(row["project"].encode()).hexdigest(), "message_index": row["message_index"], "detector_friction": row["detector_friction"], "detector_reprompt": row["detector_reprompt"], "calls": calls, "agreement": len(set(labels)) == 1 if labels else False})
    valid = [c for row in rows for c in row["calls"] if "label" in c]
    result = {"schema": "dataclaw-friction-luna-calibration-v1", "model": args.model, "row_count": len(rows), "repeats_per_row": args.repeats, "valid_call_count": len(valid), "agreement_count": sum(r["agreement"] for r in rows), "labels": {label: sum(c.get("label") == label for c in valid) for label in sorted(LABELS)}, "detector_friction_calls": sum(c.get("label") == "friction" for r in rows if r["detector_friction"] for c in r["calls"]), "rows": rows, "claim_boundary": "Frontier silver calibration only; no independent friction ground truth or causal outcome.", "content_policy": "Session/project identifiers are hashed; messages and model reasons are not emitted."}
    args.out.parent.mkdir(parents=True, exist_ok=True); args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"); print(json.dumps({k: result[k] for k in ("row_count", "valid_call_count", "agreement_count", "labels", "claim_boundary")}, indent=2))


if __name__ == "__main__": main()
