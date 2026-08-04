#!/usr/bin/env python3
"""Frontier-screen recurring tool artifacts from the multi-harness DataClaw sample.

Candidates are selected deterministically from repeated successful normalized
tool inputs. Luna receives only a bounded, credential-scrubbed preview of the
candidate examples. The committed receipt stores hashes, labels, and
agreement—not command text, tool output, or model reasons.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from dataclaw_zhiyaowang_audit import (
    content_fingerprint,
    request_row,
    request_rows,
    _normalize_value,
)


LABELS = {"reusable_procedure", "context_specific", "unsafe_or_sensitive", "insufficient_evidence"}
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
SECRET_RE = re.compile(r"(?i)(bearer\s+|sk-[a-z0-9_-]{12,}|gh[pousr]_[a-z0-9_]{12,}|xox[baprs]-[a-z0-9-]{12,}|aws_secret_access_key\s*[=:]\s*)[^\s,;]+")
LONG_TOKEN_RE = re.compile(r"\b[a-z0-9+/=_-]{32,}\b", re.I)


def digest(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def scrub(value: Any, *, limit: int = 1800) -> Any:
    if isinstance(value, str):
        text = SECRET_RE.sub("<credential>", value)
        text = LONG_TOKEN_RE.sub("<token>", text)
        text = " ".join(text.split())
        return text[:limit]
    if isinstance(value, dict):
        return {str(key): scrub(value[key], limit=limit) for key in sorted(value, key=str)}
    if isinstance(value, list):
        return [scrub(item, limit=limit) for item in value[:32]]
    return value


def fetch_sample(sample_count: int, timeout: int) -> list[dict[str, Any]]:
    total, _ = request_row(0, timeout)
    window_count = min(8, sample_count)
    window_size = (sample_count + window_count - 1) // window_count
    starts = sorted({round(index * (total - window_size) / max(1, window_count - 1)) for index in range(window_count)})
    rows: dict[int, dict[str, Any]] = {}
    for offset in starts:
        _, batch = request_rows(offset, window_size, timeout)
        for index, row in enumerate(batch):
            rows[offset + index] = row
    return [rows[offset] for offset in sorted(rows)]


def status_of(call: dict[str, Any]) -> str:
    output = call.get("output")
    if isinstance(output, dict):
        return str(call.get("status") or output.get("status") or "unknown").lower()
    return str(call.get("status") or "unknown").lower()


def collect_candidates(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    good = {"success", "completed"}
    for row in rows:
        session_hash = digest(row.get("session_id"))
        project_hash = digest(row.get("project"))
        source_hash = digest(row.get("source"))
        model_hash = digest(row.get("model"))
        messages = row.get("messages") if isinstance(row.get("messages"), list) else []
        for message in messages:
            if not isinstance(message, dict):
                continue
            uses = message.get("tool_uses") if isinstance(message.get("tool_uses"), list) else []
            for call in uses:
                if not isinstance(call, dict) or status_of(call) not in good:
                    continue
                fingerprint = content_fingerprint(call)
                entry = grouped.setdefault(
                    fingerprint,
                    {"fingerprint": fingerprint, "sessions": set(), "projects": set(), "sources": set(), "models": set(), "successes": 0, "examples": []},
                )
                entry["sessions"].add(session_hash)
                entry["projects"].add(project_hash)
                entry["sources"].add(source_hash)
                entry["models"].add(model_hash)
                entry["successes"] += 1
                if len(entry["examples"]) < 3:
                    entry["examples"].append(scrub({"tool": call.get("tool") or call.get("name"), "input": call.get("input"), "output": call.get("output"), "status": status_of(call)}))
    candidates = [entry for entry in grouped.values() if len(entry["sessions"]) >= 2 and entry["successes"] >= 2]
    candidates.sort(key=lambda item: (-len(item["projects"]), -item["successes"], item["fingerprint"]))
    return candidates[:limit]


def parse_judgment(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8").strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object")
    value = json.loads(raw[start : end + 1])
    if value.get("label") not in LABELS:
        raise ValueError("invalid label")
    confidence = float(value.get("confidence"))
    if not 0 <= confidence <= 1:
        raise ValueError("invalid confidence")
    return {"label": value["label"], "confidence": confidence, "output_sha256": hashlib.sha256(raw.encode()).hexdigest()}


def ask(candidate: dict[str, Any], model: str, timeout: int, seed: int) -> dict[str, Any]:
    prompt = (
        "Review repeated tool-artifact examples from coding-agent traces. "
        "Label reusable_procedure only when the examples show a potentially reusable operation "
        "that could be safely parameterized and revalidated. Label context_specific when it is "
        "tied to a project/path or lacks portability. Label unsafe_or_sensitive for credentials, "
        "destructive/irreversible behavior, or unsafe disclosure. Label insufficient_evidence when "
        "the bounded examples do not establish enough. Do not infer user identity, skill, employer, "
        "or task correctness from frequency. Return JSON only.\n\n"
        + json.dumps(SCHEMA, sort_keys=True)
        + "\n\nCANDIDATE COVERAGE:\n"
        + json.dumps({"successes": candidate["successes"], "session_count": len(candidate["sessions"]), "project_count": len(candidate["projects"]), "model_count": len(candidate["models"]), "source_count": len(candidate["sources"])}, sort_keys=True)
        + "\nEXAMPLES:\n"
        + json.dumps(candidate["examples"], ensure_ascii=False, sort_keys=True)
        + f"\nREVIEW SEED: {seed}\n"
    )
    with tempfile.TemporaryDirectory(prefix="frankengate-artifact-luna-") as directory:
        root = Path(directory)
        schema = root / "schema.json"
        output = root / "output.json"
        schema.write_text(json.dumps(SCHEMA), encoding="utf-8")
        started = time.perf_counter()
        process = subprocess.run(
            ["codex", "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules", "--skip-git-repo-check", "-s", "read-only", "-m", model, "--output-schema", str(schema), "--output-last-message", str(output)],
            input=prompt,
            text=True,
            capture_output=True,
            timeout=timeout,
            cwd="/private/tmp",
            check=False,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        if process.returncode != 0 or not output.exists():
            return {"error": f"exit_{process.returncode}", "elapsed_ms": elapsed_ms}
        try:
            parsed = parse_judgment(output)
        except Exception as exc:  # noqa: BLE001
            return {"error": type(exc).__name__, "elapsed_ms": elapsed_ms}
        parsed["elapsed_ms"] = elapsed_ms
        return parsed


def run(*, sample_count: int, candidate_count: int, repeats: int, model: str, timeout: int, output: Path) -> dict[str, Any]:
    rows = fetch_sample(sample_count, timeout)
    candidates = collect_candidates(rows, candidate_count)
    result_rows: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates):
        calls = [ask(candidate, model, timeout, index * 100 + repeat) for repeat in range(repeats)]
        labels = [call["label"] for call in calls if "label" in call]
        result_rows.append(
            {
                "candidate_hash": candidate["fingerprint"],
                "successes": candidate["successes"],
                "session_count": len(candidate["sessions"]),
                "project_count": len(candidate["projects"]),
                "source_count": len(candidate["sources"]),
                "model_count": len(candidate["models"]),
                "calls": calls,
                "agreement": len(set(labels)) == 1 if labels else False,
            }
        )
    valid = [call for row in result_rows for call in row["calls"] if "label" in call]
    label_counts = collections.Counter(call["label"] for call in valid)
    by_coverage: dict[str, dict[str, int]] = collections.defaultdict(lambda: collections.Counter())
    for row in result_rows:
        labels = [call["label"] for call in row["calls"] if "label" in call]
        key = "cross_project" if row["project_count"] >= 2 else "single_project"
        for label in labels:
            by_coverage[key][label] += 1
    result = {
        "schema": "frankengate-dataclaw-artifact-frontier-screen-v1",
        "source": {"dataset": "zhiyaowang/dataclaw-zhiyaowang", "revision": "f5157333cbc22489661122a9bc5347b137144900", "sample_count": len(rows), "raw_content_committed": False},
        "model": model,
        "candidate_count": len(result_rows),
        "repeats_per_candidate": repeats,
        "valid_call_count": len(valid),
        "agreement_count": sum(row["agreement"] for row in result_rows),
        "labels": dict(sorted(label_counts.items())),
        "labels_by_coverage": {key: dict(sorted(value.items())) for key, value in sorted(by_coverage.items())},
        "rows": result_rows,
        "claim_boundary": "Frontier silver screening of recurrence candidates; no independent task-success labels, correctness proof, safety certification, or automatic promotion.",
        "content_policy": "Prompts are credential-scrubbed and bounded; raw candidate examples and model reasons are not committed.",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("candidate_count", "valid_call_count", "agreement_count", "labels", "labels_by_coverage", "claim_boundary")}, sort_keys=True))
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-count", type=int, default=32)
    parser.add_argument("--candidate-count", type=int, default=8)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(sample_count=args.sample_count, candidate_count=args.candidate_count, repeats=args.repeats, model=args.model, timeout=args.timeout, output=args.output)


if __name__ == "__main__":
    main()
