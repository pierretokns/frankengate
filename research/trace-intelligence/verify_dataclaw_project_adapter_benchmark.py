#!/usr/bin/env python3
"""Verify the content-free DataClaw project-adapter receipt."""
from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path

SCHEMA_VERSION = "frankengate-dataclaw-project-adapter-verification-v1"

def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--input", type=Path, required=True); parser.add_argument("--output", type=Path, required=True); args = parser.parse_args()
    result = json.loads(args.input.read_text(encoding="utf-8")); unsigned = dict(result); expected = unsigned.pop("result_sha256", None); modes = result.get("aggregate", {})
    checks = {"schema": result.get("schema_version") == "frankengate-dataclaw-project-adapter-v1", "result_hash": expected == digest(unsigned), "modes": set(modes) == {"prompt", "tool", "combined"}, "folds": all(modes[name]["folds"] > 0 for name in modes), "bounded": all(0 <= modes[name][metric] <= 1 for name in modes for metric in ("baseline_mrr", "adapted_mrr", "baseline_recall_at_1", "adapted_recall_at_1", "baseline_recall_at_5", "adapted_recall_at_5")), "raw_absent": result.get("source", {}).get("raw_content_committed") is False, "claim_boundary": result.get("claim_boundary", {}).get("promotion_authorized") is False}
    verification = {"schema_version": SCHEMA_VERSION, "passed": all(checks.values()), "checks": checks, "result_sha256": expected}; args.output.parent.mkdir(parents=True, exist_ok=True); args.output.write_text(json.dumps(verification, indent=2, sort_keys=True) + "\n", encoding="utf-8"); print(json.dumps(verification, sort_keys=True)); raise SystemExit(0 if verification["passed"] else 1)
