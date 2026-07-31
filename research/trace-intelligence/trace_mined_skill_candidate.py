#!/usr/bin/env python3
"""Mine a bounded, content-free procedure artifact from external raw audits.

The miner reads only an external JSONL audit directory. It emits a generic
procedure candidate plus aggregate signatures and hashes; prompts, SQL, rows,
and model messages never enter the committed artifact. The candidate is a
hypothesis, not an approved skill.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


CANDIDATE_TEXT = (
    " Trace-mined candidate: after repeated identifier or policy failures, "
    "inspect the authorized schema catalog before any execute_sql call; use "
    "only exact returned table and column identifiers; preserve a successful "
    "attempt identifier, submit that exact attempt, and abstain when no "
    "authorized attempt succeeds."
)


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def mine(raw_dir: Path, *, expected_min_files: int = 1) -> dict[str, Any]:
    paths = sorted(raw_dir.rglob("*.jsonl"))
    if len(paths) < expected_min_files:
        raise ValueError("not enough external raw audit files")
    file_hashes = [_sha256(path.read_bytes()) for path in paths]
    protocol_codes: Counter[str] = Counter()
    event_counts: Counter[str] = Counter()
    no_schema_files = 0
    policy_denied_files = 0
    for path in paths:
        records = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        names = Counter(str(record.get("event", "")) for record in records)
        event_counts.update(names)
        if not any(
            record.get("event") == "agent_tool_result"
            and record.get("name") == "describe_schema"
            for record in records
        ):
            no_schema_files += 1
        denied = False
        for record in records:
            if record.get("event") == "agent_tool_result":
                try:
                    content = json.loads(str(record.get("content", "{}")))
                except json.JSONDecodeError:
                    content = {}
                code = content.get("code")
                if code:
                    protocol_codes[str(code)] += 1
                denied = denied or content.get("status") == "policy_denied"
        policy_denied_files += int(denied)
    source_digest = _sha256("\n".join(sorted(file_hashes)).encode())
    result = {
        "schema_version": "frankengate-trace-mined-skill-candidate-v1",
        "source_raw_file_count": len(paths),
        "source_raw_directory_digest": source_digest,
        "source_signature": {
            "files_without_describe_schema": no_schema_files,
            "files_with_policy_denial": policy_denied_files,
            "protocol_error_codes": dict(sorted(protocol_codes.items())),
            "event_counts": dict(sorted(event_counts.items())),
        },
        "candidate_class": "trace_mined_hypothesis",
        "candidate_text": CANDIDATE_TEXT,
        "candidate_text_sha256": _sha256(CANDIDATE_TEXT.encode()),
        "promotion_authorized": False,
        "raw_content_emitted": False,
    }
    result["result_sha256"] = _sha256(
        json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--raw-audit-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = mine(args.raw_audit_dir.resolve(strict=True))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
