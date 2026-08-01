from __future__ import annotations

import json

from artifact_subplan_changed_system_replay import run


def test_semantic_subplan_rejects_drift_while_name_only_accepts(tmp_path):
    receipt = tmp_path / "receipt.json"
    result = run(receipt)
    assert result["aggregate"]["name_only_subplan"]["accepted"] == 5
    assert result["aggregate"]["semantic_subplan"]["accepted"] == 3
    assert result["aggregate"]["name_only_subplan"]["unsafe_accept"] == 2
    assert result["aggregate"]["semantic_subplan"]["unsafe_accept"] == 0
    assert json.loads(receipt.read_text())["schema"] == "frankengate-artifact-subplan-changed-system-v1"
