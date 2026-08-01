#!/usr/bin/env python3
"""Mine recurring tool-call candidates from DataClaw without emitting commands."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

FRICTION_RE = re.compile(r"\b(?:error|errors|failed|failure|failing|broken|bug|wrong|still|retry|again|doesn['’]?t|does not|not working|isn['’]?t|is not|revert|regression|crash|misunderstood|not what|actually|instead)\b", re.I)
GENERIC = re.compile(r"^(?:ls|pwd|git\s+status|git\s+diff|cd\s+[^;&|]+)\s*$", re.I)
MANAGEMENT_TOOLS = {"taskupdate", "taskcreate", "taskget", "tasklist", "taskoutput", "taskstop", "todowrite", "enterplanmode", "exitplanmode", "askuserquestion"}


def project(value: object) -> str:
    return str(value or "<missing>")


def normalize_call(tool: object, value: object) -> str | None:
    if not isinstance(value, str): return None
    if str(tool).lower() in MANAGEMENT_TOOLS: return None
    text = " ".join(value.split())
    if len(text) < 20 or GENERIC.fullmatch(text): return None
    return f"{str(tool).lower()}::{text.lower()}"


def mine(path: Path, limit: int) -> dict:
    calls: dict[str, dict] = defaultdict(lambda: {"sessions": set(), "projects": set(), "occurrences": 0, "friction_context": 0, "tool": "<missing>"})
    sessions = 0
    for line in path.open(encoding="utf-8", errors="ignore"):
        try: session = json.loads(line)
        except json.JSONDecodeError: continue
        sessions += 1; sid = str(session.get("session_id", f"row-{sessions}")); proj = project(session.get("project")); previous_user = ""
        for message in session.get("messages", []):
            if not isinstance(message, dict): continue
            if message.get("role") == "user" and isinstance(message.get("content"), str): previous_user = message["content"][-1200:]
            if message.get("role") != "assistant": continue
            for call in message.get("tool_uses", []):
                if not isinstance(call, dict): continue
                key = normalize_call(call.get("tool"), call.get("input"))
                if key is None: continue
                row = calls[key]; row["sessions"].add(sid); row["projects"].add(proj); row["occurrences"] += 1; row["tool"] = str(call.get("tool", "<missing>"))
                if FRICTION_RE.search(previous_user): row["friction_context"] += 1
    ranked = sorted(calls.items(), key=lambda item: (-len(item[1]["sessions"]), -len(item[1]["projects"]), -item[1]["occurrences"], item[0]))[:limit]
    candidates = []
    for raw, row in ranked:
        support_sessions = len(row["sessions"]); support_projects = len(row["projects"])
        candidates.append({
            "candidate_id": hashlib.sha256(raw.encode()).hexdigest(),
            "tool": row["tool"],
            "support_sessions": support_sessions,
            "support_projects": support_projects,
            "occurrences": row["occurrences"],
            "friction_context_occurrences": row["friction_context"],
            "cross_project": support_projects >= 2,
            "review_required": True,
            "promotion_eligible": False,
        })
    return {
        "schema": "dataclaw-candidate-artifact-miner-v1",
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "session_count": sessions,
        "candidate_count": len(candidates),
        "excluded_management_tools": sorted(MANAGEMENT_TOOLS),
        "candidates": candidates,
        "claim_boundary": "Repetition and friction proximity create review candidates only; no correctness, safety, or user-benefit label is inferred.",
        "content_policy": "Commands, prompts, paths, arguments, and identifiers are not emitted; candidate IDs are content hashes.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--input", type=Path, required=True); parser.add_argument("--out", type=Path, required=True); parser.add_argument("--limit", type=int, default=100); args = parser.parse_args()
    result = mine(args.input, args.limit); args.out.parent.mkdir(parents=True, exist_ok=True); args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"); print(json.dumps({k: result[k] for k in ("session_count", "candidate_count", "claim_boundary")}, indent=2))


if __name__ == "__main__": main()
