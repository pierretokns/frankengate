import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from codex_command_artifact_replay_audit import audit, normalized_command, parse_session  # noqa: E402


def test_normalized_command_redacts_values_without_executing() -> None:
    assert normalized_command("pytest tests/test_x.py --seed 42") == "pytest tests/test_x.py --seed <value>"
    assert normalized_command("   ") is None


def test_parse_session_correlates_calls_to_structured_outcomes(tmp_path: Path) -> None:
    path = tmp_path / "rollout-2026-01-01.jsonl"
    rows = [
        {"type": "session_meta", "payload": {"cwd": "/repo"}},
        {"type": "response_item", "payload": {"type": "function_call", "call_id": "a", "name": "shell", "arguments": json.dumps({"cmd": "pytest tests/test_x.py --seed 42"})}},
        {"type": "response_item", "payload": {"type": "function_call_output", "call_id": "a", "output": "process exited with code 0"}},
        {"type": "response_item", "payload": {"type": "function_call", "call_id": "b", "name": "shell", "arguments": json.dumps({"cmd": "pytest tests/test_x.py --seed 43"})}},
        {"type": "response_item", "payload": {"type": "function_call_output", "call_id": "b", "output": "process exited with code 1"}},
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    parsed = parse_session(path)
    assert [row["outcome"] for row in parsed] == ["success", "failure"]
    assert parsed[0]["artifact_hash"] == parsed[1]["artifact_hash"]


def test_audit_counts_scope_reuse(tmp_path: Path) -> None:
    path = tmp_path / "rollout-2026-01-01.jsonl"
    rows = [
        {"type": "session_meta", "payload": {"cwd": "/repo"}},
        {"type": "response_item", "payload": {"type": "function_call", "call_id": "a", "name": "shell", "arguments": json.dumps({"cmd": "pytest tests/test_x.py"})}},
        {"type": "response_item", "payload": {"type": "function_call_output", "call_id": "a", "output": "process exited with code 0"}},
        {"type": "response_item", "payload": {"type": "function_call", "call_id": "b", "name": "shell", "arguments": json.dumps({"cmd": "pytest tests/test_x.py"})}},
        {"type": "response_item", "payload": {"type": "function_call_output", "call_id": "b", "output": "process exited with code 1"}},
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    result = audit([path])
    assert result["aggregate"]["repeated_occurrences_after_same_scope_success"] == 1
    assert result["aggregate"]["same_scope_prior_success_later_failure"] == 1
