import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rollout_ingestion_experiment import (
    build_cohort,
    candidate_types,
    dedupe_latest,
)
from wiki_gap_miner import mine_gap_candidates


def test_native_shaped_cohort_is_replay_safe_and_retains_positive_queries():
    events, labels, _ = build_cohort()
    delivered = list(events) * 7
    deduped = dedupe_latest(delivered)
    assert len(delivered) > len(deduped)
    assert deduped == dedupe_latest(events)
    observed = candidate_types(deduped)
    for query_id in ("q-absent", "q-external", "q-incomplete", "q-stale"):
        assert labels[query_id] in observed.get(query_id, set())
    assert not observed.get("q-success")
    assert not observed.get("q-unobserved")


def test_missing_retrieval_observation_fails_closed():
    events, _, _ = build_cohort()
    without_retrieval = [event for event in events if event.get("event_type") != "retrieval"]
    assert mine_gap_candidates(without_retrieval) == []


def test_equal_key_candidates_keep_all_query_lineage():
    events, _, _ = build_cohort()
    candidates = mine_gap_candidates(events)
    incomplete = next(candidate for candidate in candidates if candidate.gap_type == "incomplete_procedure")
    assert {"q-absent", "q-incomplete"}.issubset(incomplete.query_ids)
