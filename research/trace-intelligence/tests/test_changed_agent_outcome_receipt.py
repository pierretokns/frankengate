import importlib.util
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("changed_agent_outcome_receipt", ROOT / "changed_agent_outcome_receipt.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_changed_agent_receipt_recomputes_sealed_bird_outcome() -> None:
    result = MODULE.build_receipt(
        ROOT / "experiments/results/bird-sql-skill-factorial-powered-2026-07-31.json",
        ROOT / "experiments/results/bird-sql-skill-factorial-powered-verification-2026-07-31.json",
    )
    effect = result["outcome"]["exact_execution"]
    assert effect["pairs"] == 20
    assert effect["candidate_wins"] == 0
    assert effect["candidate_losses"] == 0
    assert effect["ties"] == 20
    assert result["claim_boundary"]["changed_agent_future_task_outcome_measured"] is True
    assert result["claim_boundary"]["cross_user_enterprise_transfer_measured"] is False


def test_bootstrap_is_deterministic() -> None:
    assert MODULE.bootstrap([0.0, 1.0, -1.0], seed=7) == MODULE.bootstrap([0.0, 1.0, -1.0], seed=7)
