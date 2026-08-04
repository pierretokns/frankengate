import json

from skilllearnbench_fit_audit import audit


def test_skilllearnbench_fit_audit_distinguishes_adjacent_benchmark(tmp_path):
    root = tmp_path / "skilllearn"
    task = root / "tasks" / "demo" / "demo-1"
    task.mkdir(parents=True)
    (task / "task.toml").write_text(
        '[metadata]\ncategory = "analytics"\ndifficulty = "medium"\ntags = ["sql"]\n',
        encoding="utf-8",
    )
    (task / "tests").mkdir()
    (task / "tests" / "test.sh").write_text("true\n", encoding="utf-8")
    (task / "solution").mkdir()
    (task / "solution" / "solve.sh").write_text("true\n", encoding="utf-8")
    (root / "eval_keypoints" / "demo").mkdir(parents=True)
    (root / "baselines" / "b1-one-shot").mkdir(parents=True)
    (root / "skills" / "human_authored" / "demo" / "skill").mkdir(parents=True)
    (root / "skills" / "human_authored" / "demo" / "skill" / "SKILL.md").write_text("# skill\n", encoding="utf-8")
    (root / "LICENSE").write_text("MIT License\n", encoding="utf-8")
    result = audit(root)
    assert result["benchmark"]["task_count"] == 1
    assert result["skill_artifacts"]["human_authored_present"] is True
    assert result["fit"]["continual_skill_generation"] is True
    assert result["fit"]["cross_user_transfer"] is False
    assert result["claim_boundary"]["enterprise_skill_transfer_proven"] is False
