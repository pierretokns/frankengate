import json
from pathlib import Path

from verify_traject_bench_frontier_reranker import file_hash, verify


def test_verify_checks_external_raw_hashes(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    raw = raw_dir / "case-000.json"
    raw.write_text('{"prompt_sha256":"x"}', encoding="utf-8")
    result = tmp_path / "result.json"
    result.write_text(
        json.dumps(
            {
                "schema_version": "frankengate-traject-bench-frontier-reranker-v1",
                "dataset": {"selected_cases": 1},
                "protocol": {"frontier_sees_gold_targets": False, "frontier_sees_tool_outputs": False},
                "failures": 0,
                "raw_receipts": [{"case_index": 0, "raw_sha256": file_hash(raw)}],
                "arms": {
                    "lexical": {"records": 1, "mrr": 0.0, "recall_at_1": 0.0, "recall_at_5": 0.0, "recall_at_10": 0.0},
                    "frontier": {"records": 1, "mrr": 1.0, "recall_at_1": 1.0, "recall_at_5": 1.0, "recall_at_10": 1.0},
                },
            }
        ),
        encoding="utf-8",
    )
    assert verify(result, raw_dir)["verification_passed"] is True
