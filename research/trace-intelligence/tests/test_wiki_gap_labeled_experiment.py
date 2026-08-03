import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wiki_gap_labeled_experiment import build_cohort, evaluate


def test_labeled_cohort_is_deterministic():
    first = build_cohort(3)
    second = build_cohort(3)
    assert first == second
    assert len(first[2]) == 29


def test_detector_has_zero_false_positives_on_controls():
    events, pages, gold = build_cohort(10)
    result = evaluate(events, pages, gold)
    assert result["false_positive_count"] == 0
    assert result["category_recall"]["success_control"] == 0.0
    assert result["category_recall"]["no_wiki_observation"] == 0.0
    assert result["category_recall"]["out_of_scope"] == 0.0


def test_detector_catches_positive_gap_strata():
    events, pages, gold = build_cohort(10)
    result = evaluate(events, pages, gold)
    for stratum in ("absent", "discoverability", "external_fallback", "incomplete", "stale", "contradiction"):
        assert result["category_recall"][stratum] == 1.0
