import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stateofai_wiki_adapter import adapt


def test_stateofai_adapter_partitions_sources_and_emits_identity_queries() -> None:
    data = {
        "sources": [
            {"id": "a", "title": "Annual report", "issuer": "Issuer A", "url": "https://a.example/report", "summary": "capital allocation"},
            {"id": "b", "title": "Board packet", "issuer": "Issuer B", "url": "https://b.example/packet", "summary": "governance"},
            {"id": "c", "title": "RFP", "issuer": "Issuer A", "url": "https://a.example/rfp", "summary": "procurement"},
        ],
        "pages": [],
    }
    corpus = adapt(data, top_domains=2, per_domain=10)
    assert len(corpus["pages"]) == 3
    assert len({page["wiki_id"] for page in corpus["pages"]}) == 2
    assert any(question["slice"] == "exact_identifier" for question in corpus["questions"])
    assert corpus["questions"][-1]["slice"] == "nil"
