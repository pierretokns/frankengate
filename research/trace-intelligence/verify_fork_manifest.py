#!/usr/bin/env python3
"""Verify that every recorded legacy modernization has provenance metadata."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse


REQUIRED = {
    "name",
    "upstream_repository",
    "upstream_commit",
    "upstream_license",
    "fork_repository",
    "fork_branch",
    "implementation",
    "source_copy",
    "uv_reproducible",
    "claim_boundary",
}


def verify(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema"] == "frankengate-upstream-fork-manifest-v1"
    entries = data["entries"]
    assert entries, "manifest must contain at least one fork"
    names = set()
    for entry in entries:
        assert REQUIRED <= entry.keys()
        assert entry["name"] not in names
        names.add(entry["name"])
        assert len(entry["upstream_commit"]) == 40
        assert entry["source_copy"] is False
        assert entry["uv_reproducible"] is True
        for field in ("upstream_repository", "fork_repository"):
            parsed = urlparse(entry[field])
            assert parsed.scheme == "https" and parsed.netloc == "github.com"
        assert entry["fork_branch"]
        assert entry["claim_boundary"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    verify(args.manifest)
    data = json.loads(args.manifest.read_text(encoding="utf-8"))
    print(f"fork manifest verification: PASS ({len(data['entries'])} entries)")


if __name__ == "__main__":
    main()
