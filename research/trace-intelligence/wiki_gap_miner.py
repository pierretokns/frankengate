#!/usr/bin/env python3
"""Mine likely wiki knowledge gaps from canonical trace events.

This is deliberately a deterministic first pass.  It does not ask a model to
guess a missing page from one failed query.  It turns observable evidence into
reviewable candidates, which can later be adjudicated by a frontier model or a
human and then verified by replaying the original task.

Canonical event JSONL (one object per line)::

    {"event_id":"e1", "event_type":"question", "query_id":"q1",
     "session_id":"s1", "user_id":"u1", "timestamp":"2026-01-01T00:00:00Z",
     "text":"How do I rotate the mantle key?"}
    {"event_id":"e2", "event_type":"retrieval", "query_id":"q1",
     "page_ids":[], "timestamp":"..."}
    {"event_id":"e3", "event_type":"tool_call", "query_id":"q1",
     "tool":"aws_cli", "external":true, "timestamp":"..."}
    {"event_id":"e4", "event_type":"outcome", "query_id":"q1",
     "status":"failure", "timestamp":"..."}

Wiki JSONL contains versioned pages with ``page_id``, ``title``,
``updated_at`` and optional ``aliases``/``system`` fields.

The output is content-bearing by design for a local, governed review queue:
every candidate includes the triggering query text and evidence event IDs.
Callers should apply their own authorization and retention policy before
persisting or sharing it.
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import datetime as dt
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = "frankengate-wiki-gap-candidates-v1"
TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_./:-]{1,}", re.IGNORECASE)
STOPWORDS = frozenset(
    "a an and are be can do does for how i in is it me of on or the to what when where why with".split()
)


@dataclasses.dataclass(frozen=True)
class WikiPage:
    page_id: str
    title: str
    updated_at: dt.datetime | None
    aliases: tuple[str, ...] = ()
    system: str | None = None


@dataclasses.dataclass(frozen=True)
class GapCandidate:
    gap_type: str
    key: str
    score: float
    demand_count: int
    session_count: int
    user_count: int
    query_texts: tuple[str, ...]
    evidence_event_ids: tuple[str, ...]
    page_ids: tuple[str, ...]
    explanation: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "gap_type": self.gap_type,
            "key": self.key,
            "score": round(self.score, 6),
            "demand_count": self.demand_count,
            "session_count": self.session_count,
            "user_count": self.user_count,
            "query_texts": list(self.query_texts),
            "evidence_event_ids": list(self.evidence_event_ids),
            "page_ids": list(self.page_ids),
            "explanation": self.explanation,
        }


def parse_time(value: Any) -> dt.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def tokens(text: str) -> frozenset[str]:
    return frozenset(
        token.casefold()
        for token in TOKEN_RE.findall(text)
        if token.casefold() not in STOPWORDS
    )


def normalized_key(text: str) -> str:
    values = sorted(tokens(text))
    return " ".join(values) or hashlib.sha256(text.encode()).hexdigest()[:12]


def jaccard(left: str, right: str) -> float:
    a, b = tokens(left), tokens(right)
    return len(a & b) / len(a | b) if a and b else 0.0


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _page_ids(event: Mapping[str, Any]) -> tuple[str, ...]:
    values = event.get("page_ids")
    if isinstance(values, list):
        return tuple(str(value) for value in values if value is not None)
    value = event.get("page_id")
    return (str(value),) if value is not None else ()


def _candidate(
    gap_type: str,
    key: str,
    score: float,
    questions: Sequence[Mapping[str, Any]],
    evidence: Iterable[str],
    pages: Iterable[str],
    explanation: str,
) -> GapCandidate:
    return GapCandidate(
        gap_type=gap_type,
        key=key,
        score=max(0.0, min(1.0, score)),
        demand_count=len(questions),
        session_count=len({str(q.get("session_id", "")) for q in questions}),
        user_count=len({str(q.get("user_id", "")) for q in questions}),
        query_texts=tuple(
            str(q.get("text", "")).strip()
            for q in questions
            if str(q.get("text", "")).strip()
        ),
        evidence_event_ids=tuple(dict.fromkeys(str(value) for value in evidence)),
        page_ids=tuple(dict.fromkeys(str(value) for value in pages)),
        explanation=explanation,
    )


def mine_gap_candidates(
    events: Sequence[Mapping[str, Any]],
    pages: Sequence[WikiPage] = (),
    *,
    now: dt.datetime | None = None,
    stale_after_days: int = 180,
    rephrase_threshold: float = 0.45,
) -> list[GapCandidate]:
    """Return deterministic, evidence-backed gap candidates.

    The detector intentionally errs toward review candidates.  It distinguishes
    absent/undiscoverable evidence from stale, incomplete, and operational gaps
    instead of treating every zero-result search as a missing article.
    """

    now = (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
    page_by_id = {page.page_id: page for page in pages}
    by_query: dict[str, list[Mapping[str, Any]]] = collections.defaultdict(list)
    questions: list[Mapping[str, Any]] = []
    for event in events:
        query_id = event.get("query_id")
        if query_id is not None:
            by_query[str(query_id)].append(event)
        if event.get("event_type") in {"question", "user_message"}:
            if isinstance(event.get("text"), str) and event["text"].strip():
                questions.append(event)

    candidates: list[GapCandidate] = []
    for query_id, query_events in by_query.items():
        query_questions = [
            question
            for question in questions
            if str(question.get("query_id")) == query_id
        ]
        if not query_questions:
            continue
        question = query_questions[0]
        query_text = str(question["text"])
        retrievals = [event for event in query_events if event.get("event_type") == "retrieval"]
        retrieved_pages = tuple(
            dict.fromkeys(page_id for event in retrievals for page_id in _page_ids(event))
        )
        answer_events = [event for event in query_events if event.get("event_type") == "answer"]
        feedback = [event for event in query_events if event.get("event_type") == "feedback"]
        tool_calls = [event for event in query_events if event.get("event_type") == "tool_call"]
        outcomes = [event for event in query_events if event.get("event_type") == "outcome"]
        evidence = [str(event.get("event_id")) for event in query_events if event.get("event_id")]

        no_evidence = not retrieved_pages or any(
            event.get("answerable") is False
            or (isinstance(event.get("confidence"), (int, float)) and event["confidence"] < 0.4)
            for event in answer_events
        )
        if no_evidence:
            score = 0.55 + (0.15 if not retrieved_pages else 0.0)
            candidates.append(
                _candidate(
                    "absent_or_undiscoverable",
                    normalized_key(query_text),
                    score,
                    query_questions,
                    evidence,
                    retrieved_pages,
                    "The question produced no sufficiently useful wiki evidence; distinguish missing content from vocabulary mismatch during review.",
                )
            )

        if any(event.get("external") is True for event in tool_calls) and no_evidence:
            candidates.append(
                _candidate(
                    "missing_operational_knowledge",
                    normalized_key(query_text),
                    0.78,
                    query_questions,
                    evidence,
                    retrieved_pages,
                    "An external tool was needed after wiki evidence failed, indicating a likely missing operational procedure or runbook.",
                )
            )

        if any(str(event.get("kind", "")).casefold() in {"correction", "wrong", "stale"} for event in feedback):
            candidates.append(
                _candidate(
                    "incorrect_or_stale",
                    normalized_key(query_text),
                    0.84,
                    query_questions,
                    evidence,
                    retrieved_pages,
                    "A user corrected or rejected the evidence-backed answer; verify page freshness, scope, and contradictions.",
                )
            )

        if any(str(event.get("status", "")).casefold() in {"failure", "failed", "rollback"} for event in outcomes):
            candidates.append(
                _candidate(
                    "incomplete_procedure",
                    normalized_key(query_text),
                    0.72,
                    query_questions,
                    evidence,
                    retrieved_pages,
                    "The task outcome failed or rolled back; inspect whether the wiki omitted prerequisites, failure handling, or scope constraints.",
                )
            )

        if retrieved_pages:
            event_time = next(
                (
                    parsed
                    for event in query_events
                    if (parsed := parse_time(event.get("timestamp"))) is not None
                ),
                now,
            )
            stale_pages = [
                page_id
                for page_id in retrieved_pages
                if page_id in page_by_id
                and page_by_id[page_id].updated_at is not None
                and event_time is not None
                and (event_time - page_by_id[page_id].updated_at).days >= stale_after_days
            ]
            if stale_pages and (feedback or outcomes):
                candidates.append(
                    _candidate(
                        "stale_documentation",
                        "|".join(sorted(stale_pages)),
                        0.68,
                        query_questions,
                        evidence,
                        stale_pages,
                        "The task touched documentation older than the configured freshness window and also produced correction or outcome signals.",
                    )
                )

    # Cluster semantically close questions across sessions/users.  This turns
    # individual weak signals into an enterprise demand signal without needing
    # embeddings or a model in the first pass.
    clusters: list[list[Mapping[str, Any]]] = []
    for question in questions:
        for cluster in clusters:
            if jaccard(str(question["text"]), str(cluster[0]["text"])) >= rephrase_threshold:
                cluster.append(question)
                break
        else:
            clusters.append([question])
    for cluster in clusters:
        if len(cluster) < 2 or len({str(q.get("user_id", "")) for q in cluster}) < 2:
            continue
        evidence = [
            str(event.get("event_id"))
            for event in events
            if event.get("query_id") is not None
            and any(str(event.get("query_id")) == str(q.get("query_id")) for q in cluster)
            and event.get("event_id")
        ]
        pages_seen = [
            page_id
            for event in events
            if event.get("event_type") == "retrieval"
            and any(str(event.get("query_id")) == str(q.get("query_id")) for q in cluster)
            for page_id in _page_ids(event)
        ]
        demand = min(1.0, 0.45 + 0.1 * len(cluster) + 0.15 * len({str(q.get("user_id", "")) for q in cluster}))
        candidates.append(
            _candidate(
                "recurring_enterprise_demand",
                normalized_key(str(cluster[0]["text"])),
                demand,
                cluster,
                evidence,
                pages_seen,
                "Close paraphrases recur across users; review whether one canonical wiki concept, alias, or cross-system page is missing.",
            )
        )

    # Keep the strongest evidence for each type/key pair and rank for review.
    best: dict[tuple[str, str], GapCandidate] = {}
    for candidate in candidates:
        identity = (candidate.gap_type, candidate.key)
        previous = best.get(identity)
        if previous is None or candidate.score > previous.score:
            best[identity] = candidate
    return sorted(best.values(), key=lambda item: (-item.score, item.gap_type, item.key))


def load_pages(path: Path) -> list[WikiPage]:
    pages: list[WikiPage] = []
    for row in read_jsonl(path):
        page_id = row.get("page_id")
        title = row.get("title")
        if not isinstance(page_id, str) or not isinstance(title, str):
            continue
        aliases = row.get("aliases")
        pages.append(
            WikiPage(
                page_id=page_id,
                title=title,
                updated_at=parse_time(row.get("updated_at")),
                aliases=tuple(str(value) for value in aliases) if isinstance(aliases, list) else (),
                system=str(row["system"]) if row.get("system") is not None else None,
            )
        )
    return pages


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events-jsonl", type=Path, required=True)
    parser.add_argument("--wiki-jsonl", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--now", type=str)
    parser.add_argument("--stale-after-days", type=int, default=180)
    args = parser.parse_args()
    now = parse_time(args.now) if args.now else None
    candidates = mine_gap_candidates(
        read_jsonl(args.events_jsonl),
        load_pages(args.wiki_jsonl),
        now=now,
        stale_after_days=args.stale_after_days,
    )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "candidate_count": len(candidates),
        "candidates": [candidate.as_dict() for candidate in candidates],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
