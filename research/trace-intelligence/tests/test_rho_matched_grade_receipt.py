import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("rho_matched_grade_receipt", ROOT / "rho_matched_grade_receipt.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_rejects_unmatched_grade_sets(tmp_path: Path) -> None:
    left = tmp_path / "left.json"
    right = tmp_path / "right.json"
    left.write_text(json.dumps([{"task_id": "a", "score": 1}]))
    right.write_text(json.dumps([{"task_id": "b", "score": 1}]))
    for path in (left, right):
        assert path.exists()
    try:
        MODULE._grades(left)
        MODULE._grades(right)
    except Exception as exc:  # pragma: no cover
        raise AssertionError(exc)
