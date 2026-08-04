from __future__ import annotations

import json
from pathlib import Path

from natural_trace_skill_protocol_intervention import VARIANTS, _load_fixture_with_variants


def test_skill_fixture_is_balanced_and_has_three_arms() -> None:
    path = Path(__file__).parents[1] / "configs" / "experiments" / "natural-trace-skill-protocol-fixture-2026-07-30.json"
    value, limits, fixtures = _load_fixture_with_variants(path)
    assert tuple(item["id"] for item in value["variants"]) == VARIANTS
    assert len(fixtures) == 6
    assert limits.max_sql_attempts == 2
    assert all(set(fixture.variant_order) == set(VARIANTS) for fixture in fixtures)


def test_fixture_contains_no_benchmark_content() -> None:
    path = Path(__file__).parents[1] / "configs" / "experiments" / "natural-trace-skill-protocol-fixture-2026-07-30.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    assert value["benchmark_content_used"] is False
    assert value["raw_model_content_committed"] is False
