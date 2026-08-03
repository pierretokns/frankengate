import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wiki_gap_backend_assessment import assess_clickhouse_need


def test_small_fixture_stays_postgres_first():
    result = assess_clickhouse_need(
        {
            "event_count": 10_000,
            "source_bytes": 2_000_000,
            "p95_scan_seconds": 0.4,
            "daily_gap_scans": 12,
        }
    )
    assert result["decision"] == "postgres_first"
    assert result["reasons"] == []


def test_measured_scan_pressure_earns_clickhouse_benchmark():
    result = assess_clickhouse_need(
        {
            "event_count": 200_000_000,
            "source_bytes": 800_000_000_000,
            "p95_scan_seconds": 18.0,
            "daily_gap_scans": 250,
        }
    )
    assert result["decision"] == "clickhouse_candidate"
    assert len(result["reasons"]) == 3
    assert "ClickHouse" in result["next_step"]
