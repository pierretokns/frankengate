import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wiki_gap_miner import WikiPage, mine_gap_candidates


def event(event_id, event_type, query_id, **values):
    return {
        "event_id": event_id,
        "event_type": event_type,
        "query_id": query_id,
        "session_id": query_id,
        "user_id": query_id,
        "timestamp": "2026-08-03T00:00:00Z",
        **values,
    }


def test_provider_failure_after_good_wiki_evidence_is_not_a_wiki_gap():
    rows = [
        event("q", "question", "q", text="Where is the deployment runbook?"),
        event("r", "retrieval", "q", page_ids=["runbook"]),
        event("a", "answer", "q", answerable=True, confidence=0.95),
        event("o", "outcome", "q", status="failure", failure_domain="provider"),
    ]
    assert mine_gap_candidates(rows, [WikiPage("runbook", "Runbook", None)]) == []


def test_stale_age_without_failure_or_correction_is_not_a_gap():
    rows = [
        event("q", "question", "q", text="Where is the old runbook?"),
        event("r", "retrieval", "q", page_ids=["old"]),
        event("a", "answer", "q", answerable=True, confidence=0.95),
        event("o", "outcome", "q", status="success"),
    ]
    pages = [WikiPage("old", "Old runbook", dt.datetime(2024, 1, 1, tzinfo=dt.timezone.utc))]
    assert mine_gap_candidates(rows, pages) == []


def test_successful_repeated_demand_is_not_promoted_as_a_gap():
    rows = [
        event("q1", "question", "q1", text="Where is the current runbook?", user_id="u1"),
        event("r1", "retrieval", "q1", page_ids=["runbook"]),
        event("a1", "answer", "q1", answerable=True, confidence=0.95),
        event("o1", "outcome", "q1", status="success"),
        event("q2", "question", "q2", text="Where is the current runbook?", user_id="u2"),
        event("r2", "retrieval", "q2", page_ids=["runbook"]),
        event("a2", "answer", "q2", answerable=True, confidence=0.95),
        event("o2", "outcome", "q2", status="success"),
    ]
    assert mine_gap_candidates(rows, [WikiPage("runbook", "Runbook", None)]) == []
