#!/usr/bin/env python3
"""Verify the content-free DataClaw user-history audit."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    data = json.loads(args.receipt.read_text(encoding="utf-8"))
    assert data["schema"] == "dataclaw-user-history-audit-v1"
    assert data["source"]["license"] == "MIT"
    assert data["sessions"] >= 100
    assert data["project_count"] >= 2
    assert data["tool_uses"] > 0
    assert 0.0 <= data["friction_session_rate"] <= 1.0
    assert data["claim_boundary"]["candidate_artifacts_only"] is True
    assert data["claim_boundary"]["known_good_artifacts"] is False
    assert "not emitted" in data["content_policy"]
    print("DataClaw user-history audit verification: PASS")


if __name__ == "__main__":
    main()
