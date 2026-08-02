import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from codex_archive_history_mining import parse_session  # noqa: E402


def test_current_archive_schema_is_one_session_per_file(tmp_path: Path) -> None:
    path = tmp_path / "rollout-example.jsonl"
    rows = [
        {"type": "session_meta", "payload": {"id": "session-1", "cwd": "/repo"}},
        {"type": "event_msg", "payload": {"type": "user_message", "message": "Please fix the failing query"}},
        {"type": "event_msg", "payload": {"type": "agent_message", "message": "I will inspect it"}},
        {"type": "response_item", "payload": {"type": "function_call", "name": "shell", "arguments": "{}"}},
        {"type": "response_item", "payload": {"type": "function_call_output", "output": "process exited with code 1"}},
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    result = parse_session(path)
    assert result["session_id"] == "rollout-example"
    assert result["user_prompt_count"] == 1
    assert result["assistant_turn_count"] == 1
    assert result["function_call_count"] == 1
    assert result["function_call_output_count"] == 1
    assert result["structured_executor_error_count"] == 1
    assert result["explicit_signal_counts"]["retry_or_repair"] == 1
    assert result["episode_count"] == 1
    assert result["episodes_with_structured_error"] == 1
    assert result["episodes_with_unresolved_structured_error"] == 1
    assert result["friction_episode_count"] == 1
