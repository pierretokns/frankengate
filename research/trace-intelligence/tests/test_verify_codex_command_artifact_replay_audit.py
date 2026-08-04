import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from codex_command_artifact_replay_audit import audit
from verify_codex_command_artifact_replay_audit import parse_file, verify


def _row(payload: dict) -> str:
    return json.dumps({"type": "response_item", "payload": payload}, ensure_ascii=False)


def test_verifier_preserves_unicode_line_separator_inside_json_record(tmp_path: Path) -> None:
    path = tmp_path / "rollout-2026-01-01.jsonl"
    output = "process exited with code 0\u2028after a tool result"
    path.write_text(
        "\n".join(
            [
                _row({"type": "session_meta", "cwd": "/repo"}),
                _row({"type": "function_call", "call_id": "a", "arguments": json.dumps({"cmd": "pytest tests/test_x.py"})}),
                _row({"type": "function_call_output", "call_id": "a", "output": output}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps(audit([path])), encoding="utf-8")
    checked = verify(result_path, tmp_path)
    assert checked["receipt_matches"] is True
    assert len(parse_file(path)) == 1


def test_verifier_claim_boundary_does_not_authorize_replay(tmp_path: Path) -> None:
    path = tmp_path / "rollout-2026-01-01.jsonl"
    path.write_text(
        "\n".join(
            [
                _row({"type": "function_call", "call_id": "a", "arguments": json.dumps({"cmd": "echo ok"})}),
                _row({"type": "function_call_output", "call_id": "a", "output": "process exited with code 0"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps(audit([path])), encoding="utf-8")
    checked = verify(result_path, tmp_path)
    assert checked["claim_boundary"]["verification_passed"] is True
    assert checked["claim_boundary"]["automatic_replay_authorized"] is False
