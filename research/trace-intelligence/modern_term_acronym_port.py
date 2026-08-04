#!/usr/bin/env python3
"""Current-Python ports of two legacy vocabulary concepts.

This is intentionally a concept port, not a claim of byte-for-byte equivalence
to TermSuite or AcronymExpansion. It uses standard-library tokenization,
foreground/background termhood, variant normalization, and contextual acronym
definition extraction so the contracts can be tested without obsolete POS or
Doc2Vec dependencies.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any


TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9@_./:-]{1,}")
ACRONYM_RE = re.compile(r"\b[A-Z][A-Z0-9-]{1,9}\b")
STOP = {
    "a", "an", "and", "are", "as", "at", "by", "for", "from", "in", "into",
    "is", "it", "of", "on", "or", "the", "to", "with", "using", "used", "this",
    "that", "these", "those", "be", "can", "does", "do", "not", "than", "then",
}


def stable_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def strings_from_content(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        output: list[str] = []
        for item in value:
            if isinstance(item, str):
                output.append(item)
            elif isinstance(item, dict):
                for key in ("text", "content", "input", "output"):
                    if isinstance(item.get(key), str):
                        output.append(item[key])
        return output
    if isinstance(value, dict):
        return [value[key] for key in ("text", "content", "input", "output") if isinstance(value.get(key), str)]
    return []


def record_text(record: dict[str, Any]) -> str:
    message = record.get("message")
    if isinstance(message, dict):
        values = strings_from_content(message.get("content"))
        if values:
            return "\n".join(values)
    for key in ("content", "lastPrompt", "result"):
        values = strings_from_content(record.get(key))
        if values:
            return "\n".join(values)
    return ""


def load_wisp(root: Path) -> list[str]:
    documents: list[str] = []
    for path in sorted(root.rglob("*.jsonl")):
        rows: list[str] = []
        for line in path.read_bytes().splitlines():
            try:
                value = record_text(json.loads(line))
            except (json.JSONDecodeError, TypeError):
                continue
            if value:
                rows.append(value)
        if rows:
            documents.append("\n".join(rows))
    return documents


def tokens(text: str) -> list[str]:
    return [item.lower() for item in TOKEN_RE.findall(text)]


def canonical(term: str) -> str:
    value = re.sub(r"[-_/]+", " ", term.lower())
    value = re.sub(r"\s+", " ", value).strip()
    words = value.split()
    if words and len(words[-1]) > 4 and words[-1].endswith("s"):
        words[-1] = words[-1][:-1]
    return " ".join(words)


def termhood(foreground: list[str], background: list[str], limit: int = 3000) -> list[dict[str, Any]]:
    fg_df: collections.Counter[str] = collections.Counter()
    bg_df: collections.Counter[str] = collections.Counter()
    fg_tf: collections.Counter[str] = collections.Counter()
    for text, target in [(value, fg_df) for value in foreground] + [(value, bg_df) for value in background]:
        words = tokens(text)
        seen: set[str] = set()
        for n in range(1, 5):
            for index in range(0, len(words) - n + 1):
                phrase = words[index:index + n]
                if phrase[0] in STOP or phrase[-1] in STOP or not any(len(word) > 2 for word in phrase):
                    continue
                item = " ".join(phrase)
                seen.add(item)
                if target is fg_df:
                    fg_tf[item] += 1
        target.update(seen)
    scored: list[tuple[float, str]] = []
    fg_docs = max(1, len(foreground))
    bg_docs = max(1, len(background))
    for item, count in fg_df.items():
        fg_rate = (count + 1) / (fg_docs + 1)
        bg_rate = (bg_df.get(item, 0) + 1) / (bg_docs + 1)
        score = math.log(fg_rate / bg_rate) + 0.05 * math.log1p(fg_tf[item])
        scored.append((score, item))
    scored.sort(key=lambda pair: (-pair[0], pair[1]))
    output: list[dict[str, Any]] = []
    grouped: dict[str, list[str]] = collections.defaultdict(list)
    for score, item in scored[:limit]:
        grouped[canonical(item)].append(item)
        output.append({
            "term_hash": stable_hash(item),
            "canonical_hash": stable_hash(canonical(item)),
            "score_bucket": "positive" if score > 0 else "nonpositive",
            "foreground_df": fg_df[item],
            "background_df": bg_df.get(item, 0),
        })
    for row, (_, item) in zip(output, scored[:limit]):
        row["variant_count"] = len(grouped[canonical(item)])
    return output


def acronym_initials(phrase: str) -> str:
    letters: list[str] = []
    for word in TOKEN_RE.findall(phrase.lower()):
        for part in word.split("-"):
            if part and part not in STOP:
                letters.append(part[0])
    return "".join(letters)


def acronym_definitions(text: str) -> dict[str, list[dict[str, Any]]]:
    found: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    patterns = [
        re.compile(r"(?P<full>[A-Za-z][A-Za-z0-9-]*(?:\s+[A-Za-z][A-Za-z0-9-]*){0,9})\s*\((?P<abbr>[A-Z][A-Z0-9-]{1,9})\)"),
        re.compile(r"\b(?P<abbr>[A-Z][A-Z0-9-]{1,9})\s*\((?P<full>[A-Za-z][A-Za-z0-9-]*(?:\s+[A-Za-z][A-Za-z0-9-]*){0,9})\)"),
    ]
    for pattern in patterns:
        for match in pattern.finditer(text):
            full = " ".join(match.group("full").split())
            abbr = match.group("abbr")
            initials = acronym_initials(full)
            letters = re.sub(r"[^a-z]", "", abbr.lower())
            if initials == letters or (len(letters) >= 2 and letters in initials):
                found[abbr].append({"full_hash": stable_hash(full), "match": True})
            else:
                found[abbr].append({"full_hash": stable_hash(full), "match": False})
    return dict(found)


def synthetic_probe() -> dict[str, Any]:
    cases = [
        ("row-level security (RLS) protects the governed table", "RLS", True),
        ("authorization epoch reference (AER) is required", "AER", True),
        ("retrieval augmented generation (RAG) is a common pattern", "RAG", True),
        ("semantic cache authority gate (SCAG) denies stale lookups", "SCAG", True),
        ("the platform emits RLS in a log with no definition", "RLS", False),
        ("RLS (row-level security) is documented here", "RLS", True),
        ("schema fingerprint (SF) is old; scope filter (SF) is new", "SF", False),
        ("MCP tool calls are recorded without a full-form definition", "MCP", False),
    ]
    hits = 0
    details = []
    for text, acronym, expected in cases:
        rows = acronym_definitions(text).get(acronym, [])
        valid = [row for row in rows if row["match"]]
        abstained = len({row["full_hash"] for row in valid}) != 1
        hit = (len(valid) == 1 and not abstained) if expected else (len(valid) == 0 or abstained)
        hits += int(hit)
        details.append({"text_hash": stable_hash(text), "acronym": acronym, "expected": expected, "hit": hit, "candidate_count": len(valid)})
    return {"cases": len(cases), "hits": hits, "details": details}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-docs", type=int, default=49)
    args = parser.parse_args()
    docs = load_wisp(args.corpus_root)[:args.max_docs]
    split = len(docs) // 2
    candidates = termhood(docs[:split], docs[split:])
    result = {
        "schema_version": "frankengate-modern-term-acronym-port-v1",
        "dataset": {
            "dataset_id": "crispwisp/wisp-claude-code-sessions",
            "dataset_revision": "c2c90b59174318ab0b163ec9c9ac82bb879288ce",
            "document_count": len(docs),
            "foreground_count": split,
            "background_count": len(docs) - split,
        },
        "termhood_port": {
            "concept": "TermSuite/Termolator-style foreground-background termhood plus normalized variant groups",
            "candidate_count": len(candidates),
            "positive_score_count": sum(row["score_bucket"] == "positive" for row in candidates),
            "top_term_hashes": [row["term_hash"] for row in candidates[:100]],
        },
        "acronym_port": {
            "concept": "AcronymExpansion-style contextual full-form extraction with ambiguity abstention",
            "synthetic_probe": synthetic_probe(),
        },
        "claim_boundary": {
            "legacy_equivalence_established": False,
            "enterprise_quality_established": False,
            "retrieval_impact_evaluated": False,
            "raw_text_committed": False,
            "reason": "Current-Python concept port on a public single-contributor corpus; it is not byte-for-byte equivalence or enterprise label quality.",
        },
    }
    result["result_sha256"] = stable_hash(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"documents": len(docs), "candidates": len(candidates), "acronym_probe": result["acronym_port"]["synthetic_probe"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
