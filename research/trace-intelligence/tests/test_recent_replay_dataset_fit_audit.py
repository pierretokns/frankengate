from __future__ import annotations

import json

from recent_replay_dataset_fit_audit import audit_recovery


def test_recovery_audit_excludes_aggregate_and_distinguishes_initial_runs(tmp_path):
    run = tmp_path / "runs" / "initial-model"
    trial = run / "task__trial"
    (trial / "verifier").mkdir(parents=True)
    (trial / "config.json").write_text("{}", encoding="utf-8")
    (trial / "result.json").write_text(
        json.dumps(
            {
                "task_name": "task",
                "agent_info": {"name": "agent", "model_info": {"name": "model"}},
                "config": {"environment": {"type": "local"}},
            }
        ),
        encoding="utf-8",
    )
    (trial / "agent").mkdir()
    (trial / "agent" / "trajectory.json").write_text(
        json.dumps({"schema_version": "ATIF-v1.6", "steps": []}), encoding="utf-8"
    )
    (trial / "verifier" / "reward.txt").write_text("0\n", encoding="utf-8")
    (run / "result.json").write_text(json.dumps({"stats": {}}), encoding="utf-8")

    result = audit_recovery(tmp_path)
    assert result["result_files"] == 1
    assert result["trajectory_files"] == 1
    assert result["initial_result_files"] == 1
    assert result["recovery_result_files"] == 0
    assert result["initial_failure_count"] == 1
