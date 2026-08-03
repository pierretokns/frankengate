import numpy as np

from comrag_centroid_trace_benchmark import CentroidStore, extract_session, run


def test_extract_session_keeps_only_content_free_shape_features():
    session = extract_session({
        "session_id": "session-1",
        "project": "project-a",
        "start_time": "2026-01-01T00:00:00Z",
        "messages": [
            {"role": "user", "content": "Fix the cache"},
            {"role": "assistant", "tool_uses": [{"tool": "Bash", "input": {"command": "x"}, "status": "success"}]},
        ],
    })
    assert session is not None
    assert session.prompt == "Fix the cache"
    assert session.project == "project-a"
    assert len(session.shapes) == 1
    assert session.has_error is False


def test_centroid_store_merges_when_budget_is_exceeded():
    store = CentroidStore(threshold=0.99, max_clusters=2)
    store.add(np.asarray([1.0, 0.0]), 0, 1)
    store.add(np.asarray([0.0, 1.0]), 1, 1)
    store.add(np.asarray([-1.0, 0.0]), 2, 0)
    assert len(store.clusters) <= 2
    assert sum(len(cluster.members) for cluster in store.clusters) == 3


def test_run_reports_proxy_retrieval_metrics_without_gold_claims():
    sessions = [
        extract_session({"session_id": "1", "project": "a", "start_time": "2026-01-01", "messages": [{"role": "user", "content": "cache repair"}, {"role": "assistant", "tool_uses": [{"tool": "Bash", "input": {"command": "x"}, "status": "success"}]}]}),
        extract_session({"session_id": "2", "project": "a", "start_time": "2026-01-02", "messages": [{"role": "user", "content": "cache repair again"}, {"role": "assistant", "tool_uses": [{"tool": "Bash", "input": {"command": "x"}, "status": "success"}]}]}),
        extract_session({"session_id": "3", "project": "a", "start_time": "2026-01-03", "messages": [{"role": "user", "content": "cache repair later"}, {"role": "assistant", "tool_uses": [{"tool": "Bash", "input": {"command": "x"}, "status": "success"}]}]}),
    ]
    result = run([session for session in sessions if session is not None], train_fraction=2 / 3, threshold=0.1, max_clusters=2)
    assert result["test_sessions"] == 1
    assert 0 <= result["centroid_shape_hit_rate"] <= 1
