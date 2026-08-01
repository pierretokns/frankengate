#!/usr/bin/env python3
"""Content-free audit of a licensed DataClaw Claude Code history export.

This measures observable interaction signals only. Repeated tool-call inputs are
candidate artifacts, never "known good" artifacts, because the export omits tool
outputs and outcome labels.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


FRICTION = re.compile(
    r"\b(?:error|errors|failed|failure|failing|broken|bug|wrong|still|retry|again|"
    r"doesn['’]?t|does not|not working|isn['’]?t|is not|revert|regression|crash|"
    r"misunderstood|not what|actually|instead)\b",
    re.I,
)
CORRECTION = re.compile(
    r"(?:^|\W)(?:no[,\s]|actually\b|instead\b|that['’]?s not|not what|"
    r"you misunderstood|i meant|wrong)(?:$|\W)",
    re.I,
)
GENERIC_COMMAND = re.compile(r"^(?:ls|pwd|cd\s+[^;&|]+|git\s+status|git\s+diff)\s*$", re.I)


def words(text: str) -> set[str]:
    return set(re.findall(r"[a-z][a-z0-9_./:-]{2,}", text.lower()))


def normalized_tool_call(tool: str, value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    if len(text) < 20 or GENERIC_COMMAND.fullmatch(text):
        return None
    return f"{tool.lower()}::{text.lower()}"


def audit(path: Path) -> dict:
    source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    sessions = 0
    messages = 0
    user_messages = 0
    assistant_messages = 0
    tool_uses = 0
    friction_messages = 0
    correction_messages = 0
    reprompt_pairs = 0
    projects = Counter()
    models = Counter()
    tools = Counter()
    recurring_calls: Counter[str] = Counter()
    call_sessions: defaultdict[str, set[str]] = defaultdict(set)
    friction_by_project = Counter()
    session_rows = []

    with path.open(encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            try:
                session = json.loads(line)
            except json.JSONDecodeError:
                continue
            sessions += 1
            sid = str(session.get("session_id", f"row-{sessions}"))
            project = str(session.get("project", "<missing>"))
            model = str(session.get("model", "<missing>"))
            projects[project] += 1
            models[model] += 1
            previous_user_words: set[str] | None = None
            session_friction = 0
            session_corrections = 0
            session_calls = 0
            for message in session.get("messages", []):
                if not isinstance(message, dict):
                    continue
                messages += 1
                role = message.get("role")
                if role == "user":
                    user_messages += 1
                    content = message.get("content")
                    text = content if isinstance(content, str) else ""
                    current_words = words(text)
                    if previous_user_words and current_words:
                        overlap = len(previous_user_words & current_words) / len(previous_user_words | current_words)
                        if overlap >= 0.45 or CORRECTION.search(text):
                            reprompt_pairs += 1
                    previous_user_words = current_words
                    if FRICTION.search(text):
                        friction_messages += 1
                        session_friction += 1
                    if CORRECTION.search(text):
                        correction_messages += 1
                        session_corrections += 1
                elif role == "assistant":
                    assistant_messages += 1
                    calls = message.get("tool_uses", [])
                    if isinstance(calls, list):
                        for call in calls:
                            if not isinstance(call, dict):
                                continue
                            tool = str(call.get("tool", "<missing>"))
                            tools[tool] += 1
                            tool_uses += 1
                            candidate = normalized_tool_call(tool, call.get("input"))
                            if candidate:
                                recurring_calls[candidate] += 1
                                call_sessions[candidate].add(sid)
                                session_calls += 1
            if session_friction:
                friction_by_project[project] += session_friction
            session_rows.append((sid, project, session_friction, session_corrections, session_calls))

    recurring_across_sessions = [key for key, ids in call_sessions.items() if len(ids) >= 2]
    recurring_across_projects = 0
    for key in recurring_across_sessions:
        seen = {project for sid, project, *_ in session_rows if sid in call_sessions[key]}
        if len(seen) >= 2:
            recurring_across_projects += 1
    friction_sessions = sum(1 for _, _, f, _, _ in session_rows if f)
    return {
        "schema": "dataclaw-user-history-audit-v1",
        "source": {
            "dataset": "peteromallet/dataclaw-peteromallet",
            "license": "MIT",
            "sha256": source_hash,
        },
        "sessions": sessions,
        "messages": messages,
        "user_messages": user_messages,
        "assistant_messages": assistant_messages,
        "tool_uses": tool_uses,
        "project_count": len(projects),
        "project_session_counts": dict(sorted(projects.items())),
        "model_session_counts": dict(sorted(models.items())),
        "tool_counts": dict(sorted(tools.items())),
        "friction_messages": friction_messages,
        "friction_session_count": friction_sessions,
        "friction_session_rate": friction_sessions / sessions if sessions else 0.0,
        "correction_messages": correction_messages,
        "reprompt_or_correction_pairs": reprompt_pairs,
        "nontrivial_tool_call_forms": len(recurring_calls),
        "nontrivial_calls_repeated_across_sessions": len(recurring_across_sessions),
        "repeated_calls_seen_across_projects": recurring_across_projects,
        "claim_boundary": {
            "candidate_artifacts_only": True,
            "known_good_artifacts": False,
            "reason": "The export contains tool-call inputs but no tool outputs, independent verification, or task outcome labels.",
        },
        "content_policy": "Only counts, model/project/tool labels, and a source hash are emitted; prompt and tool text are not emitted.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    receipt = audit(args.input)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: receipt[k] for k in ("sessions", "project_count", "tool_uses", "friction_messages", "friction_session_rate", "reprompt_or_correction_pairs", "nontrivial_calls_repeated_across_sessions", "repeated_calls_seen_across_projects", "claim_boundary")}, indent=2))


if __name__ == "__main__":
    main()
