#!/usr/bin/env python3
"""Verify the frontier adjudication pilot receipt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    data = json.loads(args.receipt.read_text(encoding="utf-8"))
    assert data["schema"] == "dataclaw-cross-user-luna-adjudication-v1"
    assert data["pair_count"] > 0
    assert data["repeats_per_pair"] >= 2
    assert data["valid_call_count"] <= data["pair_count"] * data["repeats_per_pair"]
    for row in data["rows"]:
        assert 0.0 <= row["lexical_cosine"] <= 1.0
        assert 0.0 <= row["tool_name_jaccard"] <= 1.0
        for call in row["calls"]:
            if "label" in call:
                assert call["label"] in {"same_task", "related_task", "different", "unclear"}
                assert 0.0 <= call["confidence"] <= 1.0
    assert "Silver frontier" in data["claim_boundary"]
    assert "not emitted" in data["content_policy"]
    print("DataClaw cross-user Luna adjudication verification: PASS")


if __name__ == "__main__":
    main()
