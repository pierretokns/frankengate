import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bird_trace_model_cascade import parse_json_response  # noqa: E402
from verify_bird_trace_model_cascade import parse_json_response as verify_parse_json_response  # noqa: E402


def test_parse_json_response_requires_cascade_contract() -> None:
    parsed = parse_json_response(
        '```json {"artifact_matches_task": null, "replayability": "unclear", '
        '"validator_type": "query_result", "confidence": "low"} ```'
    )
    assert parsed is not None
    assert parsed["artifact_matches_task"] is None
    assert parse_json_response("not json") is None
    assert verify_parse_json_response('{"artifact_matches_task": null, "replayability": "unclear", "validator_type": "query_result", "confidence": "low"}') is not None
