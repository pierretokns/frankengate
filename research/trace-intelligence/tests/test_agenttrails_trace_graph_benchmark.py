import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agenttrails_trace_graph_benchmark import _event, graph_edges, parse_episode, similarity


def call(tool, input_keys, output, status="completed"):
    return {"tool": tool, "input": {key: "redacted" for key in input_keys}, "output": output, "status": status}


def test_event_and_graph_are_content_free_and_deterministic():
    first = _event(call("read_file", ["path"], {"contents": "secret"}))
    second = _event(call("read_file", ["path"], {"contents": "different"}))
    assert first.action_id == second.action_id
    assert first.artifact_schema_id == second.artifact_schema_id
    assert graph_edges((first,)) == (f"a:{first.action_id}->o:{first.artifact_id}",)


def test_graph_similarity_captures_output_to_next_action_edge():
    a = _event(call("read_file", ["path"], {"contents": "x"}))
    b = _event(call("run_command", ["command"], {"output": "x"}))
    c = _event(call("edit_file", ["path", "patch"], {"ok": True}))
    assert similarity((a, b), (a, b), "graph") == 1.0
    assert similarity((a, b), (a, c), "graph") < 1.0
    assert 0.0 <= similarity((a, b), (a, c), "graph_shape") <= 1.0


def test_parse_episode_requires_four_tool_events():
    row = {"session_id": "s", "start_time": "2026-01-01", "source": "x", "project": "p", "messages": [{"tool_uses": [call("read_file", ["path"], {"contents": "x"})]}]}
    assert parse_episode(row) is None
