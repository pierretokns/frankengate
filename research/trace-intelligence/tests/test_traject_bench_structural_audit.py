import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from traject_bench_structural_audit import audit


def test_audit_counts_parallel_and_sequential_structure(tmp_path: Path) -> None:
    parallel = tmp_path / "parallel" / "Finance"
    sequential = tmp_path / "sequential" / "Finance"
    parallel.mkdir(parents=True)
    sequential.mkdir(parents=True)
    parallel_rows = [
        {
            "query": "q",
            "trajectory_type": "parallel",
            "tool count": 2,
            "tool list": [
                {"tool name": "a", "required parameters": [{"name": "x", "value": "1"}], "executed_output": "ok"},
                {"tool name": "b", "required parameters": [{"name": "y", "value": ""}], "executed_output": "ok"},
            ],
        }
    ]
    sequential_rows = [
        {
            "query": "q2",
            "trajectory_type": "sequential",
            "num_tools_used": 1,
            "num_successful_tools": 1,
            "executable": True,
            "connected tools": ["a"],
            "tool list": [{"tool name": "a", "required parameters": [], "executed_output": "ok"}],
        }
    ]
    (parallel / "simple_ver.json").write_text(json.dumps(parallel_rows), encoding="utf-8")
    (sequential / "traj_query.json").write_text(json.dumps(sequential_rows), encoding="utf-8")
    result = audit(tmp_path)
    assert result["records"] == 2
    assert result["parallel_records"] == 1
    assert result["sequential_records"] == 1
    assert result["tool_invocations_described"] == 3
    assert result["tools_with_nonempty_executed_output"] == 3
    assert result["parameter_values_present"] == 1
    assert result["parameter_values_total"] == 2
    assert result["tool_count_mismatches"] == 0
    assert result["successful_tool_count_mismatches"] == 0


def test_audit_marks_benchmark_claim_boundary(tmp_path: Path) -> None:
    directory = tmp_path / "parallel" / "Weather"
    directory.mkdir(parents=True)
    (directory / "hard_ver.json").write_text(json.dumps([{"tool list": [], "query": "q"}]), encoding="utf-8")
    result = audit(tmp_path)
    assert result["claim_boundary"]["model_quality_measured"] is False
    assert result["claim_boundary"]["enterprise_user_behavior_measured"] is False
