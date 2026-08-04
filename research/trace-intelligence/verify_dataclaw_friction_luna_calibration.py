#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path

def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("receipt", type=Path); args = parser.parse_args(); data = json.loads(args.receipt.read_text(encoding="utf-8"))
    assert data["schema"] == "dataclaw-friction-luna-calibration-v1"; assert data["row_count"] > 0; assert data["valid_call_count"] <= data["row_count"] * data["repeats_per_row"]; assert "silver" in data["claim_boundary"].lower(); assert "not emitted" in data["content_policy"]
    for row in data["rows"]:
        for call in row["calls"]:
            if "label" in call: assert call["label"] in {"friction", "productive_iteration", "unclear"} and 0 <= call["confidence"] <= 1
    print("DataClaw friction Luna calibration verification: PASS")
if __name__ == "__main__": main()
