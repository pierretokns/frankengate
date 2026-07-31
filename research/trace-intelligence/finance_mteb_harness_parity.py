#!/usr/bin/env python3
"""Join same-projection HF and Ollama FinanceBench receipts."""

from __future__ import annotations

import argparse
import json
import pathlib
from typing import Any


SCHEMA_VERSION = "frankengate-finance-mteb-harness-parity-v1"


def load(path: pathlib.Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"result must be an object: {path}")
    return value


def build(hf: dict[str, Any], ollama: dict[str, Any]) -> dict[str, Any]:
    if hf.get("dataset", {}).get("id") != ollama.get("dataset", {}).get("id"):
        raise ValueError("dataset IDs differ")
    for field in ("revision", "corpus_sha256", "queries_sha256", "qrels_sha256", "evaluated_queries"):
        if hf.get("dataset", {}).get(field) != ollama.get("dataset", {}).get(field):
            raise ValueError(f"dataset field differs: {field}")
    if hf.get("dataset", {}).get("projection") != ollama.get("dataset", {}).get("projection"):
        raise ValueError("projection differs; parity requires the same bounded input")
    hf_arm = next(
        arm for arm in hf.get("arms", []) if arm.get("method") == "BalyasnyAI/multilingual-e5-base"
    )
    ollama_arm = ollama.get("arm")
    if not isinstance(ollama_arm, dict):
        raise ValueError("Ollama arm is missing")
    return {
        "schema_version": SCHEMA_VERSION,
        "analysis_revision": "financebench-hf-ollama-parity-v1",
        "dataset": hf["dataset"],
        "arms": [
            {"harness": "sentence-transformers-local", **hf_arm},
            {"harness": "ollama-native-api-loopback", **ollama_arm},
        ],
        "models": {
            "sentence_transformers": hf_arm.get("model"),
            "ollama": ollama.get("model"),
        },
        "relative": {
            "recall20_delta_hf_minus_ollama": hf_arm["recall@20"] - ollama_arm["recall@20"],
            "mrr_delta_hf_minus_ollama": hf_arm["mrr"] - ollama_arm["mrr"],
        },
        "claim_boundary": {
            "same_corpus": True,
            "same_projection": True,
            "multiple_harnesses_compared": True,
            "authorization_evaluated": False,
            "deletion_evaluated": False,
            "enterprise_transfer_evaluated": False,
            "automatic_promotion_authorized": False,
            "reason": "Public relevance parity only; endpoint and model behavior are not a governed production guarantee.",
        },
        "raw_data_committed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hf", type=pathlib.Path, required=True)
    parser.add_argument("--ollama", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--summary", type=pathlib.Path, required=True)
    args = parser.parse_args()
    result = build(load(args.hf), load(args.ollama))
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# FinanceBench embedding harness parity (bounded)",
        "",
        "The two arms use the same revision-pinned corpus and the same 2,500-character document projection.",
        "",
        "| harness/model | MRR | Recall@1 | Recall@5 | Recall@10 | Recall@20 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm in result["arms"]:
        lines.append(
            f"| {arm['harness']} / {arm['method']} | {arm['mrr']:.4f} | {arm['recall@1']:.4f} | {arm['recall@5']:.4f} | {arm['recall@10']:.4f} | {arm['recall@20']:.4f} |"
        )
    lines.extend([
        "",
        f"HF minus Ollama: Recall@20 {result['relative']['recall20_delta_hf_minus_ollama']:+.4f}; MRR {result['relative']['mrr_delta_hf_minus_ollama']:+.4f}.",
        "",
        "This is a public relevance comparison only; it does not authorize production promotion or establish RLS/deletion behavior.",
    ])
    args.summary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
