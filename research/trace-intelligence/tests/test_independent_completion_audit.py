from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("independent_completion_audit", ROOT / "independent_completion_audit.py")
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_completion_audit_keeps_goal_incomplete_and_blocks_promotion() -> None:
    result = MODULE.audit(ROOT / "experiments/results")
    assert result["schema_version"] == "frankengate-independent-completion-audit-v1"
    assert result["status"] == "active_incomplete"
    assert result["claim_boundary"]["objective_complete"] is False
    assert result["claim_boundary"]["automatic_integration_authorized"] is False
    assert "independent_outcome_evaluation" in result["incomplete_requirement_ids"]
    assert "fair_controls_and_disjoint_splits" in result["incomplete_requirement_ids"]
