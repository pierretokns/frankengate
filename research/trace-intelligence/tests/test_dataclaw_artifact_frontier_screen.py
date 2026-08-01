import json

from dataclaw_artifact_frontier_screen import collect_candidates, parse_judgment, scrub


def test_scrub_removes_credential_like_values_but_keeps_shape():
    value = scrub({"command": "curl -H 'Authorization: Bearer abcdefghijklmnop' /tmp/a"})
    assert "abcdefghijklmnop" not in value["command"]
    assert "<credential>" in value["command"]


def test_collect_candidates_requires_repeated_successes_across_sessions():
    rows = [
        {"session_id": "a", "project": "p1", "source": "s1", "model": "m1", "messages": [{"role": "assistant", "tool_uses": [{"tool": "bash", "input": {"command": "echo ok"}, "status": "success", "output": {"text": "ok"}}]}]},
        {"session_id": "b", "project": "p2", "source": "s2", "model": "m2", "messages": [{"role": "assistant", "tool_uses": [{"tool": "bash", "input": {"command": "echo ok"}, "status": "success", "output": {"text": "ok"}}]}]},
    ]
    candidates = collect_candidates(rows, 8)
    assert len(candidates) == 1
    assert len(candidates[0]["sessions"]) == 2
    assert len(candidates[0]["projects"]) == 2


def test_parse_judgment_accepts_only_schema_label(tmp_path):
    path = tmp_path / "out.json"
    path.write_text(json.dumps({"label": "reusable_procedure", "confidence": 0.8, "reason": "x"}))
    result = parse_judgment(path)
    assert result["label"] == "reusable_procedure"
