import json

import pytest

from hard_negative_frontier_adjudication import page_packet, parse_output


def test_page_packet_excludes_page_id_and_bounds_text():
    packet = page_packet({"page_id": "secret-id", "title": "Title", "aliases": ["Alias"], "text": "x" * 10000})
    assert "page_id" not in packet
    assert len(packet["text"]) == 9000
    assert packet["truncated"] == "true"


def test_parse_output_validates_duplicate_refs_without_schema_unique_items(tmp_path):
    output = tmp_path / "output.json"
    output.write_text(json.dumps({
        "label": "near_miss_hard_negative",
        "confidence": "high",
        "evidence_refs": ["candidate", "candidate"],
    }))
    with pytest.raises(ValueError, match="unique"):
        parse_output(output)
