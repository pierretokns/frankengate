#!/usr/bin/env python3
"""Test the Claude/Codex rollout -> canonical events -> gap miner contract.

This experiment deliberately sits before a database.  It answers a question the
database benchmark cannot: whether native Claude Code and Codex rollout shapes
retain enough lifecycle evidence to support wiki-gap mining, and whether a
replayed/out-of-order batch is safe to project into an analytical store.

The cohort is synthetic but shaped like the native public formats.  It contains
known positives and controls, malformed input, duplicate delivery, reordering,
and observability ablations.  The receipt contains no prompt text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from wiki_gap_miner import mine_gap_candidates


SCHEMA_VERSION = "frankengate-rollout-ingestion-experiment-v1"


def _id(prefix: str, value: str) -> str:
    return f"{prefix}-{hashlib.sha256(value.encode()).hexdigest()[:16]}"


def _question(query_id: str, user_id: str, text: str) -> dict[str, Any]:
    return {
        "event_id": _id("question", query_id),
        "event_type": "question",
        "query_id": query_id,
        "session_id": f"session-{query_id}",
        "user_id": user_id,
        "text": text,
        "timestamp": "2026-08-03T12:00:00Z",
    }


def claude_rollout(query_id: str, user_id: str, text: str, *, mode: str) -> bytes:
    """Return a native-looking Claude Code JSONL rollout."""
    records: list[dict[str, Any]] = [
        {"type": "user", "sessionId": f"session-{query_id}", "message": {"role": "user", "content": text}},
    ]
    if mode != "unobserved":
        records.append({
            "type": "assistant",
            "sessionId": f"session-{query_id}",
            "message": {"role": "assistant", "content": [{"type": "tool_use", "id": f"search-{query_id}", "name": "wiki_search", "input": {"query": text}}]},
        })
        page_ids = [] if mode in {"absent", "external"} else [f"page-{query_id}"]
        records.append({
            "type": "user",
            "sessionId": f"session-{query_id}",
            "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": f"search-{query_id}", "content": json.dumps({"page_ids": page_ids})}]},
        })
    if mode == "external":
        records.append({
            "type": "assistant",
            "message": {"role": "assistant", "content": [{"type": "tool_use", "id": f"tool-{query_id}", "name": "aws_cli", "input": {"command": "describe"}}]},
        })
    if mode == "stale":
        records.append({"type": "user", "message": {"role": "user", "content": "That page is stale; the endpoint moved."}})
    records.append({"type": "result", "result": "failed" if mode in {"absent", "external", "incomplete"} else "success"})
    return ("\n".join(json.dumps(record, separators=(",", ":")) for record in records) + "\n").encode()


def codex_rollout(query_id: str, user_id: str, text: str, *, mode: str) -> bytes:
    """Return a native-looking Codex archived rollout JSONL."""
    records: list[dict[str, Any]] = [
        {"timestamp": "2026-08-03T12:00:00Z", "payload": {"type": "user_message", "message": text}},
    ]
    if mode != "unobserved":
        records.extend([
            {"timestamp": "2026-08-03T12:00:01Z", "payload": {"type": "function_call", "name": "wiki_search", "arguments": json.dumps({"query": text})}},
            {"timestamp": "2026-08-03T12:00:02Z", "payload": {"type": "function_call_output", "output": json.dumps({"page_ids": [] if mode in {"absent", "external"} else [f"page-{query_id}"], "status": "ok"})}},
        ])
    if mode == "external":
        records.extend([
            {"timestamp": "2026-08-03T12:00:03Z", "payload": {"type": "function_call", "name": "aws_cli", "arguments": "{\"command\":\"describe\"}"}},
            {"timestamp": "2026-08-03T12:00:04Z", "payload": {"type": "function_call_output", "output": "exit code 0"}},
        ])
    if mode == "stale":
        records.append({"timestamp": "2026-08-03T12:00:03Z", "payload": {"type": "user_message", "message": "Actually, that is stale and wrong."}})
    records.append({"timestamp": "2026-08-03T12:00:05Z", "payload": {"type": "function_call_output", "output": "failed" if mode in {"absent", "external", "incomplete"} else "all tests pass"}})
    return ("\n".join(json.dumps(record, separators=(",", ":")) for record in records) + "\n").encode()


def _content_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return " ".join(str(item.get("text", "")) for item in value if isinstance(item, dict))
    return ""


def adapt_claude(raw: bytes, *, query_id: str, user_id: str) -> tuple[list[dict[str, Any]], int]:
    events: list[dict[str, Any]] = [_question(query_id, user_id, "How do I rotate the mantle key?")]
    malformed = 0
    for line_number, line in enumerate(raw.splitlines(), start=1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        message = record.get("message", {}) if isinstance(record, dict) else {}
        content = message.get("content") if isinstance(message, dict) else None
        text = _content_text(content)
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                kind = block.get("type")
                if kind == "tool_use":
                    name = str(block.get("name", ""))
                    events.append({"event_id": _id("tool", f"{query_id}:{line_number}:{name}"), "event_type": "retrieval" if name == "wiki_search" else "tool_call", "query_id": query_id, "session_id": f"session-{query_id}", "user_id": user_id, "page_ids": [], "external": name != "wiki_search", "timestamp": "2026-08-03T12:00:01Z"})
                if kind == "tool_result":
                    try:
                        result = json.loads(str(block.get("content", "{}")))
                    except json.JSONDecodeError:
                        result = {}
                    for event in reversed(events):
                        if event.get("event_type") == "retrieval" and event.get("query_id") == query_id:
                            event["page_ids"] = [str(page) for page in result.get("page_ids", [])]
                            break
        if text and "stale" in text.casefold():
            events.append({"event_id": _id("feedback", f"{query_id}:{line_number}"), "event_type": "feedback", "kind": "stale", "query_id": query_id, "session_id": f"session-{query_id}", "user_id": user_id})
        if record.get("type") == "result":
            value = str(record.get("result", ""))
            events.append({"event_id": _id("outcome", query_id), "event_type": "outcome", "status": "failure" if value == "failed" else "success", "query_id": query_id, "session_id": f"session-{query_id}", "user_id": user_id})
    return events, malformed


def adapt_codex(raw: bytes, *, query_id: str, user_id: str) -> tuple[list[dict[str, Any]], int]:
    events: list[dict[str, Any]] = [_question(query_id, user_id, "How do I rotate the mantle key?")]
    malformed = 0
    for line_number, line in enumerate(raw.splitlines(), start=1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        payload = record.get("payload", {}) if isinstance(record, dict) else {}
        kind = payload.get("type") if isinstance(payload, dict) else None
        if kind == "user_message" and any(token in str(payload.get("message", "")).casefold() for token in ("stale", "wrong")):
            events.append({"event_id": _id("feedback", f"{query_id}:{line_number}"), "event_type": "feedback", "kind": "stale", "query_id": query_id, "session_id": f"session-{query_id}", "user_id": user_id})
        elif kind == "function_call":
            name = str(payload.get("name", ""))
            events.append({"event_id": _id("tool", f"{query_id}:{line_number}:{name}"), "event_type": "retrieval" if name == "wiki_search" else "tool_call", "query_id": query_id, "session_id": f"session-{query_id}", "user_id": user_id, "page_ids": [], "external": name != "wiki_search", "timestamp": "2026-08-03T12:00:01Z"})
        elif kind == "function_call_output":
            output = str(payload.get("output", ""))
            if "page_ids" in output:
                try:
                    result = json.loads(output)
                except json.JSONDecodeError:
                    result = {}
                for event in reversed(events):
                    if event.get("event_type") == "retrieval" and event.get("query_id") == query_id:
                        event["page_ids"] = [str(page) for page in result.get("page_ids", [])]
                        break
            if "stale" in output.casefold() or "wrong" in output.casefold():
                events.append({"event_id": _id("feedback", f"{query_id}:{line_number}"), "event_type": "feedback", "kind": "stale", "query_id": query_id, "session_id": f"session-{query_id}", "user_id": user_id})
            # ``exit code 0`` is a tool result, not the rollout's final outcome.
            # Treating both as the same event ID made replay order change the
            # winning status, which is precisely the kind of ingestion bug this
            # experiment is intended to expose.
            if output in {"failed", "all tests pass"}:
                events.append({"event_id": _id("outcome", query_id), "event_type": "outcome", "status": "failure" if output == "failed" else "success", "query_id": query_id, "session_id": f"session-{query_id}", "user_id": user_id})
    return events, malformed


def build_cohort() -> tuple[list[dict[str, Any]], dict[str, str], dict[str, Any]]:
    specs = [
        ("claude", "q-absent", "u-1", "absent", "absent_or_undiscoverable"),
        ("claude", "q-success", "u-2", "success", "control"),
        ("codex", "q-external", "u-3", "external", "missing_operational_knowledge"),
        ("codex", "q-stale", "u-4", "stale", "incorrect_or_stale"),
        ("codex", "q-unobserved", "u-5", "unobserved", "unobservable"),
        ("claude", "q-incomplete", "u-6", "incomplete", "incomplete_procedure"),
    ]
    events: list[dict[str, Any]] = []
    labels: dict[str, str] = {}
    source_stats: Counter[str] = Counter()
    for provider, query_id, user_id, mode, label in specs:
        raw = claude_rollout(query_id, user_id, "How do I rotate the mantle key?", mode=mode) if provider == "claude" else codex_rollout(query_id, user_id, "How do I rotate the mantle key?", mode=mode)
        raw += b"{malformed\n" if query_id == "q-absent" else b""
        adapted, malformed = adapt_claude(raw, query_id=query_id, user_id=user_id) if provider == "claude" else adapt_codex(raw, query_id=query_id, user_id=user_id)
        events.extend(adapted)
        labels[query_id] = label
        source_stats[f"{provider}_rollouts"] += 1
        source_stats["malformed_records"] += malformed
    return events, labels, {"source_stats": dict(source_stats), "spec_count": len(specs)}


def dedupe_latest(events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for event in events:
        latest[str(event["event_id"])] = event
    return sorted(latest.values(), key=lambda item: (str(item.get("query_id")), str(item.get("event_id"))))


def candidate_types(events: list[dict[str, Any]]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for candidate in mine_gap_candidates(events):
        for query_id in candidate.query_ids:
            result.setdefault(query_id, set()).add(candidate.gap_type)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replays", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.replays < 1:
        raise SystemExit("--replays must be positive")
    started = time.perf_counter()
    events, labels, source = build_cohort()
    rng = random.Random(44017)
    replayed = list(events) * args.replays
    rng.shuffle(replayed)
    deduped = dedupe_latest(replayed)
    full_candidates = candidate_types(deduped)
    observed = {query_id: types for query_id, types in full_candidates.items()}
    expected_positive = {query_id: label for query_id, label in labels.items() if label not in {"control", "unobservable"}}
    true_positive = sum(label in observed.get(query_id, set()) for query_id, label in expected_positive.items())
    false_positive = sum(bool(observed.get(query_id)) for query_id, label in labels.items() if label in {"control", "unobservable"})

    no_retrieval = [event for event in deduped if event.get("event_type") != "retrieval"]
    no_outcome_feedback = [event for event in deduped if event.get("event_type") not in {"outcome", "feedback"}]
    ablation = {
        "without_retrieval_events": {"candidate_count": len(mine_gap_candidates(no_retrieval))},
        "without_outcome_feedback_events": {"candidate_types": {key: sorted(value) for key, value in candidate_types(no_outcome_feedback).items()}},
    }
    receipt = {
        "schema_version": SCHEMA_VERSION,
        "cohort": source,
        "raw_canonical_event_count": len(events),
        "replay_batches": args.replays,
        "delivered_event_count": len(replayed),
        "deduped_event_count": len(deduped),
        "duplicate_delivery_count": len(replayed) - len(deduped),
        "out_of_order_delivery": True,
        "replay_safe": deduped == dedupe_latest(events),
        "candidate_types_by_query": {key: sorted(value) for key, value in observed.items()},
        "expected_positive_queries": sorted(expected_positive),
        "true_positive_queries": true_positive,
        "false_positive_query_count": false_positive,
        "positive_recall": true_positive / len(expected_positive) if expected_positive else 1.0,
        "ablation": ablation,
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "interpretation": "Native-shaped Claude/Codex records retain enough evidence for deterministic gap mining only when wiki retrieval, tool fallback, and outcome/feedback events are emitted. Replay deduplication is required before ClickHouse projection; MergeTree append alone is not idempotent.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
