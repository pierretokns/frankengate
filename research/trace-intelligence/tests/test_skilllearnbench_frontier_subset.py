from __future__ import annotations

import json

from skilllearnbench_frontier_subset import _validate_answer, load_expected


def test_validate_answer_requires_published_q1_q3_and_numeric_tokens(tmp_path):
    answer = tmp_path / "answer.json"
    answer.write_text(
        json.dumps(
            {
                "q1": {"answer": sorted(["eid_06cddbb3", "eid_1e9356f5", "eid_24dbff62", "eid_2d72674d", "eid_4350bf70", "eid_7ab41e2c", "eid_99835861", "eid_c3f3eff2"]), "tokens": 1},
                "q3": {"answer": ["https://www.convosuggest.com/demo", "https://www.pitchperfectai.com/demo", "https://www.salesmateai.com/demo"], "tokens": 2},
            }
        ),
        encoding="utf-8",
    )
    result = _validate_answer(answer)
    assert result["passed"] is True
    assert result["q1_missing"] == 0
    assert result["q3_missing"] == 0


def test_validate_answer_rejects_missing_gold_item(tmp_path):
    answer = tmp_path / "answer.json"
    answer.write_text(
        json.dumps(
            {
                "q1": {"answer": ["eid_06cddbb3"], "tokens": 1},
                "q3": {"answer": [], "tokens": 2},
            }
        ),
        encoding="utf-8",
    )
    result = _validate_answer(answer)
    assert result["passed"] is False
    assert result["q1_missing"] == 7
    assert result["q3_missing"] == 3


def test_validate_answer_records_precision_not_only_required_inclusion(tmp_path):
    answer = tmp_path / "answer.json"
    answer.write_text(
        json.dumps(
            {
                "q1": {
                    "answer": sorted(
                        [
                            "eid_06cddbb3",
                            "eid_1e9356f5",
                            "eid_24dbff62",
                            "eid_2d72674d",
                            "eid_4350bf70",
                            "eid_7ab41e2c",
                            "eid_99835861",
                            "eid_c3f3eff2",
                            "eid_extra",
                        ]
                    ),
                    "tokens": 1,
                },
                "q3": {
                    "answer": [
                        "https://www.convosuggest.com/demo",
                        "https://www.pitchperfectai.com/demo",
                        "https://www.salesmateai.com/demo",
                    ],
                    "tokens": 2,
                },
            }
        ),
        encoding="utf-8",
    )
    result = _validate_answer(answer)
    assert result["passed"] is True
    assert result["exact_metrics"]["q1"]["precision"] == 8 / 9
    assert result["exact_metrics"]["q1"]["recall"] == 1.0


def test_load_expected_reads_pinned_task_verifier_without_execution(tmp_path):
    verifier = tmp_path / "tests" / "test_outputs.py"
    verifier.parent.mkdir()
    verifier.write_text(
        "EXPECTED_ANSWER_Q1 = ['a']\nEXPECTED_ANSWER_Q3 = ['b']\n",
        encoding="utf-8",
    )
    assert load_expected(tmp_path) == {"q1": {"a"}, "q3": {"b"}}
