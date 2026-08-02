from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from verify_wmh_bird_step_fault_audit import verify  # noqa: E402


def test_verify_step_fault_receipt(tmp_path) -> None:
    result = {"schema_version": "frankengate-wmh-bird-step-fault-audit-v1", "aggregate": {"traces": 1, "reward_0": 0, "reward_1": 1, "sql_traces": 1, "sql_steps": 1}, "rows": [{"trace_hash": "x"}], "claim_boundary": {"gold_diff_step_proxy_measured": True, "causal_fault_attribution_established": False, "skill_revision_utility_measured": False, "enterprise_transfer_established": False}}
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(result), encoding="utf-8")
    assert verify(path)["verification_passed"] is True
