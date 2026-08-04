import sys

from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stateofai_wiki_quality_adapter import adapt, usable


def test_quality_filter_rejects_cache_urls_and_short_summaries() -> None:
    assert not usable({"title": "https://example.org/a", "summary": "x" * 200, "issuer": "Org", "source_family": "family"})
    assert not usable({"title": "Useful report", "summary": "short", "issuer": "Org", "source_family": "family"})


def test_quality_adapter_is_deterministic_and_adds_multiple_nil_cases() -> None:
    source = {"id": "public-source:example.org:one:abc", "title": "Example Annual Report", "summary": "A useful report about investments and operations " * 5, "issuer": "Example Org", "source_family": "annual_reports", "url": "https://example.org/one.pdf"}
    result = adapt({"sources": [source]}, top_domains=1, per_domain=1)
    assert len(result["pages"]) == 1
    assert len(result["questions"]) == 10
    assert sum(question["slice"] == "nil" for question in result["questions"]) == 5
    assert result == adapt({"sources": [source]}, top_domains=1, per_domain=1)
