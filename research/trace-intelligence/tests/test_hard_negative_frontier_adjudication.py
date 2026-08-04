import json

import pytest

from hard_negative_frontier_adjudication import choose_control_packets, page_packet, parse_output


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


def test_control_packets_exclude_gold_page_for_random_and_lexical_controls():
    data = {
        "pages": [
            {"page_id": "gold", "title": "DB2 error", "text": "SQLCODE -401"},
            {"page_id": "near", "title": "DB2 error", "text": "SQLCODE -402"},
            {"page_id": "other", "title": "Python guide", "text": "unrelated"},
        ],
        "questions": [
            {"question_id": "q1", "question": "Why does DB2 SQLCODE -401 fail?", "gold_page_ids": ["gold"]},
        ],
    }
    for control in ("random", "lexical"):
        packets = choose_control_packets(data, control=control, candidate_limit=3, train_limit=1, test_limit=0, seed=7, limit=1)
        assert len(packets) == 1
        assert packets[0]["candidate_hash"] != packets[0]["positive_hash"]
