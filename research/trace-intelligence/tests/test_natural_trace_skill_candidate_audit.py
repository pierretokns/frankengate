from __future__ import annotations

import json
from pathlib import Path

from natural_trace_skill_candidate_audit import load_tool_events, protocol_predicates


def test_claude_protocol_predicates() -> None:
    events = [
        type("E", (), {"name": "Read", "arguments": {"file_path": "/task/problem/README.md"}})(),
        type("E", (), {"name": "Read", "arguments": {"file_path": "/task/problem/data_description.md"}})(),
        type("E", (), {"name": "Bash", "arguments": {"command": "find /task/problem/data; curl health; nvidia-smi"}})(),
        type("E", (), {"name": "Write", "arguments": {"file_path": "/workspace/run.py"}})(),
        type("E", (), {"name": "Bash", "arguments": {"command": "python evaluate.py score output"}})(),
    ]
    result = protocol_predicates(events)
    assert result["candidate_protocol_complete"] is True
    assert result["candidate_protocol_score"] == 1.0


def test_loads_codex_function_calls(tmp_path: Path) -> None:
    path = tmp_path / "codex.jsonl"
    path.write_text(
        json.dumps(
            {
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "name": "exec_command",
                    "arguments": '{"cmd":"cat /task/problem/README.md"}',
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    events = load_tool_events(path)
    assert len(events) == 1
    assert events[0].name == "exec_command"
    assert events[0].arguments["cmd"].startswith("cat /task/problem")
