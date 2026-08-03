import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from canonical_governed_to_wiki_gap import adapt_trace, mine_directory


def test_user_request_without_wiki_event_is_not_a_false_gap():
    events, wiki_observed = adapt_trace(
        {
            "trace_id": "t1",
            "task": {"task_id": "task"},
            "events": [{"event_id": "e1", "kind": "user_request", "content": "Where is the runbook?"}],
            "outcome": {"value": "succeeded"},
        }
    )
    assert wiki_observed is False
    assert [event["event_type"] for event in events] == ["question", "outcome"]


def test_governed_fixture_cohort_reports_missing_wiki_observability():
    result = mine_directory(Path(__file__).resolve().parents[1] / "fixtures" / "governed-v1")
    assert result["trace_count"] == 12
    assert result["question_count"] == 4
    assert result["wiki_observed_trace_count"] == 0
    assert result["wiki_observation_coverage"] == 0.0
    assert result["candidate_count"] == 0
    assert "No wiki gap claims" in result["interpretation"]
