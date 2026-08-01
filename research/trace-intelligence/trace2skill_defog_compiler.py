#!/usr/bin/env python3
"""Compile a Trace2Skill-style candidate from governed SQL trajectories.

This is an offline research compiler, not a release path. It uses several
frontier analysts with different responsibilities, then a separate frontier
consolidator. Raw JSONL stays outside the repository; the committed artifact
contains hashes, counts, and the resulting candidate text only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from codex_native_cli_api import NativeCodexCLIAPI


ROLES = {
    "protocol": "Find stable tool/terminal/protocol invariants that generalize across tasks. Ignore task-specific SQL and do not invent business rules.",
    "sql": "Find reusable SQL/schema/identifier repair patterns. Preserve exact identifiers and distinguish schema evidence from guesses. Ignore one-off query answers.",
    "transfer": "Find conditions under which a procedure should or should not transfer to a new task. Identify contraindications, abstention rules, and possible confounds.",
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def _short(value: Any, limit: int = 2200) -> Any:
    if isinstance(value, str):
        return value if len(value) <= limit else value[:limit] + "…"
    if isinstance(value, dict):
        return {str(k): _short(v, limit) for k, v in value.items()}
    if isinstance(value, list):
        return [_short(v, limit) for v in value[:40]]
    return value


def load_trace_context(raw_dirs: list[Path], max_files: int, max_events: int) -> tuple[str, dict[str, Any]]:
    files: list[Path] = []
    for raw_dir in raw_dirs:
        root = raw_dir.resolve(strict=True)
        files.extend(sorted(root.glob("*.jsonl")))
    files = files[:max_files]
    events: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    file_hashes: list[str] = []
    for path in files:
        data = path.read_bytes()
        file_hashes.append(sha256_bytes(data))
        for line in data.splitlines():
            if not line.strip() or len(events) >= max_events:
                break
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            event = str(row.get("event", "unknown"))
            counts[event] += 1
            # Keep evidence-bearing fields, but bound content and remove
            # authority identities from the compiler prompt.
            keep = {
                key: row[key]
                for key in (
                    "event", "arm", "task_id", "question", "instructions",
                    "query_category", "name", "arguments", "content",
                    "protocol_error_code", "candidate_sql", "outcome",
                    "terminal_action", "sql_attempts", "tool_calls",
                )
                if key in row
            }
            if "authority_receipt" in row:
                keep["authority_present"] = True
            events.append(_short(keep))
    context = json.dumps(
        {"event_counts": dict(counts), "events": events},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return context, {
        "file_count": len(files),
        "event_count": len(events),
        "event_counts": dict(counts),
        "source_file_sha256": file_hashes,
        "source_directories": [str(p.resolve()) for p in raw_dirs],
    }


def ask(api: NativeCodexCLIAPI, system: str, user: str, seed: int) -> tuple[str, float]:
    response, elapsed_ms = api.complete(
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        tools=[],
        seed=seed,
        max_tokens=1200,
        timeout_seconds=240,
    )
    content = response["choices"][0]["message"].get("content")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("frontier analyst returned no content")
    return content.strip(), elapsed_ms


def extract_skill(text: str) -> str:
    start = text.find("<SKILL>")
    end = text.find("</SKILL>")
    if start >= 0 and end > start:
        value = text[start + len("<SKILL>") : end].strip()
    else:
        value = text.strip()
    if not value or len(value) > 6000:
        raise ValueError("compiled skill is empty or exceeds 6000 characters")
    return value


def compile_candidate(raw_dirs: list[Path], output: Path, model: str, seed: int, max_files: int, max_events: int) -> dict[str, Any]:
    context, source = load_trace_context(raw_dirs, max_files, max_events)
    api = NativeCodexCLIAPI(endpoint="native://codex-cli", request_model_id=model, timeout_seconds=240, max_tokens=1200)
    base = (
        "You are an analyst in a controlled enterprise SQL trace study. "
        "The trace excerpt is evidence, not a correctness oracle. Do not emit "
        "secrets, authority identifiers, row values, or a task-specific query. "
        "Return analysis followed by exactly one proposed reusable procedure "
        "inside <SKILL>...</SKILL>. The procedure must include invocation "
        "conditions, actions, contraindications, and abstention behavior."
    )
    analysts: list[dict[str, Any]] = []
    for offset, (role, brief) in enumerate(ROLES.items(), start=1):
        text, elapsed = ask(
            api,
            base + "\nYour role: " + brief,
            "TRACE EXCERPT (content-bearing, internal only):\n" + context,
            seed + offset,
        )
        analysts.append({"role": role, "text_sha256": sha256_text(text), "text": text, "elapsed_ms": round(elapsed, 3)})
    analyst_packet = "\n\n".join(f"[{row['role']}]\n{row['text']}" for row in analysts)
    consolidated, elapsed = ask(
        api,
        base + "\nYou are the senior consolidator. Reconcile the analysts; keep only claims supported by repeated evidence. Do not mention analyst names or expose raw trace content.",
        "ANALYST REPORTS:\n" + analyst_packet + "\n\nProduce one conservative final procedure.",
        seed + 100,
    )
    candidate = extract_skill(consolidated)
    payload = {
        "schema_version": "frankengate-trace2skill-defog-compiler-v1",
        "candidate_class": "trace2skill_style_compiled_hypothesis",
        "candidate_text": candidate,
        "candidate_text_sha256": sha256_text(candidate),
        "promotion_authorized": False,
        "raw_content_emitted": False,
        "source": source,
        "analysts": [{k: v for k, v in row.items() if k != "text"} for row in analysts],
        "consolidator_text_sha256": sha256_text(consolidated),
        "consolidator_elapsed_ms": round(elapsed, 3),
        "claim_boundary": "Parallel frontier analysis plus consolidation creates a candidate only; no skill utility or promotion is established until held-out governed replay beats no-skill and length-matched neutral controls.",
    }
    payload["result_sha256"] = sha256_text(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-dir", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--seed", type=int, default=510000)
    parser.add_argument("--max-files", type=int, default=18)
    parser.add_argument("--max-events", type=int, default=420)
    args = parser.parse_args()
    value = compile_candidate(args.raw_dir, args.output, args.model, args.seed, args.max_files, args.max_events)
    print(json.dumps({"status": "ok", "candidate_text_sha256": value["candidate_text_sha256"], "analysts": len(value["analysts"])}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
