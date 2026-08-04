import json
import sqlite3
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bird_trace_artifact_reuse import (  # noqa: E402
    extract_sql,
    instantiate,
    mutate_literal,
    sql_template,
)
from sqlglot import parse_one  # noqa: E402


def test_extract_sql_handles_display_pipe_and_rejects_multi_statement() -> None:
    command = 'sqlite3 database.db "SELECT count(*) FROM t;" | head -5'
    assert extract_sql(command) == "SELECT count(*) FROM t;"
    assert extract_sql('sqlite3 database.db "SELECT 1; SELECT 2;"') is None


def test_parameter_round_trip_preserves_structure_and_changes_literal() -> None:
    source = "SELECT COUNT(*) FROM orders WHERE status = 'paid' AND amount > 10"
    template, literals = sql_template(source)
    target_literals = [mutate_literal(literal, index) for index, literal in enumerate(literals)]
    rendered = instantiate(template, target_literals)
    assert "status = 'paid__frankengate_parameter_1'" in rendered
    assert "amount > 12" in rendered
    assert parse_one(rendered, read="sqlite")


def test_sqlite_execution_can_compare_artifact_and_target() -> None:
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE orders(status TEXT, amount INTEGER)")
    connection.executemany("INSERT INTO orders VALUES (?, ?)", [("paid", 11), ("hold", 20)])
    connection.commit()
    source = "SELECT COUNT(*) FROM orders WHERE status = 'paid' AND amount > 10"
    template, literals = sql_template(source)
    target = instantiate(template, [mutate_literal(literal, index) for index, literal in enumerate(literals)])
    source_result = connection.execute(source).fetchall()
    target_result = connection.execute(target).fetchall()
    assert source_result == [(1,)]
    assert target_result == [(0,)]
