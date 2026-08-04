import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from traject_bench_toolqp_peak_rank import peak_rank  # noqa: E402


def test_peak_rank_prefers_best_turn_rank() -> None:
    candidates = [{"tool name": "alpha"}, {"tool name": "beta"}, {"tool name": "gamma"}]
    order = peak_rank(["beta", "gamma"], candidates, top_k=1)
    assert order[:2] == [1, 2]
