#!/usr/bin/env python3
"""Convert native Codex rollouts to a content-bearing private calibration input.

The generated JSONL is intended for a local, authorized frontier calibration
run and must remain outside Git. The committed calibration receipt contains
only hashes, detector flags, and aggregate labels.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def payload_text(payload: dict[str, Any]) -> str:
    value = payload.get("message", payload.get("output", ""))
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(
            str(item.get("text", ""))
            for item in value
            if isinstance(item, dict) and isinstance(item.get("text"), str)
        )
    return ""


def session(path: Path) -> dict[str, Any]:
    session_id = path.stem
    project = "<missing>"
    messages: list[dict[str, str]] = []
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            payload = record.get("payload") if isinstance(record, dict) else None
            if not isinstance(payload, dict):
                continue
            if isinstance(payload.get("cwd"), str):
                project = payload["cwd"]
            # ``user_message`` is the native user-event signal. Avoid
            # response_item/developer-context messages that also have role=user.
            if payload.get("type") != "user_message":
                continue
            text = payload_text(payload).strip()
            if text:
                messages.append({"role": "user", "content": text})
    return {"session_id": session_id, "project": project, "messages": messages}


def convert(root: Path, output: Path) -> dict[str, Any]:
    paths = sorted(root.glob("rollout-*.jsonl"))
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        session_count = 0
        message_count = 0
        source_digest = hashlib.sha256()
        for path in paths:
            source_digest.update(hashlib.sha256(path.read_bytes()).digest())
            row = session(path)
            session_count += 1
            message_count += len(row["messages"])
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {
        "schema_version": "frankengate-codex-private-friction-input-v1",
        "source": {"path_count": len(paths), "path_sha256": source_digest.hexdigest(), "raw_content_committed": False},
        "sessions": session_count,
        "user_messages": message_count,
        "output_path": str(output),
        "claim_boundary": "Private calibration input only; no labels, outcomes, or enterprise quality claims.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = convert(args.root, args.output)
    print(json.dumps({key: value for key, value in result.items() if key != "output_path"}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
