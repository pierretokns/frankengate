import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wiki_hard_negative_audit import rank_of


def test_rank_of_returns_one_based_position_or_none() -> None:
    assert rank_of(["a", "b"], {"b"}) == 2
    assert rank_of(["a"], {"b"}) is None
