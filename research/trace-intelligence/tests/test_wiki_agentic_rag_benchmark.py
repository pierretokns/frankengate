import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wiki_agentic_rag_benchmark import WikiIndex, evaluate, fixture


def test_fixture_is_deterministic_and_has_scale() -> None:
    first = fixture(25)
    second = fixture(25)
    assert first == second
    assert len(first["pages"]) == 100
    assert len({page["wiki_id"] for page in first["pages"]}) == 25
    assert any(question["slice"] == "nil" for question in first["questions"])


def test_backend_contract_supports_search_page_and_link_expansion() -> None:
    data = fixture(2)
    index = WikiIndex(data["pages"], backend="hybrid", compiled=True)
    ranked = index.search("When does Atlas-00 normally deploy?", k=5)
    assert ranked
    assert "wiki-00/operations" in {row["page_id"] for row in ranked}
    assert index.get_page("wiki-00/operations")["wiki_id"] == "wiki-00"
    linked = {page["page_id"] for page in index.expand_links("wiki-00/overview", depth=1)}
    assert linked == {"wiki-00/operations", "wiki-00/security"}


def test_scale_evaluation_reports_all_backend_arms() -> None:
    result = evaluate(fixture(25), sizes=(1, 5, 10, 25), k=5)
    assert len(result["results"]) == 24
    assert {row["size"] for row in result["results"]} == {1, 5, 10, 25}
    assert {row["backend"] for row in result["results"]} == {"fts", "tfidf", "hybrid"}
    assert all("p95_latency_ms" in row["metrics"] for row in result["results"])
