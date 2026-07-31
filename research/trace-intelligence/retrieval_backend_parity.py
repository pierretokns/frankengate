#!/usr/bin/env python3
"""Produce a bounded retrieval/storage parity receipt.

This is intentionally not a benchmark of products for which no local runtime or
source-pinned corpus exists.  It joins the completed same-corpus E2/PostgreSQL
receipt with a capability probe for locally installed CASS and explicit null
receipts for unavailable Frankensearch, pg_textsearch, pgContext, TurboVec and
Turbopuffer.  A missing run is represented as ``None`` rather than a fabricated
zero, so the result can safely be used as an architecture gate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shutil
import subprocess
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parent
E2 = ROOT / "experiments/results/codetracebench-e2-authorized-retrieval-factorial-2026-07-30.json"
PG = ROOT / "experiments/results/codetracebench-e2-postgres-joint-retrieval-2026-07-30.json"
SCHEMA_VERSION = "frankengate-retrieval-backend-parity-v1"


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def load(path: pathlib.Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def probe_cass() -> dict[str, Any]:
    executable = shutil.which("cass")
    if not executable:
        return {"installed": False, "capability_receipt": None}
    proc = subprocess.run(
        [executable, "capabilities", "--json"],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    if proc.returncode:
        return {"installed": True, "capability_receipt": None, "exit_code": proc.returncode}
    parsed = json.loads(proc.stdout)
    commands = {str(item.get("name")) for item in parsed.get("commands", [])}
    features = parsed.get("features", {})
    return {
        "installed": True,
        "version": parsed.get("version"),
        "api_version": parsed.get("api_version"),
        "capability_receipt": {
            "commands": sorted(commands),
            "feature_keys": sorted(str(k) for k in features),
            "sha256": digest(proc.stdout.encode()),
        },
        "same_corpus_run": False,
        "reason": "CASS is installed, but its indexed corpus is not the pinned E2 corpus; no cross-corpus ranking claim is made.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--summary", type=pathlib.Path, required=True)
    args = parser.parse_args()

    e2 = load(E2)
    pg = load(PG)
    cohort = e2.get("cohort", {})
    pg_cohort = pg.get("cohort", {})
    systems: list[dict[str, Any]] = [
        {
            "system": "offline exact/structured/dense/hybrid",
            "kind": "reference",
            "same_corpus_run": True,
            "ranking": e2.get("arms"),
            "rls": None,
            "deletion": None,
            "verdict": "reference quality run; authorization is not evaluated offline",
        },
        {
            "system": "PostgreSQL FTS/trigram/pgvector",
            "kind": "relational",
            "same_corpus_run": True,
            "ranking": pg.get("arms"),
            "rls": pg.get("authorization_oracles"),
            "deletion": pg.get("deletion_oracles"),
            "verdict": "completed bounded local forced-RLS run; rejected as a hybrid replacement on this slice because quality and latency regressed",
        },
        {"system": "CASS", "kind": "local hybrid search", **probe_cass(), "verdict": "capability-only; same-corpus result unavailable"},
    ]
    for name, reason in (
        ("Frankensearch", "no local executable or source-pinned same-corpus adapter in this checkout"),
        ("pg_textsearch", "extension/package not installed and no source-pinned runtime receipt"),
        ("pgContext", "no source-pinned runtime or dependency receipt in this checkout"),
        ("TurboVec", "no source-pinned runtime or dependency receipt in this checkout"),
        ("Turbopuffer", "managed service requires an external account/network receipt; none was supplied"),
    ):
        systems.append({
            "system": name,
            "kind": "unrun",
            "same_corpus_run": False,
            "ranking": None,
            "rls": None,
            "deletion": None,
            "verdict": "null",
            "reason": reason,
        })

    result = {
        "schema_version": SCHEMA_VERSION,
        "analysis_revision": "retrieval-backend-parity-e2-v1",
        "corpus": {
            "documents": cohort.get("documents"),
            "queries": cohort.get("eligible_queries"),
            "dataset_revision": e2.get("dataset_revision"),
            "offline_result_sha256": digest(E2.read_bytes()),
            "postgres_result_sha256": digest(PG.read_bytes()),
        },
        "postgres_corpus": {
            "documents": pg_cohort.get("documents"),
            "queries": pg_cohort.get("eligible_queries"),
        },
        "systems": systems,
        "policy": {
            "missing_runs_are_null": True,
            "no_cross_corpus_quality_claim": True,
            "RLS_must_precede_ranking_and_snippet": True,
            "deletion_must_remove_authorized_candidates_and_derivatives": True,
        },
    }
    encoded = json.dumps(result, sort_keys=True, indent=2) + "\n"
    args.output.write_text(encoded)
    lines = [
        "# Retrieval backend parity (bounded)",
        "",
        f"Pinned cohort: {cohort.get('documents')} documents / {cohort.get('eligible_queries')} queries.",
        "",
        "Only offline ranking and the local forced-RLS PostgreSQL run have same-corpus evidence. CASS was capability-probed but its indexed corpus is not the pinned cohort. Frankensearch, pg_textsearch, pgContext, TurboVec, and Turbopuffer are explicit nulls, not zero scores.",
        "",
        "The PostgreSQL receipt carries the existing authorization/deletion oracles. It does not establish Aurora scale, selective-scope concurrency, or managed-service behavior.",
        "",
        "Architecture gate: retain PostgreSQL as policy/evidence authority; do not replace it with an unrun backend. A backend promotion requires the same corpus, exact-ID and semantic labels, pre-ranking authorization, deletion closure, latency, and cost receipts.",
        "",
        f"Result SHA256: `{digest(encoded.encode())}`",
    ]
    args.summary.write_text("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
