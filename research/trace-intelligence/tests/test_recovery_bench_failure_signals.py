from __future__ import annotations

import json

from recovery_bench_failure_signals import summarize_trajectory


def test_failure_signal_summary_is_structural_and_deterministic(tmp_path):
    path = tmp_path / "trajectory.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "ATIF-v1.6",
                "steps": [
                    {"source": "user", "message": "task"},
                    {
                        "source": "agent",
                        "tool_calls": [{"function_name": "bash_command"}],
                        "observation": {"content": "Permission denied: no such file"},
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    first = summarize_trajectory(path)
    second = summarize_trajectory(path)
    assert first == second
    assert first["tool_families"] == {"shell": 1}
    assert first["signal_counts"]["permission"] == 1
    assert first["signal_counts"]["missing_resource"] == 1
    assert "Permission denied" not in json.dumps(first)
