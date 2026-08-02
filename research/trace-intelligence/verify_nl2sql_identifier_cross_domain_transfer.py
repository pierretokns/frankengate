#!/usr/bin/env python3
"""Verify cross-domain identifier-transfer receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def verify(path: Path) -> dict[str, object]:
    result = json.loads(path.read_text(encoding="utf-8"))
    assert result["schema_version"] == "frankengate-nl2sql-identifier-cross-domain-transfer-v1"
    assert result["datasets"]["defog"]["cases"] > 0
    assert result["datasets"]["wmh_bird"]["cases"] > 0
    assert set(result["directions"]) == {"defog_to_bird", "bird_to_defog"}
    for direction in result["directions"].values():
        for arm, metrics in direction.items():
            assert metrics["cases"] > 0
            assert 0.0 <= metrics["mrr"] <= 1.0
            assert 0.0 <= metrics["recall_at_1"] <= 1.0
            assert 0.0 <= metrics["recall_at_5"] <= 1.0
    claim = result["claim_boundary"]
    assert claim["semantic_alias_labels"] is False
    assert claim["changed_system_replay"] is False
    assert claim["enterprise_transfer"] is False
    assert claim["embedding_promotion"] is False
    body = dict(result)
    actual = body.pop("result_sha256")
    assert actual == digest(body)
    verification = {"schema_version": "frankengate-nl2sql-identifier-cross-domain-transfer-verification-v1", "passed": True, "result_sha256": actual}
    print(json.dumps(verification, sort_keys=True))
    return verification


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
