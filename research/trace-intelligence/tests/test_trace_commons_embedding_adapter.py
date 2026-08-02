import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from trace_commons_embedding_adapter import adapter_weights, apply_adapter  # noqa: E402


def test_adapter_weights_are_bounded_and_favor_same_group_terms() -> None:
    docs = [{"prompt:alpha": 1}, {"prompt:alpha": 1}, {"prompt:beta": 1}]
    weights = adapter_weights(docs, ["a", "a", "b"])
    assert weights["prompt:alpha"] > 0
    assert -2 <= weights["prompt:alpha"] <= 2


def test_apply_adapter_preserves_keys() -> None:
    vector = {"prompt:alpha": 1.0, "prompt:beta": 2.0}
    adapted = apply_adapter(vector, {"prompt:alpha": 1.0})
    assert set(adapted) == set(vector)
    assert adapted["prompt:alpha"] > vector["prompt:alpha"]
    assert adapted["prompt:beta"] == vector["prompt:beta"]
