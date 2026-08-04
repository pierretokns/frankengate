#!/usr/bin/env python3
"""Verify the content-free multi-user DataClaw overlap receipt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    data = json.loads(args.receipt.read_text(encoding="utf-8"))
    assert data["schema"] == "dataclaw-multi-user-overlap-v1"
    assert len(data["datasets"]) >= 2
    assert all(item["license"] == "MIT" for item in data["datasets"].values())
    assert 0.0 <= data["pair"]["prompt_vocabulary_jaccard"] <= 1.0
    assert data["pair"]["shared_nontrivial_tool_call_forms"] >= 0
    assert "descriptive only" in data["claim_boundary"]
    assert "not emitted" in data["content_policy"]
    print("DataClaw multi-user overlap verification: PASS")


if __name__ == "__main__":
    main()
