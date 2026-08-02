import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from codex_archive_to_friction_luna import convert


def test_converter_uses_native_user_events_only(tmp_path: Path) -> None:
    root = tmp_path / "archive"
    root.mkdir()
    source = root / "rollout-test.jsonl"
    source.write_text(
        json.dumps({"payload": {"type": "session_meta", "cwd": "/private/project"}})
        + "\n"
        + json.dumps({"payload": {"type": "message", "role": "user", "message": "context"}})
        + "\n"
        + json.dumps({"payload": {"type": "user_message", "message": "please fix this"}})
        + "\n",
        encoding="utf-8",
    )
    output = tmp_path / "input.jsonl"
    result = convert(root, output)
    assert result["sessions"] == 1
    assert result["user_messages"] == 1
    row = json.loads(output.read_text(encoding="utf-8"))
    assert row["project"] == "/private/project"
    assert row["messages"] == [{"role": "user", "content": "please fix this"}]
