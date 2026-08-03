from pathlib import Path


def test_clickhouse_projection_keeps_analytics_separate_from_authority():
    sql = (Path(__file__).resolve().parents[1] / "sql" / "clickhouse_wiki_gap_mining.sql").read_text()
    assert "ENGINE = MergeTree" in sql
    assert "PARTITION BY toYYYYMM(event_time)" in sql
    assert "ORDER BY (tenant_id, session_id, event_time, event_id)" in sql
    assert "CREATE OR REPLACE VIEW frankengate_wiki_gap_query_rollup" in sql
    assert "missing_operational_knowledge" in sql
    assert "distinct_users >= 2" in sql
    assert "PostgreSQL" in sql
