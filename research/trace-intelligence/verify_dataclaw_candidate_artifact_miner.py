#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path

def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("receipt", type=Path); args = parser.parse_args(); data = json.loads(args.receipt.read_text(encoding="utf-8"))
    assert data["schema"] == "dataclaw-candidate-artifact-miner-v1"; assert data["candidate_count"] == len(data["candidates"]); assert data["candidate_count"] > 0; assert all(item["review_required"] and not item["promotion_eligible"] for item in data["candidates"]); assert "not emitted" in data["content_policy"]
    print("DataClaw candidate artifact miner verification: PASS")
if __name__ == "__main__": main()
