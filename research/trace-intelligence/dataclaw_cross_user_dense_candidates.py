#!/usr/bin/env python3
"""Local-only cross-user candidate generation over licensed DataClaw exports.

No session text leaves the machine. Lexical and local Nomic rankings are
compared as candidate generators; there is deliberately no semantic ground
truth or external model adjudication in this receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Sequence
from urllib import request

from dataclaw_cross_user_luna_adjudication import clean_text, cosine as set_cosine, load, terms


SCHEMA_VERSION = "frankengate-dataclaw-cross-user-dense-candidates-v1"
EMBED_MODEL = "nomic-embed-text:latest"


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def vector_cosine(left: Sequence[float], right: Sequence[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(a * a for a in right))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


def post_embed(endpoint: str, texts: Sequence[str]) -> list[list[float]]:
    payload = json.dumps({"model": EMBED_MODEL, "input": list(texts), "truncate": True}).encode()
    req = request.Request(endpoint.rstrip("/") + "/api/embed", data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with request.urlopen(req, timeout=600) as response:
        value = json.loads(response.read().decode())
    vectors = value.get("embeddings")
    if not isinstance(vectors, list) or len(vectors) != len(texts):
        raise RuntimeError("embedding response count mismatch")
    return [[float(item) for item in vector] for vector in vectors]


def pair_hash(left: dict[str, Any], right: dict[str, Any]) -> str:
    return digest({"left": left["id"], "right": right["id"]})


def run(left_path: Path, right_path: Path, output: Path, *, endpoint: str, top_k: int) -> dict[str, Any]:
    left = load(left_path, "left")
    right = load(right_path, "right")
    if not left or not right:
        raise ValueError("both exports must contain sessions")
    texts = [clean_text(row["summary"]) for row in left + right]
    vectors = post_embed(endpoint, texts)
    left_vectors = vectors[: len(left)]
    right_vectors = vectors[len(left) :]
    rows: list[dict[str, Any]] = []
    lexical_top: Counter[str] = Counter()
    dense_top: Counter[str] = Counter()
    top_overlap = 0
    top5_jaccard: list[float] = []
    lexical_scores: list[float] = []
    dense_scores: list[float] = []
    for left_index, left_row in enumerate(left):
        lexical_order = sorted(range(len(right)), key=lambda index: (-set_cosine(left_row["terms"], right[index]["terms"]), right[index]["id"]))
        dense_order = sorted(range(len(right)), key=lambda index: (-vector_cosine(left_vectors[left_index], right_vectors[index]), right[index]["id"]))
        lexical_indices = lexical_order[:top_k]
        dense_indices = dense_order[:top_k]
        lexical_top_hash = pair_hash(left_row, right[lexical_indices[0]])
        dense_top_hash = pair_hash(left_row, right[dense_indices[0]])
        lexical_top[lexical_top_hash] += 1
        dense_top[dense_top_hash] += 1
        top_overlap += int(lexical_top_hash == dense_top_hash)
        lexical_scores.append(set_cosine(left_row["terms"], right[lexical_indices[0]]["terms"]))
        dense_scores.append(vector_cosine(left_vectors[left_index], right_vectors[dense_indices[0]]))
        lexical_set = {pair_hash(left_row, right[index]) for index in lexical_indices}
        dense_set = {pair_hash(left_row, right[index]) for index in dense_indices}
        top5_jaccard.append(len(lexical_set & dense_set) / max(1, len(lexical_set | dense_set)))
        rows.append({
            "left_session_hash": hashlib.sha256(left_row["id"].encode()).hexdigest(),
            "lexical_top_pair_hash": lexical_top_hash,
            "dense_top_pair_hash": dense_top_hash,
            "lexical_top_tool_jaccard": len(left_row["tools"] & right[lexical_indices[0]]["tools"]) / max(1, len(left_row["tools"] | right[lexical_indices[0]]["tools"])),
            "dense_top_tool_jaccard": len(left_row["tools"] & right[dense_indices[0]]["tools"]) / max(1, len(left_row["tools"] | right[dense_indices[0]]["tools"])),
            "lexical_top_score": round(lexical_scores[-1], 6),
            "dense_top_score": round(dense_scores[-1], 6),
            "top_k_set_jaccard": round(top5_jaccard[-1], 6),
        })
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source": {"left_manifest_sha256": digest(sorted((path.name, path.stat().st_size) for path in left_path.parent.glob("*.jsonl"))), "right_manifest_sha256": digest(sorted((path.name, path.stat().st_size) for path in right_path.parent.glob("*.jsonl"))), "left_session_count": len(left), "right_session_count": len(right), "raw_content_committed": False, "external_model_calls": False},
        "protocol": {"candidate_generators": ["cleaned lexical term cosine", "local Nomic embedding cosine"], "embedding_endpoint": endpoint, "embedding_model": EMBED_MODEL, "top_k": top_k, "session_text_stays_local": True, "semantic_adjudication": False},
        "aggregate": {"queries": len(rows), "candidate_pool": len(right), "top1_generator_agreement_rate": round(top_overlap / len(rows), 6), "mean_lexical_top_score": round(sum(lexical_scores) / len(lexical_scores), 6), "mean_dense_top_score": round(sum(dense_scores) / len(dense_scores), 6), "mean_top_k_set_jaccard": round(sum(top5_jaccard) / len(top5_jaccard), 6), "lexical_unique_top_pair_count": len(lexical_top), "dense_unique_top_pair_count": len(dense_top), "lexical_top_pair_concentration": round(max(lexical_top.values()) / len(rows), 6), "dense_top_pair_concentration": round(max(dense_top.values()) / len(rows), 6), "mean_lexical_top_tool_jaccard": round(sum(float(row["lexical_top_tool_jaccard"]) for row in rows) / len(rows), 6), "mean_dense_top_tool_jaccard": round(sum(float(row["dense_top_tool_jaccard"]) for row in rows) / len(rows), 6)},
        "rows": rows,
        "claim_boundary": {"candidate_generation_measured": True, "cross_user_task_equivalence_established": False, "skill_gap_established": False, "enterprise_collaboration_value_established": False, "reason": "This is a local-only candidate-generation comparison over two public user exports. It has no independent task-equivalence labels, human outcomes, or external adjudication."},
    }
    result["result_sha256"] = digest(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"aggregate": result["aggregate"]}, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--left", type=Path, required=True)
    parser.add_argument("--right", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    run(args.left.resolve(), args.right.resolve(), args.output.resolve(), endpoint=args.endpoint, top_k=args.top_k)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
