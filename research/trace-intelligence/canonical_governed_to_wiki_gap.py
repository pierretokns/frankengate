#!/usr/bin/env python3
"""Adapt Frankengate canonical governed fixtures to the wiki-gap schema.

The adapter is intentionally conservative: a ``user_request`` is not treated
as a wiki search.  If a trace contains no explicit wiki-search/retrieval event,
the receipt reports an observability gap instead of falsely claiming that the
wiki is missing knowledge.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from wiki_gap_miner import mine_gap_candidates


WIKI_EVENT_KINDS = frozenset({"wiki_search", "wiki_retrieval", "retrieval", "knowledge_search"})


def adapt_trace(trace: dict[str, Any]) -> tuple[list[dict[str, Any]], bool]:
    trace_id = str(trace.get("trace_id", "unknown"))
    task_id = str(trace.get("task", {}).get("task_id", trace_id))
    query_id = f"{trace_id}:{task_id}"
    adapted: list[dict[str, Any]] = []
    wiki_observed = False
    for source_event in trace.get("events", []):
        if not isinstance(source_event, dict):
            continue
        kind = str(source_event.get("kind", ""))
        event_id = str(source_event.get("event_id", f"{trace_id}:{len(adapted)}"))
        content = source_event.get("content")
        if kind == "user_request" and isinstance(content, str) and content.strip():
            adapted.append(
                {
                    "event_id": event_id,
                    "event_type": "question",
                    "query_id": query_id,
                    "session_id": trace_id,
                    "user_id": str(source_event.get("subject_id", "governed-fixture-user")),
                    "text": content,
                    "timestamp": source_event.get("timestamp"),
                }
            )
        elif kind in WIKI_EVENT_KINDS:
            wiki_observed = True
            page_ids = source_event.get("page_ids")
            adapted.append(
                {
                    "event_id": event_id,
                    "event_type": "retrieval",
                    "query_id": query_id,
                    "session_id": trace_id,
                    "user_id": "governed-fixture-user",
                    "page_ids": page_ids if isinstance(page_ids, list) else [],
                    "wiki_search_attempted": True,
                    "timestamp": source_event.get("timestamp"),
                }
            )
        elif kind == "tool_call_proposal":
            adapted.append(
                {
                    "event_id": event_id,
                    "event_type": "tool_call",
                    "query_id": query_id,
                    "session_id": trace_id,
                    "user_id": "governed-fixture-user",
                    "external": False,
                    "timestamp": source_event.get("timestamp"),
                }
            )
    outcome = trace.get("outcome")
    if isinstance(outcome, dict):
        value = str(outcome.get("value", "")).casefold()
        adapted.append(
            {
                "event_id": f"{trace_id}:outcome",
                "event_type": "outcome",
                "query_id": query_id,
                "session_id": trace_id,
                "user_id": "governed-fixture-user",
                "status": "failure" if any(token in value for token in ("failed", "denied", "cancelled", "rollback")) else "success",
            }
        )
    return adapted, wiki_observed


def mine_directory(root: Path) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    traces = wiki_traces = 0
    for path in sorted(root.glob("*.json")):
        trace = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(trace, dict):
            continue
        trace_events, wiki_observed = adapt_trace(trace)
        events.extend(trace_events)
        traces += 1
        wiki_traces += int(wiki_observed)
    candidates = mine_gap_candidates(events)
    question_count = sum(1 for event in events if event.get("event_type") == "question")
    return {
        "schema_version": "frankengate-governed-wiki-gap-observation-v1",
        "trace_count": traces,
        "question_count": question_count,
        "wiki_observed_trace_count": wiki_traces,
        "wiki_observation_coverage": (wiki_traces / traces) if traces else 0.0,
        "candidate_count": len(candidates),
        "candidates": [candidate.as_dict() for candidate in candidates],
        "interpretation": (
            "No wiki gap claims are admissible until wiki retrieval/search events are emitted."
            if wiki_traces == 0
            else "Candidates are eligible for review; inspect evidence and replay before publishing wiki changes."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = mine_directory(args.fixture_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
