from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wmh_bird_replay_negative_reranker import feature_vector  # noqa: E402
from wmh_bird_exposure_counterfactual import Trace  # noqa: E402


def test_feature_vector_is_deterministic() -> None:
    trace = Trace("hash", "task", "db", "show customer totals", "SELECT * FROM customer", 1.0, frozenset({"customer"}), frozenset({"customer"}))
    first = feature_vector(trace, "customer", {})
    second = feature_vector(trace, "customer", {})
    assert first == second
    assert first[0] > 0

