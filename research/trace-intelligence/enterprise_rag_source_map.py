#!/usr/bin/env python3
"""Build a small indexed source-type map beside an EnterpriseRAG FTS DB."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-enterprise-rag-source-map-v1"


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def build(source_database: Path, output_database: Path, output_receipt: Path, batch_size: int = 8192) -> dict[str, Any]:
    source = sqlite3.connect(f"file:{source_database}?mode=ro", uri=True)
    destination = sqlite3.connect(output_database)
    try:
        destination.executescript("""
            PRAGMA journal_mode=OFF;
            PRAGMA synchronous=OFF;
            CREATE TABLE IF NOT EXISTS doc_sources(
                doc_rowid INTEGER PRIMARY KEY,
                source_type TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS doc_sources_source_type ON doc_sources(source_type);
        """)
        destination.execute("DELETE FROM doc_sources")
        count = 0
        cursor = source.execute("SELECT rowid, source_type FROM docs ORDER BY rowid")
        while True:
            rows = cursor.fetchmany(batch_size)
            if not rows:
                break
            destination.executemany("INSERT INTO doc_sources(doc_rowid, source_type) VALUES (?, ?)", rows)
            destination.commit()
            count += len(rows)
        result = {
            "schema_version": SCHEMA_VERSION,
            "source": {"source_database_sha256": file_sha256(source_database), "raw_document_content_committed": False},
            "map": {"rows": count, "source_types_indexed": True, "source_database_read_only": True},
            "claim_boundary": {"source_map_built": True, "authorization_measured": False, "semantic_labels_established": False},
        }
        result["result_sha256"] = stable_hash(result)
        output_receipt.parent.mkdir(parents=True, exist_ok=True)
        output_receipt.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(result["map"], sort_keys=True))
        return result
    finally:
        source.close()
        destination.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-database", type=Path, required=True)
    parser.add_argument("--output-database", type=Path, required=True)
    parser.add_argument("--output-receipt", type=Path, required=True)
    args = parser.parse_args()
    build(args.source_database, args.output_database, args.output_receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
