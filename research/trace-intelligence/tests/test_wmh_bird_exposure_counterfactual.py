from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wmh_bird_exposure_counterfactual import lexical_score, rank_metrics, sql_tables, substitute_table  # noqa: E402


def test_sql_tables_and_substitution() -> None:
    sql = "SELECT a.id FROM alpha AS a JOIN beta b ON a.id = b.id"
    assert sql_tables(sql) == {"alpha", "beta"}
    rewritten = substitute_table(sql, "beta", "gamma")
    assert "gamma" in rewritten.lower()
    assert "beta" not in rewritten.lower()


def test_rank_metrics_uses_first_target() -> None:
    metrics = rank_metrics(["noise", "target", "other"], frozenset({"target"}))
    assert metrics == {"mrr": 0.5, "recall_at_1": 0.0, "recall_at_5": 1.0, "recall_at_10": 1.0}


def test_lexical_score_preserves_identifier_signal() -> None:
    assert lexical_score("show customer totals", "customer_totals") > lexical_score("show customer totals", "accounts")
