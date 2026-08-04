import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from replit_claims_factorial import (
    baseline_metrics,
    build_factorial_cohort,
    query_records,
    run_arm,
)


def test_deterministic_baseline_remains_authoritative_with_collision_controls():
    events, pages, gold = build_factorial_cohort(2, 2)
    result = baseline_metrics(events, pages, gold)
    assert result["precision"] == 1.0
    assert result["recall"] == 1.0
    assert result["false_positive_count"] == 0


def test_typed_facets_improve_issue_cluster_coverage_without_raw_text_leakage():
    events, _, gold = build_factorial_cohort(4, 4)
    records = query_records(events, gold)
    raw = run_arm(records, arm="raw_lexical")
    typed = run_arm(records, arm="facet_typed_lexical", typed_weight=2.0)
    assert typed["positive_coverage"] >= raw["positive_coverage"]
    assert typed["control_contamination_rate"] <= raw["control_contamination_rate"]
    assert typed["lineage_query_count"] >= typed["eval_candidate_count"]
