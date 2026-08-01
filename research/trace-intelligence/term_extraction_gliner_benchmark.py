#!/usr/bin/env python3
"""Run a content-minimized GLiNER and deterministic vocabulary probe.

The raw Wisp transcript and extracted strings remain outside Git.  The committed
receipt contains hashes, counts, aggregate score buckets, and a fixed synthetic
capability probe; it never stores prompt text or candidate term strings.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import re
from pathlib import Path
from typing import Any


STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "have",
    "what", "when", "where", "which", "please", "need", "want", "use",
    "could", "would", "should", "about", "then", "than", "your", "you",
    "our", "their", "there", "just", "also", "only", "does", "how",
}
WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_./:-]{2,}")
ACRONYM_RE = re.compile(r"\b[A-Z][A-Z0-9]{1,7}\b")

LABELS = [
    "internal system",
    "project",
    "metric",
    "acronym",
    "legacy term",
    "database",
    "tool",
    "business process",
]

PROBES = [
    ("Aurora", "internal system"),
    ("Mantle", "internal system"),
    ("Project Northstar", "project"),
    ("Recall@20", "metric"),
    ("RLS", "acronym"),
    ("legacy Atlas", "legacy term"),
    ("PostgreSQL", "database"),
    ("semantic cache", "tool"),
]


def stable_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def strings_from_content(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            if isinstance(item, str):
                out.append(item)
            elif isinstance(item, dict):
                for key in ("text", "content", "input", "output"):
                    if isinstance(item.get(key), str):
                        out.append(item[key])
        return out
    if isinstance(value, dict):
        out = []
        for key in ("text", "content", "input", "output"):
            if isinstance(value.get(key), str):
                out.append(value[key])
        return out
    return []


def record_text(record: dict[str, Any]) -> tuple[str, str | None]:
    role = None
    message = record.get("message")
    if isinstance(message, dict):
        role = message.get("role") if isinstance(message.get("role"), str) else None
        content = strings_from_content(message.get("content"))
        if content:
            return "\n".join(content), role
    for key in ("content", "lastPrompt", "result"):
        content = strings_from_content(record.get(key))
        if content:
            return "\n".join(content), role
    return "", role


def load_documents(root: Path, max_docs: int | None) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*.jsonl")):
        if max_docs is not None and len(docs) >= max_docs:
            break
        texts: list[str] = []
        user_messages: list[str] = []
        try:
            for line in path.read_bytes().splitlines():
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                text, role = record_text(record)
                if text:
                    texts.append(text)
                    if role == "user":
                        user_messages.append(text)
        except OSError:
            continue
        if texts:
            docs.append(
                {
                    "path_hash": hashlib.sha256(str(path.relative_to(root)).encode()).hexdigest(),
                    "text": "\n".join(texts),
                    "user_messages": user_messages,
                }
            )
    return docs


def deterministic_terms(docs: list[dict[str, Any]]) -> dict[str, Any]:
    df: collections.Counter[str] = collections.Counter()
    tf: collections.Counter[str] = collections.Counter()
    acronym_counts: collections.Counter[str] = collections.Counter()
    reformulations = 0
    for doc in docs:
        words = [word.lower() for word in WORD_RE.findall(doc["text"])]
        filtered = [word for word in words if word not in STOPWORDS and len(word) > 3]
        tf.update(filtered)
        df.update(set(filtered))
        acronym_counts.update(ACRONYM_RE.findall(doc["text"]))
        messages = doc["user_messages"]
        for first, second in zip(messages, messages[1:]):
            first_set = set(x.lower() for x in WORD_RE.findall(first))
            second_set = set(x.lower() for x in WORD_RE.findall(second))
            if first_set and second_set:
                overlap = len(first_set & second_set) / max(1, len(first_set | second_set))
                if overlap >= 0.25 and first_set != second_set:
                    reformulations += 1
    top_terms = sorted(df, key=lambda item: (-df[item], -tf[item], item))[:100]
    term_hashes = [stable_hash(term) for term in top_terms]
    return {
        "document_count": len(docs),
        "unique_term_count": len(df),
        "top_term_hashes": term_hashes,
        "top_term_document_frequency": [df[term] for term in top_terms],
        "acronym_count": len(acronym_counts),
        "top_acronym_hashes": [stable_hash(term) for term, _ in acronym_counts.most_common(50)],
        "reformulation_candidate_count": reformulations,
    }


def score_bucket(score: float) -> str:
    if score >= 0.8:
        return "0.8-1.0"
    if score >= 0.6:
        return "0.6-0.8"
    if score >= 0.4:
        return "0.4-0.6"
    return "<0.4"


def run_gliner(docs: list[dict[str, Any]], model_name: str, raw_output: Path | None) -> dict[str, Any]:
    from gliner import GLiNER

    model = GLiNER.from_pretrained(model_name)
    texts = [doc["text"][:5000] for doc in docs]
    predictions = model.batch_predict_entities(texts, LABELS, threshold=0.35, batch_size=4)
    raw_rows: list[dict[str, Any]] = []
    label_counts: collections.Counter[str] = collections.Counter()
    score_buckets: collections.Counter[str] = collections.Counter()
    term_hashes: collections.Counter[str] = collections.Counter()
    for doc, entities in zip(docs, predictions):
        for entity in entities:
            label = str(entity.get("label", ""))
            text = str(entity.get("text", ""))
            score = float(entity.get("score", 0.0))
            label_counts[label] += 1
            score_buckets[score_bucket(score)] += 1
            term_hashes[stable_hash(text.lower())] += 1
            raw_rows.append(
                {
                    "path_hash": doc["path_hash"],
                    "label": label,
                    "text": text,
                    "score": score,
                }
            )
    if raw_output is not None:
        raw_output.parent.mkdir(parents=True, exist_ok=True)
        raw_output.write_text(json.dumps(raw_rows, ensure_ascii=False), encoding="utf-8")
    probe_hits: list[bool] = []
    probe_details: list[dict[str, Any]] = []
    probe_texts = [text for text, _ in PROBES]
    probe_expected = [label for _, label in PROBES]
    probe_predictions = model.batch_predict_entities(probe_texts, LABELS, threshold=0.35, batch_size=4)
    for text, expected, entities in zip(probe_texts, probe_expected, probe_predictions):
        hit = any(entity.get("label") == expected and text.lower() in str(entity.get("text", "")).lower() for entity in entities)
        probe_hits.append(hit)
        probe_details.append({"text_hash": stable_hash(text), "expected_label": expected, "hit": hit})
    return {
        "model": model_name,
        "entity_count": len(raw_rows),
        "unique_entity_hash_count": len(term_hashes),
        "label_counts": dict(sorted(label_counts.items())),
        "score_buckets": dict(sorted(score_buckets.items())),
        "top_entity_hashes": [item[0] for item in term_hashes.most_common(100)],
        "capability_probe": {
            "cases": len(PROBES),
            "hits": sum(probe_hits),
            "details": probe_details,
            "interpretation": "fixed synthetic capability probe, not enterprise quality",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--raw-output", type=Path)
    parser.add_argument("--model", default="urchade/gliner_base")
    parser.add_argument("--max-docs", type=int)
    args = parser.parse_args()
    docs = load_documents(args.corpus_root, args.max_docs)
    if not docs:
        raise SystemExit("no documents found")
    result = {
        "schema_version": "frankengate-term-extraction-gliner-benchmark-v1",
        "dataset": {
            "dataset_id": "crispwisp/wisp-claude-code-sessions",
            "dataset_revision": "c2c90b59174318ab0b163ec9c9ac82bb879288ce",
            "document_count": len(docs),
            "document_path_hash": stable_hash([doc["path_hash"] for doc in docs]),
        },
        "baseline": deterministic_terms(docs),
        "gliner": run_gliner(docs, args.model, args.raw_output),
        "claim_boundary": {
            "enterprise_term_quality_established": False,
            "retrieval_impact_evaluated": False,
            "raw_text_committed": False,
            "reason": "Public single-contributor Wisp corpus and fixed capability probe; candidate precision requires blinded labels and retrieval replay.",
        },
    }
    result["result_sha256"] = stable_hash(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"documents": len(docs), "entities": result["gliner"]["entity_count"], "probe": result["gliner"]["capability_probe"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
