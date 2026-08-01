#!/usr/bin/env python3
"""Audit Trace Commons metadata without copying transcript content.

This is a readiness check, not a clustering benchmark.  It deliberately records
only structural counts and normalized metadata so the result cannot become a
second copy of the corpus.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


IDENTITY_KEYS = {
    "user",
    "user_id",
    "userId",
    "author",
    "author_id",
    "account_id",
    "organization_id",
    "tenant_id",
    "email",
}
PROJECT_KEYS = {"cwd", "gitBranch", "repository", "repo", "workspace", "project"}


def normalize_cwd(value: str) -> str:
    value = value.replace("\\", "/")
    value = re.sub(r"/Users/[^/]+", "/Users/USER", value, flags=re.I)
    value = re.sub(r"/home/[^/]+", "/home/USER", value, flags=re.I)
    value = re.sub(r"[A-Za-z]:/Users/[^/]+", "C:/Users/USER", value, flags=re.I)
    return value


def audit(root: Path) -> dict:
    files = sorted(root.rglob("*.jsonl"))
    event_types = Counter()
    key_counts = Counter()
    sessions = set()
    cwd_to_sessions: dict[str, set[str]] = defaultdict(set)
    branch_to_sessions: dict[str, set[str]] = defaultdict(set)
    identity_values = Counter()
    line_count = 0
    user_messages = 0
    tool_events = 0

    for path in files:
        for line in path.open(encoding="utf-8", errors="ignore"):
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            line_count += 1
            event_types[str(event.get("type", "<missing>"))] += 1
            key_counts.update(event.keys())
            session = event.get("sessionId")
            if isinstance(session, str):
                sessions.add(session)
            cwd = event.get("cwd")
            if isinstance(cwd, str) and isinstance(session, str):
                cwd_to_sessions[normalize_cwd(cwd)].add(session)
            branch = event.get("gitBranch")
            if isinstance(branch, str) and isinstance(session, str):
                branch_to_sessions[branch].add(session)
            if event.get("type") == "user":
                user_messages += 1
            if "toolUseResult" in event:
                tool_events += 1
            for key in IDENTITY_KEYS:
                if key in event:
                    identity_values[key] += 1

    duplicate_projects = {
        project: sorted(session_ids)
        for project, session_ids in cwd_to_sessions.items()
        if len(session_ids) > 1
    }
    return {
        "schema": "trace-commons-metadata-audit-v1",
        "source_root_name": root.name,
        "file_count": len(files),
        "line_count": line_count,
        "event_type_counts": dict(sorted(event_types.items())),
        "key_presence_counts": dict(sorted(key_counts.items())),
        "session_count": len(sessions),
        "user_message_count": user_messages,
        "tool_event_count": tool_events,
        "explicit_identity_key_counts": dict(sorted(identity_values.items())),
        "normalized_project_count": len(cwd_to_sessions),
        "projects_with_multiple_sessions": duplicate_projects,
        "branch_count": len(branch_to_sessions),
        "readiness": {
            "has_explicit_user_identity": bool(identity_values),
            "has_session_identity": bool(sessions),
            "has_project_proxy": bool(cwd_to_sessions),
            "supports_cross_user_clustering": False,
            "reason": (
                "The export contains session IDs and cwd/gitBranch proxies but no explicit "
                "user, tenant, organization, or author identity. A cross-user result would "
                "therefore be an unsupported inference; only a session/project-proxy study "
                "is admissible."
            ),
        },
        "content_policy": "No transcript, prompt, tool argument, or response content is emitted.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    receipt = audit(args.root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: receipt[k] for k in ("file_count", "line_count", "session_count", "normalized_project_count", "readiness")}, indent=2))


if __name__ == "__main__":
    main()
