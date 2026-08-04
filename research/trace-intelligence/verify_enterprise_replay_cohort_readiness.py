#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path

def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("receipt", type=Path); args = parser.parse_args(); data = json.loads(args.receipt.read_text(encoding="utf-8"))
    assert data["schema"] == "frankengate-enterprise-replay-cohort-readiness-v1"; assert data["record_count"] >= 0; assert isinstance(data["missing_required_record_fields"], list); assert data["ready_for_causal_replay"] is False; assert "No prompt" in data["content_policy"]
    print("enterprise replay cohort readiness verification: PASS")
if __name__ == "__main__": main()
