#!/usr/bin/env python3
"""Compare licensed DataClaw exports without emitting transcript content."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from dataclaw_user_history_audit import audit, normalized_tool_call, words


def extract(path: Path) -> tuple[set[str], set[str], Counter[str]]:
    vocabulary: set[str] = set()
    calls: set[str] = set()
    tools: Counter[str] = Counter()
    with path.open(encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            try:
                session = json.loads(line)
            except json.JSONDecodeError:
                continue
            for message in session.get("messages", []):
                if not isinstance(message, dict):
                    continue
                if message.get("role") == "user" and isinstance(message.get("content"), str):
                    vocabulary.update(words(message["content"]))
                if message.get("role") != "assistant":
                    continue
                for call in message.get("tool_uses", []):
                    if not isinstance(call, dict):
                        continue
                    tools[str(call.get("tool", "<missing>"))] += 1
                    candidate = normalized_tool_call(str(call.get("tool", "<missing>")), call.get("input"))
                    if candidate:
                        calls.add(candidate)
    return vocabulary, calls, tools


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", action="append", required=True, metavar="OWNER=PATH")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    datasets: dict[str, dict] = {}
    extracted: dict[str, tuple[set[str], set[str], Counter[str]]] = {}
    for item in args.dataset:
        owner, raw_path = item.split("=", 1)
        path = Path(raw_path)
        receipt = audit(path)
        receipt["source"]["owner_label"] = owner
        datasets[owner] = receipt
        extracted[owner] = extract(path)
    owners = sorted(datasets)
    assert len(owners) >= 2
    left, right = owners[:2]
    left_vocab, left_calls, left_tools = extracted[left]
    right_vocab, right_calls, right_tools = extracted[right]
    vocab_union = left_vocab | right_vocab
    call_union = left_calls | right_calls
    result = {
        "schema": "dataclaw-multi-user-overlap-v1",
        "datasets": {owner: {
            "sessions": datasets[owner]["sessions"],
            "project_count": datasets[owner]["project_count"],
            "tool_uses": datasets[owner]["tool_uses"],
            "friction_session_rate": datasets[owner]["friction_session_rate"],
            "source_sha256": datasets[owner]["source"]["sha256"],
            "license": datasets[owner]["source"]["license"],
        } for owner in owners},
        "pair": {
            "owners": [left, right],
            "prompt_vocabulary_intersection": len(left_vocab & right_vocab),
            "prompt_vocabulary_union": len(vocab_union),
            "prompt_vocabulary_jaccard": len(left_vocab & right_vocab) / len(vocab_union) if vocab_union else 0.0,
            "shared_nontrivial_tool_call_forms": len(left_calls & right_calls),
            "union_nontrivial_tool_call_forms": len(call_union),
            "shared_tool_name_count": len(set(left_tools) & set(right_tools)),
        },
        "claim_boundary": "Cross-user lexical/action overlap is descriptive only; no task labels, outputs, or outcome equivalence are available.",
        "content_policy": "Only counts and hashes are emitted; prompt and tool text are not emitted.",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
