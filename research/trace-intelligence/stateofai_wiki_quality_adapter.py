#!/usr/bin/env python3
"""Build a quality-filtered State of AI wiki benchmark with silver labels.

The source export is a curation/index corpus, not a hand-authored QA dataset.
This adapter keeps records with usable titles, issuers, and summaries, then
generates deterministic identity/paraphrase/NIL questions. Every generated
question carries label provenance so it cannot be mistaken for human review.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlparse
from typing import Any


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "unknown"


def load_export(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    return json.loads(text.split("=", 1)[1].strip().rstrip(";"))


def usable(source: dict[str, Any]) -> bool:
    title = str(source.get("title") or "").strip()
    summary = str(source.get("summary") or "").strip()
    issuer = str(source.get("issuer") or "").strip()
    family = str(source.get("source_family") or "").strip()
    return bool(title and summary and issuer and family and len(summary) >= 120 and not title.lower().startswith(("http://", "https://")) and family != "public_source_cache")


def source_text(source: dict[str, Any]) -> str:
    fields = [
        source.get("title", ""),
        source.get("issuer", ""),
        source.get("summary", ""),
        source.get("source_family", ""),
        source.get("category", ""),
        source.get("evidence_level", ""),
        source.get("freshness", ""),
        source.get("published_date", ""),
    ]
    return " ".join(str(value) for value in fields if value)


def title_tokens(title: str) -> set[str]:
    return {token.lower() for token in re.findall(r"[a-z0-9]+", title) if len(token) > 2}


def nearest_same_domain(index: int, records: list[dict[str, Any]]) -> str | None:
    target = title_tokens(str(records[index].get("title", "")))
    candidates: list[tuple[float, str]] = []
    for other_index, other in enumerate(records):
        if other_index == index:
            continue
        other_tokens = title_tokens(str(other.get("title", "")))
        overlap = len(target & other_tokens) / max(1, len(target | other_tokens))
        candidates.append((-overlap, str(other.get("id", ""))))
    return min(candidates)[1] if candidates else None


def adapt(data: dict[str, Any], top_domains: int = 10, per_domain: int = 40) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for source in data.get("sources", []):
        if not usable(source):
            continue
        host = urlparse(str(source.get("url", ""))).netloc.lower()
        if host:
            grouped[host].append(source)
    ranked_domains = sorted(grouped, key=lambda host: (-len(grouped[host]), host))[:top_domains]
    pages: list[dict[str, Any]] = []
    questions: list[dict[str, Any]] = []
    for host in ranked_domains:
        wiki_id = f"quality:{slug(host)}"
        records = sorted(grouped[host], key=lambda row: str(row.get("id", "")))[:per_domain]
        by_source_id = {str(row.get("id")): f"{wiki_id}/{slug(str(row.get('id')))}" for row in records}
        for source in records:
            source_id = str(source.get("id"))
            pages.append({
                "page_id": by_source_id[source_id],
                "wiki_id": wiki_id,
                "title": str(source.get("title")),
                "aliases": [value for value in [str(source.get("issuer") or ""), str(source.get("source_family") or ""), source_id] if value],
                "text": source_text(source),
                "links": [],
                "source_id": source_id,
                "source_domain": host,
                "issuer": str(source.get("issuer") or ""),
                "source_family": str(source.get("source_family") or ""),
                "published_date": str(source.get("published_date") or ""),
            })
        for index, source in enumerate(records):
            source_id = str(source.get("id"))
            page_id = by_source_id[source_id]
            title = str(source.get("title"))
            issuer = str(source.get("issuer"))
            family = str(source.get("source_family"))
            hard_negative_source = nearest_same_domain(index, records)
            hard_negative = [by_source_id[hard_negative_source]] if hard_negative_source else []
            base = {"wiki_id": wiki_id, "gold_page_ids": [page_id], "label_provenance": "deterministic_template_from_source_metadata", "hard_negative_page_ids": hard_negative}
            questions.extend([
                {**base, "question_id": f"{slug(host)}-{slug(source_id)}-exact", "slice": "exact_title", "question": f'Find the source titled "{title}".'},
                {**base, "question_id": f"{slug(host)}-{slug(source_id)}-paraphrase", "slice": "title_paraphrase", "question": f"Which document discusses {title}?"},
                {**base, "question_id": f"{slug(host)}-{slug(source_id)}-issuer", "slice": "issuer_title", "question": f'What {issuer} source is named "{title}"?'},
                {**base, "question_id": f"{slug(host)}-{slug(source_id)}-id", "slice": "exact_identifier", "question": f"Retrieve source record {source_id}."},
                {**base, "question_id": f"{slug(host)}-{slug(source_id)}-family", "slice": "family_title", "question": f'Find the {family} item from {issuer} called "{title}".'},
            ])
    nils = [
        ("nil-unknown-id", "Retrieve source record public-source:nonexistent.example:artifact:deadbeef."),
        ("nil-unknown-title", "Which document is titled Zeta-99 Enterprise Deployment Playbook?"),
        ("nil-unknown-issuer", "Find the source from Nonexistent Holdings about a nonexistent system."),
        ("nil-unknown-family", "Show the nonexistent quantum-ledger source family record."),
        ("nil-unknown-domain", "Which source proves the deployment window for the nonexistent Zeta-99 system?"),
    ]
    questions.extend({"question_id": question_id, "wiki_id": None, "slice": "nil", "question": question, "gold_page_ids": [], "label_provenance": "deterministic_negative_template", "hard_negative_page_ids": []} for question_id, question in nils)
    return {
        "schema_version": "frankengate-stateofai-quality-wiki-v1",
        "source": {"domains": ranked_domains, "quality_records": sum(len(grouped[host]) for host in ranked_domains), "source_count": len(data.get("sources", []))},
        "pages": pages,
        "questions": questions,
        "claim_boundary": "Silver identity/paraphrase/NIL labels generated from source metadata; not human-reviewed answer labels.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--domains", type=int, default=10)
    parser.add_argument("--per-domain", type=int, default=40)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = adapt(load_export(args.input), args.domains, args.per_domain)
    result["source"]["input_sha256"] = sha256(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"schema_version": result["schema_version"], "domains": len(result["source"]["domains"]), "pages": len(result["pages"]), "questions": len(result["questions"]), "quality_records": result["source"]["quality_records"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
