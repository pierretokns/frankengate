#!/usr/bin/env python3
"""Benchmark identifier-aware retrieval on pinned NL2SQL rows.

This is a conservative, executable hard-negative study. A row contributes a
positive only when a question surface and a gold-SQL identifier agree under
the existing exact morphology rule. Identifiers with the same normalized
surface in another database are hard negatives. The benchmark therefore
measures collision resolution, not semantic alias discovery.

Raw questions, SQL, and identifiers remain external; the committed receipt is
aggregate/hash-only. Embeddings are optional and use a loopback Ollama model.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib import request

from nl2sql_alias_mining import canonical_identifiers, normalize, surface_tokens


SCHEMA_VERSION = "frankengate-nl2sql-identifier-hard-negative-benchmark-v1"
MODEL = "nomic-embed-text:latest"
TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def char_ngrams(value: str, n: int = 3) -> set[str]:
    normalized = " ".join(TOKEN_RE.findall(value.lower()))
    padded = f"  {normalized}  "
    return {padded[index:index + n] for index in range(max(0, len(padded) - n + 1))}


def jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def lexical_score(query: str, candidate: str) -> float:
    return 0.5 * jaccard(set(TOKEN_RE.findall(query.lower())), set(TOKEN_RE.findall(candidate.lower()))) + 0.5 * jaccard(char_ngrams(query), char_ngrams(candidate))


def post_json(endpoint: str, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        endpoint.rstrip("/") + "/api/embed",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=180) as response:
        return json.loads(response.read().decode("utf-8"))


def embed_unique(texts: Sequence[str], endpoint: str, batch_size: int) -> dict[str, list[float]]:
    result: dict[str, list[float]] = {}
    unique = list(dict.fromkeys(texts))
    for start in range(0, len(unique), batch_size):
        batch = unique[start:start + batch_size]
        payload = post_json(endpoint, {"model": MODEL, "input": batch, "truncate": True})
        vectors = payload.get("embeddings")
        if not isinstance(vectors, list) or len(vectors) != len(batch):
            raise RuntimeError("embedding response count mismatch")
        for text, vector in zip(batch, vectors):
            if not isinstance(vector, list) or not vector:
                raise RuntimeError("empty embedding vector")
            result[text] = [float(value) for value in vector]
    return result


def cosine(left: Sequence[float], right: Sequence[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    return dot / (left_norm * right_norm) if left_norm and right_norm else 0.0


def _ranked_metrics(
    links: Sequence[Mapping[str, str]],
    candidates: Sequence[tuple[str, str]],
    score_fn: Any,
    *,
    filter_db: bool,
) -> dict[str, Any]:
    reciprocal: list[float] = []
    top1: list[float] = []
    top5: list[float] = []
    collision_before_target: list[float] = []
    eligible = 0
    for link in links:
        target = (link["db"], link["identifier"])
        pool = [candidate for candidate in candidates if not filter_db or candidate[0] == link["db"]]
        if target not in pool:
            continue
        eligible += 1
        query = link["question"]
        ranked = sorted(
            ((float(score_fn(query, candidate[0], candidate[1])), candidate) for candidate in pool),
            key=lambda item: (-item[0], item[1]),
        )
        position = next(index for index, (_, candidate) in enumerate(ranked, start=1) if candidate == target)
        reciprocal.append(1.0 / position)
        top1.append(float(position == 1))
        top5.append(float(position <= 5))
        hard = normalize(link["identifier"])
        collision_before_target.append(
            float(any(candidate != target and normalize(candidate[1]) == hard and index < position for index, (_, candidate) in enumerate(ranked, start=1)))
        )
    return {
        "eligible_links": eligible,
        "mrr": round(sum(reciprocal) / len(reciprocal), 6) if reciprocal else 0.0,
        "recall_at_1": round(sum(top1) / len(top1), 6) if top1 else 0.0,
        "recall_at_5": round(sum(top5) / len(top5), 6) if top5 else 0.0,
        "hard_negative_before_target_rate": round(sum(collision_before_target) / len(collision_before_target), 6) if collision_before_target else 0.0,
    }


def run(
    sources: Sequence[Path],
    *,
    endpoint: str,
    batch_size: int,
    with_embeddings: bool,
) -> dict[str, Any]:
    rows: list[dict[str, str]] = []
    source_hashes: dict[str, str] = {}
    for source in sources:
        payload = source.read_bytes()
        source_hashes[source.name] = hashlib.sha256(payload).hexdigest()
        with source.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                row["_source"] = source.name
                rows.append(row)

    candidates_set: set[tuple[str, str]] = set()
    links: list[dict[str, str]] = []
    seen_links: set[tuple[str, str, str, str]] = set()
    for row_index, row in enumerate(rows):
        db = row.get("db_name", "")
        identifiers = canonical_identifiers(row.get("query", ""))
        candidates_set.update((db, identifier) for identifier in identifiers)
        by_normalized: dict[str, set[str]] = defaultdict(set)
        for identifier in identifiers:
            by_normalized[normalize(identifier)].add(identifier)
        for surface in surface_tokens(row.get("question", "")):
            for identifier in by_normalized.get(normalize(surface), set()):
                key = (db, surface, identifier, str(row_index))
                if key in seen_links:
                    continue
                seen_links.add(key)
                links.append({
                    "db": db,
                    "surface": surface,
                    "identifier": identifier,
                    "question": row.get("question", ""),
                })
    candidates = sorted(candidates_set)

    def surface_exact(query: str, db: str, identifier: str) -> float:
        surfaces = surface_tokens(query)
        return float(any(normalize(surface) == normalize(identifier) for surface in surfaces))

    def db_char(query: str, db: str, identifier: str) -> float:
        # The known source database is structured metadata, not inferred text.
        return lexical_score(f"database {db} question {query}", f"database {db} identifier {identifier}")

    arms: dict[str, Any] = {
        "surface_exact_unfiltered": _ranked_metrics(links, candidates, surface_exact, filter_db=False),
        "surface_exact_db_filtered": _ranked_metrics(links, candidates, surface_exact, filter_db=True),
        "chargram_db_filtered": _ranked_metrics(links, candidates, db_char, filter_db=True),
    }
    embedding_meta: dict[str, Any] = {"status": "not_run"}
    if with_embeddings:
        query_texts = [f"database {link['db']} question {link['question']}" for link in links]
        candidate_texts = [f"database {db} identifier {identifier}" for db, identifier in candidates]
        vectors = embed_unique(query_texts + candidate_texts, endpoint, batch_size)
        query_vectors = {link["question"] + "\u0000" + link["db"]: vectors[text] for link, text in zip(links, query_texts)}
        candidate_vectors = {candidate: vectors[text] for candidate, text in zip(candidates, candidate_texts)}

        def embedding_score(query: str, db: str, identifier: str) -> float:
            return cosine(query_vectors[query + "\u0000" + db], candidate_vectors[(db, identifier)])

        arms["embedding_db_filtered"] = _ranked_metrics(links, candidates, embedding_score, filter_db=True)
        embedding_meta = {"status": "completed", "endpoint": endpoint, "model": MODEL, "dimension": len(next(iter(vectors.values()))) if vectors else 0}

    cross_scope_collisions = 0
    normalized_to_dbs: dict[str, set[str]] = defaultdict(set)
    for db, identifier in candidates:
        normalized_to_dbs[normalize(identifier)].add(db)
    cross_scope_collisions = sum(len(dbs) > 1 for dbs in normalized_to_dbs.values())
    return {
        "schema_version": SCHEMA_VERSION,
        "sources": {"rows": len(rows), "files": source_hashes, "raw_content_committed": False},
        "corpus": {"candidate_identifiers": len(candidates), "links": len(links), "cross_scope_collision_classes": cross_scope_collisions},
        "protocol": {
            "positive_definition": "question surface and gold SQL identifier agree under exact morphology normalization",
            "hard_negative_definition": "same normalized identifier surface in another database scope",
            "held_out": "none; this is a collision-resolution baseline, not a generalization estimate",
            "embedding_model": embedding_meta,
        },
        "arms": arms,
        "claim_boundary": "Measures conservative identifier collision retrieval only. It does not establish semantic alias truth, corporate terminology quality, or changed-agent utility; frontier/SME labels and family-held-out replay remain required.",
        "result_sha256": digest(arms),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, action="append", required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--with-embeddings", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.source, endpoint=args.endpoint, batch_size=args.batch_size, with_embeddings=args.with_embeddings)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "ok", "links": result["corpus"]["links"], "embedding": result["protocol"]["embedding_model"]["status"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
