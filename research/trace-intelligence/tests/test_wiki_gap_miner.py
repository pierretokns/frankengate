import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wiki_gap_miner import WikiPage, mine_gap_candidates


NOW = dt.datetime(2026, 8, 3, tzinfo=dt.timezone.utc)


def event(event_id, event_type, query_id, **values):
    return {
        "event_id": event_id,
        "event_type": event_type,
        "query_id": query_id,
        "session_id": values.pop("session_id", query_id),
        "user_id": values.pop("user_id", query_id),
        "timestamp": values.pop("timestamp", "2026-08-03T00:00:00Z"),
        **values,
    }


def test_detects_absence_external_fallback_and_failed_outcome():
    rows = [
        event("q1", "question", "q1", text="How do I rotate the mantle key?", user_id="u1"),
        event("r1", "retrieval", "q1", page_ids=[]),
        event("t1", "tool_call", "q1", tool="aws", external=True),
        event("o1", "outcome", "q1", status="failure"),
    ]
    candidates = mine_gap_candidates(rows, now=NOW)
    kinds = {candidate.gap_type for candidate in candidates}
    assert "absent_or_undiscoverable" in kinds
    assert "missing_operational_knowledge" in kinds
    assert "incomplete_procedure" in kinds
    assert all(candidate.evidence_event_ids for candidate in candidates)


def test_distinguishes_correction_and_stale_page():
    rows = [
        event("q1", "question", "q1", text="How do I rotate the mantle key?", user_id="u1"),
        event("r1", "retrieval", "q1", page_ids=["mantle"], timestamp="2026-08-03T00:00:00Z"),
        event("f1", "feedback", "q1", kind="correction"),
        event("o1", "outcome", "q1", status="failure"),
    ]
    pages = [
        WikiPage(
            page_id="mantle",
            title="Mantle",
            updated_at=dt.datetime(2025, 1, 1, tzinfo=dt.timezone.utc),
        )
    ]
    candidates = mine_gap_candidates(rows, pages, now=NOW, stale_after_days=180)
    kinds = {candidate.gap_type for candidate in candidates}
    assert "incorrect_or_stale" in kinds
    assert "stale_documentation" in kinds
    assert "incomplete_procedure" in kinds


def test_finds_cross_user_recurring_demand_without_embeddings():
    rows = [
        event("q1", "question", "q1", text="How do I rotate the mantle key?", user_id="u1", session_id="s1"),
        event("r1", "retrieval", "q1", page_ids=[]),
        event("q2", "question", "q2", text="What is the process to rotate a mantle key?", user_id="u2", session_id="s2"),
        event("r2", "retrieval", "q2", page_ids=[]),
    ]
    candidates = mine_gap_candidates(rows, now=NOW)
    recurring = [candidate for candidate in candidates if candidate.gap_type == "recurring_enterprise_demand"]
    assert recurring
    assert recurring[0].user_count == 2
    assert recurring[0].demand_count == 2


def test_does_not_promote_one_successful_lookup_to_a_gap():
    rows = [
        event("q1", "question", "q1", text="Where is the deployment runbook?", user_id="u1"),
        event("r1", "retrieval", "q1", page_ids=["deploy"]),
        event("a1", "answer", "q1", answerable=True, confidence=0.95),
        event("o1", "outcome", "q1", status="success"),
    ]
    candidates = mine_gap_candidates(rows, now=NOW)
    assert candidates == []
