#!/usr/bin/env python3
"""Verify the content-free Trace Commons metadata audit invariants."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    data = json.loads(args.receipt.read_text(encoding="utf-8"))
    assert data["schema"] == "trace-commons-metadata-audit-v1"
    assert data["file_count"] > 0
    assert data["line_count"] >= data["session_count"]
    assert data["session_count"] > 1
    assert data["readiness"]["supports_cross_user_clustering"] is False
    assert data["readiness"]["has_explicit_user_identity"] is False
    assert "No transcript" in data["content_policy"]
    print("trace commons metadata audit verification: PASS")


if __name__ == "__main__":
    main()
