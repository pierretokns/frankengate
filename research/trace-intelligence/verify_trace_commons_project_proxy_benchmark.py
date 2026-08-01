#!/usr/bin/env python3
"""Verify the content-free project-proxy benchmark receipt."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    data = json.loads(args.receipt.read_text(encoding="utf-8"))
    assert data["schema"] == "trace-commons-project-proxy-benchmark-v1"
    assert data["session_count"] > 1
    assert data["eligible_repeated_project_sessions"] > 1
    assert set(data["arms"]) == {"structure", "prompt", "combined"}
    for arm in data["arms"].values():
        assert 0.0 <= arm["top1_rate"] <= 1.0
        assert 0.0 <= arm["same_project_mrr"] <= 1.0
    assert "no user identity" in data["interpretation"].lower()
    assert "no transcript" in data["content_policy"].lower()
    print("trace commons project-proxy benchmark verification: PASS")


if __name__ == "__main__":
    main()
