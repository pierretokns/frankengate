import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wiki_agentic_rag_benchmark import WikiIndex, fixture
from wiki_arag_codex_loop import SCHEMA, _chunks, _search_observation
from wiki_arag_receipt import aggregate


def test_arag_exposes_three_distinct_retrieval_actions():
    actions = SCHEMA["properties"]["action"]["enum"]
    assert actions == ["keyword_search", "semantic_search", "read_chunk", "finish"]


def test_arag_keyword_and_semantic_tools_use_different_backends():
    data = fixture(1)
    index = WikiIndex(data["pages"], backend="hybrid")
    keyword = _search_observation(index, "Atlas-00 preferred endpoint", 3, "fts")
    semantic = _search_observation(index, "When does the service normally deploy?", 3, "tfidf")
    assert keyword
    assert semantic
    assert index.backend == "hybrid"


def test_arag_chunk_reads_are_bounded_and_addressable():
    page = fixture(1)["pages"][1]
    chunks = _chunks(page)
    assert chunks
    assert all(len(chunk) <= 320 for chunk in chunks)
    assert "Atlas-00" in chunks[0]


def test_arag_receipt_aggregates_tool_usage_without_trace_content():
    rows = [
        {
            "corpus_size": 1,
            "gold_page_ids": ["wiki-00/operations"],
            "searched_gold": True,
            "loaded_gold": True,
            "finished": True,
            "answer_matches_gold": True,
            "steps": 3,
            "latency_ms": 10.0,
            "error": None,
            "tool_counts": {"keyword_search": 1, "read_chunk": 1, "finish": 1},
        },
        {
            "corpus_size": 1,
            "gold_page_ids": [],
            "searched_gold": False,
            "loaded_gold": False,
            "finished": True,
            "answer_matches_gold": True,
            "steps": 2,
            "latency_ms": 20.0,
            "error": None,
            "tool_counts": {"keyword_search": 1, "finish": 1},
        },
    ]
    receipt = aggregate(rows)
    assert receipt[0]["target_answer_accuracy"] == 1.0
    assert receipt[0]["nil_abstention_accuracy"] == 1.0
    assert receipt[0]["tool_counts"]["keyword_search"] == 2
