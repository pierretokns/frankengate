#!/usr/bin/env python3
"""Adapt the local State of AI wiki export to the wiki benchmark contract.

Only the generated corpus manifest and hashes are committed; source bodies and
URLs remain in the local export. The adapter treats top source domains as
separate knowledge collections so the 1/5/10/25 scale study is reproducible.
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
    marker = "="
    if marker not in text:
        raise ValueError("expected a window.* = JSON export")
    return json.loads(text.split(marker, 1)[1].strip().rstrip(";"))


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


def adapt(data: dict[str, Any], top_domains: int = 25, per_domain: int = 80) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for source in data.get("sources", []):
        host = urlparse(str(source.get("url", ""))).netloc.lower()
        if host:
            grouped[host].append(source)
    domains = [host for host, _ in Counter({host: len(rows) for host, rows in grouped.items()}).most_common(top_domains)]
    pages: list[dict[str, Any]] = []
    questions: list[dict[str, Any]] = []
    for host in domains:
        wiki_id = f"domain:{slug(host)}"
        records = sorted(grouped[host], key=lambda row: str(row.get("id", "")))[:per_domain]
        ids = [str(row.get("id")) for row in records]
        for index, source in enumerate(records):
            page_id = f"{wiki_id}/{slug(str(source.get('id') or index))}"
            links = []
            if len(ids) > 1:
                links = [f"{wiki_id}/{slug(ids[(index + 1) % len(ids)])}"]
            pages.append({
                "page_id": page_id,
                "wiki_id": wiki_id,
                "title": str(source.get("title") or source.get("id") or "untitled"),
                "aliases": [str(value) for value in (source.get("issuer"), source.get("source_family"), source.get("id")) if value],
                "text": source_text(source),
                "links": links,
                "source_id": str(source.get("id")),
                "source_domain": host,
            })
        by_id = {str(source.get("id")): f"{wiki_id}/{slug(str(source.get('id')))}" for source in records}
        for source in records[:4]:
            source_id = str(source.get("id"))
            page_id = by_id[source_id]
            title = str(source.get("title") or source_id)
            issuer = str(source.get("issuer") or host)
            questions.extend(
                [
                    {"question_id": f"{slug(host)}-{slug(source_id)}-title", "wiki_id": wiki_id, "slice": "exact_title", "question": f"Which source record is titled {title}?", "gold_page_ids": [page_id]},
                    {"question_id": f"{slug(host)}-{slug(source_id)}-issuer", "wiki_id": wiki_id, "slice": "issuer_title", "question": f"Find the {issuer} record named {title}.", "gold_page_ids": [page_id]},
                    {"question_id": f"{slug(host)}-{slug(source_id)}-id", "wiki_id": wiki_id, "slice": "exact_identifier", "question": f"Retrieve source record {source_id}.", "gold_page_ids": [page_id]},
                ]
            )
    questions.append({"question_id": "stateofai-nil-nonexistent-domain", "wiki_id": None, "slice": "nil", "question": "Which source record proves the nonexistent Zeta-99 system deployment window?", "gold_page_ids": []})
    return {
        "schema_version": "frankengate-stateofai-wiki-corpus-v1",
        "source": {"domains": domains, "source_count": len(data.get("sources", [])), "pages_exported": len(data.get("pages", []))},
        "pages": pages,
        "questions": questions,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--domains", type=int, default=25)
    parser.add_argument("--per-domain", type=int, default=80)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = load_export(args.input)
    result = adapt(data, top_domains=args.domains, per_domain=args.per_domain)
    result["source"]["input_sha256"] = sha256(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"schema_version": result["schema_version"], "domains": len(result["source"]["domains"]), "pages": len(result["pages"]), "questions": len(result["questions"]), "input_sha256": result["source"]["input_sha256"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
