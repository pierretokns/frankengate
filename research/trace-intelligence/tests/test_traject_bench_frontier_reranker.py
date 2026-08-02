import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from traject_bench_frontier_reranker import metrics, select_cases  # noqa: E402


def test_metrics_respect_target_set_and_rank() -> None:
    candidates = [{"tool name": "a"}, {"tool name": "b"}, {"tool name": "c"}]
    row = {"tool list": [{"tool name": "b"}]}
    result = metrics(row, candidates, [1, 0, 2])
    assert result["mrr"] == 1.0
    assert result["recall_at_1"] == 1.0


def test_case_selection_rejects_missing_target_manifest(tmp_path: Path) -> None:
    root = tmp_path / "public_data"
    (root / "parallel" / "Demo").mkdir(parents=True)
    (root / "tools").mkdir()
    (root / "tools" / "Demo_tool.json").write_text(json.dumps([{"tool name": "known", "tool description": ""}]), encoding="utf-8")
    (root / "parallel" / "Demo" / "hard_ver.json").write_text(json.dumps([{"query": "q", "tool list": [{"tool name": "unknown"}]}]), encoding="utf-8")
    assert select_cases(root, 5) == []
