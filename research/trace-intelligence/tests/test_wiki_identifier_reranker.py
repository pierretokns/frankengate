import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wiki_identifier_reranker import rerank_score, text


def test_identifier_and_aliases_are_in_reranker_text() -> None:
    page = {"title": "Payments", "text": "ledger", "aliases": ["pay"], "source_id": "SRC-42", "source_domain": "example.org"}
    assert "SRC-42" in text(page)
    assert rerank_score("retrieve SRC-42", page, 0.2) > rerank_score("retrieve SRC-99", page, 0.2)
