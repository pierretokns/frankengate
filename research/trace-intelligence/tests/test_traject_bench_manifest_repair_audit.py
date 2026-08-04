import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from traject_bench_manifest_repair_audit import audit, normalize_name  # noqa: E402


def test_normalize_name_only_removes_presentation_differences() -> None:
    assert normalize_name("Spotify_v2: New releases") == normalize_name("Spotify _v2: New releases")
    assert normalize_name("alpha") != normalize_name("beta")


def test_audit_separates_exact_unique_and_unresolved_rows(tmp_path: Path) -> None:
    public = tmp_path / "public_data"
    (public / "tools").mkdir(parents=True)
    (public / "parallel" / "Demo").mkdir(parents=True)
    tools = [{"tool name": "Spotify _v2: New releases"}, {"tool name": "known"}]
    rows = [
        {"tool list": [{"tool name": "known"}]},
        {"tool list": [{"tool name": "Spotify_v2: New releases"}]},
        {"tool list": [{"tool name": "missing unknown"}]},
    ]
    (public / "tools" / "Demo_tool.json").write_text(json.dumps(tools), encoding="utf-8")
    (public / "tools" / "all_tools.json").write_text(json.dumps(tools), encoding="utf-8")
    (public / "parallel" / "Demo" / "simple_ver.json").write_text(json.dumps(rows), encoding="utf-8")
    result = audit(public)
    assert result["rows"] == 3
    assert result["exact_candidate_manifest_rows"] == 1
    assert result["uniquely_normalized_repair_rows"] == 1
    assert result["unresolved_rows"] == 1
    assert result["claim_boundary"]["automatic_fuzzy_repair_authorized"] is False
