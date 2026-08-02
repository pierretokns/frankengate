import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from trace_commons_feature_ablation import evaluate, project_proxy, tokens  # noqa: E402


def test_project_proxy_removes_home_prefix() -> None:
    assert project_proxy("/Users/anon/ComparIA") == "comparia"
    assert project_proxy("C:/Users/anon/BentoFolio") == "bentofolio"


def test_tokens_preserve_identifiers_and_remove_stopwords() -> None:
    assert tokens("Please update SQLModel v2.0") == ["update", "sqlmodel", "v2.0"]


def test_feature_evaluate_has_bounded_proxy_metrics() -> None:
    sessions = [
        {"label": "a", "events": {"user": 1}, "prompt": {"alpha": 2}, "identifier": {"db_a": 1}},
        {"label": "a", "events": {"user": 1}, "prompt": {"alpha": 2}, "identifier": {"db_a": 1}},
        {"label": "b", "events": {"tool": 1}, "prompt": {"beta": 2}, "identifier": {"db_b": 1}},
    ]
    result = evaluate(sessions, "combined", mask_labels=False)
    assert result["evaluated_sessions"] == 2
    assert 0 <= result["top1_rate"] <= 1
    assert 0 <= result["same_project_mrr"] <= 1
