#!/usr/bin/env python3
"""Blind frontier adjudication of Oracle-style hard-negative candidates.

The distance inequalities only say that a candidate is close to a query and
farther from the selected positive.  This runner tests the missing question:
is the candidate actually relevant to the query (a false negative), merely a
near-miss, or unrelated?  Gold page IDs are never included in the judge
packet.  The committed receipt contains labels and hashes only; raw page text
stays in the local fixture and temporary Codex packets.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Sequence

from enterprise_hard_negative_paper_reproduction import (
    PAPER_EMBEDDING_MODELS,
    bounded_pages,
    fit_ensemble,
    mine_triplets,
)


LABELS = ["relevant_false_negative", "near_miss_hard_negative", "unrelated", "indeterminate"]
CONFIDENCES = ["high", "medium", "low"]
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["label", "confidence", "evidence_refs"],
    "properties": {
        "label": {"type": "string", "enum": LABELS},
        "confidence": {"type": "string", "enum": CONFIDENCES},
        "evidence_refs": {
            "type": "array",
            "items": {"type": "string", "enum": ["query", "positive", "candidate"]},
            "maxItems": 3,
        },
    },
}


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def stable_key(seed: int, value: str) -> str:
    return sha256_text(f"{seed}\0{value}")


def page_packet(page: dict[str, Any]) -> dict[str, str]:
    # Keep enough context for identifiers and the answer-bearing section while
    # bounding prompt size.  Gold IDs are intentionally not exposed here.
    text = str(page.get("text") or "")
    return {
        "title": str(page.get("title") or ""),
        "aliases": ", ".join(str(value) for value in (page.get("aliases") or [])),
        "text": text[:9000],
        "truncated": "true" if len(text) > 9000 else "false",
    }


def build_prompt(candidate: dict[str, Any]) -> str:
    return """You are an independent relevance adjudicator for hard-negative mining.

Use only the bounded query, selected positive source, and candidate source. Do
not execute tools, browse, infer hidden metadata, or use a page ID as evidence.
Preserve exact product names, versions, SQL/error identifiers, and scope. The
candidate is a valid hard-negative *geometric* candidate, but that does not
make it correct or incorrect semantically.

Choose exactly one label:
- relevant_false_negative: the candidate directly supports the same question,
  supplies another valid answer source, or is clearly a duplicate/relevant
  alternative that should not be used as a contrastive negative.
- near_miss_hard_negative: the candidate is meaningfully related and plausibly
  confusable, but does not directly answer the exact question.
- unrelated: the candidate does not materially support the question.
- indeterminate: the supplied excerpts are insufficient to decide.

Return JSON only. Cite one or more of query, positive, and candidate in
evidence_refs. Do not output prose or identify people, organizations, or
private information.

LABEL SCHEMA:
""" + json.dumps(SCHEMA, sort_keys=True) + "\n\nPACKET:\n" + json.dumps(
        {
            "query": candidate["query"],
            "positive": candidate["positive"],
            "candidate": candidate["candidate"],
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def parse_output(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if set(value) != set(SCHEMA["required"]):
        raise ValueError("response fields do not match schema")
    if value["label"] not in LABELS or value["confidence"] not in CONFIDENCES:
        raise ValueError("invalid label or confidence")
    refs = value["evidence_refs"]
    if not isinstance(refs, list) or not refs or len(refs) != len(set(refs)):
        raise ValueError("evidence_refs must be a non-empty unique list")
    if any(ref not in {"query", "positive", "candidate"} for ref in refs):
        raise ValueError("unknown evidence reference")
    return value


def adjudicate(candidate: dict[str, Any], model: str, timeout: int) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="frankengate-hard-negative-judge-") as directory:
        root = Path(directory)
        schema_path = root / "schema.json"
        output_path = root / "output.json"
        schema_path.write_text(json.dumps(SCHEMA), encoding="utf-8")
        started = time.perf_counter()
        completed = subprocess.run(
            [
                "codex", "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
                "--skip-git-repo-check", "-s", "read-only", "-m", model,
                "--output-schema", str(schema_path), "--output-last-message", str(output_path),
            ],
            input=build_prompt(candidate),
            text=True,
            capture_output=True,
            timeout=timeout,
            cwd="/private/tmp",
            check=False,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        if completed.returncode != 0 or not output_path.exists():
            return {
                "error": f"exit_{completed.returncode}",
                "elapsed_ms": elapsed_ms,
                "stderr_tail": completed.stderr[-1200:],
            }
        try:
            result = parse_output(output_path)
        except Exception as exc:
            return {"error": type(exc).__name__, "elapsed_ms": elapsed_ms}
        result["elapsed_ms"] = elapsed_ms
        return result


def choose_packets(
    data: dict[str, Any],
    *,
    model_ids: Sequence[str],
    candidate_limit: int,
    train_limit: int,
    test_limit: int,
    seed: int,
    device: str,
    batch_size: int,
    max_seq_length: int,
    limit: int,
) -> list[dict[str, Any]]:
    all_questions = [question for question in data["questions"] if question.get("gold_page_ids")]
    train = all_questions[:train_limit]
    test = all_questions[train_limit : train_limit + test_limit]
    required = {str(page_id) for question in train + test for page_id in question["gold_page_ids"]}
    pages = bounded_pages(list(data["pages"]), required, candidate_limit, seed)
    queries = [str(question["question"]) for question in train + test]
    ensemble, _ = fit_ensemble(
        pages,
        queries,
        model_ids,
        device=device,
        batch_size=batch_size,
        max_seq_length=max_seq_length,
        local_files_only=True,
        trust_remote_code=True,
    )
    triplets, _ = mine_triplets(ensemble, train + test, range(len(train)))
    pages_by_id = {str(page["page_id"]): page for page in pages}
    questions_by_text = {str(question["question"]): question for question in train}
    candidates: list[dict[str, Any]] = []
    for query, positive_id, negative_id in triplets:
        question = questions_by_text[query]
        candidates.append({
            "query": query,
            "positive": page_packet(pages_by_id[positive_id]),
            "candidate": page_packet(pages_by_id[negative_id]),
            "query_hash": sha256_text(query),
            "positive_hash": sha256_text(positive_id),
            "candidate_hash": sha256_text(negative_id),
            "question_id_hash": sha256_text(str(question.get("question_id") or query)),
        })
    candidates.sort(key=lambda item: stable_key(seed, item["query_hash"] + item["candidate_hash"]))
    return candidates[:limit]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--arm", action="append", nargs="+", metavar="MODEL", help="Arm name followed by one or more model IDs.")
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--candidate-limit", type=int, default=500)
    parser.add_argument("--train-limit", type=int, default=100)
    parser.add_argument("--test-limit", type=int, default=100)
    parser.add_argument("--limit-per-arm", type=int, default=20)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--max-seq-length", type=int, default=256)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()
    if not args.arm:
        args.arm = [["labse", "sentence-transformers/LaBSE"], ["composite", *PAPER_EMBEDDING_MODELS]]
    data = json.loads(args.dataset.read_text(encoding="utf-8"))
    arms: list[dict[str, Any]] = []
    for raw_arm in args.arm:
        if len(raw_arm) < 2:
            raise SystemExit("each --arm requires a name and at least one model ID")
        name, *model_ids = raw_arm
        packets = choose_packets(
            data,
            model_ids=model_ids,
            candidate_limit=args.candidate_limit,
            train_limit=args.train_limit,
            test_limit=args.test_limit,
            seed=args.seed,
            device=args.device,
            batch_size=args.batch_size,
            max_seq_length=args.max_seq_length,
            limit=args.limit_per_arm,
        )
        arms.append({"name": name, "model_ids": model_ids, "packets": packets})

    jobs: list[tuple[str, int, int, dict[str, Any]]] = []
    for arm in arms:
        for index, packet in enumerate(arm["packets"]):
            for repeat in range(args.repeats):
                jobs.append((arm["name"], index, repeat, packet))
    rows: dict[tuple[str, int], dict[str, Any]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(adjudicate, packet, args.model, args.timeout): (name, index, repeat, packet)
            for name, index, repeat, packet in jobs
        }
        for future in concurrent.futures.as_completed(futures):
            name, index, repeat, packet = futures[future]
            key = (name, index)
            row = rows.setdefault(key, {
                "arm": name,
                "candidate_index": index,
                "query_hash": packet["query_hash"],
                "positive_hash": packet["positive_hash"],
                "candidate_hash": packet["candidate_hash"],
                "question_id_hash": packet["question_id_hash"],
                "calls": [],
            })
            result = future.result()
            result["repeat"] = repeat
            row["calls"].append(result)

    normalized_rows = []
    for row in sorted(rows.values(), key=lambda value: (value["arm"], value["candidate_index"])):
        valid = [call for call in row["calls"] if "label" in call]
        labels = [call["label"] for call in valid]
        row["calls"] = sorted(row["calls"], key=lambda call: call.get("repeat", 0))
        row["valid_call_count"] = len(valid)
        row["agreement"] = bool(labels) and len(set(labels)) == 1
        normalized_rows.append(row)
    summary: dict[str, Any] = {}
    for arm in arms:
        arm_rows = [row for row in normalized_rows if row["arm"] == arm["name"]]
        labels = [call["label"] for row in arm_rows for call in row["calls"] if "label" in call]
        summary[arm["name"]] = {
            "models": arm["model_ids"],
            "candidate_count": len(arm_rows),
            "valid_call_count": len(labels),
            "agreement_count": sum(1 for row in arm_rows if row["agreement"]),
            "label_counts": {label: labels.count(label) for label in LABELS},
            "relevant_false_negative_rate": labels.count("relevant_false_negative") / len(labels) if labels else None,
        }
    result = {
        "schema_version": "frankengate-hard-negative-frontier-adjudication-v1",
        "model": args.model,
        "dataset": {"fixture_sha256": sha256_text(args.dataset.read_text(encoding="utf-8")), "pages": len(data["pages"]), "train_questions": args.train_limit, "test_questions": args.test_limit, "seed": args.seed, "max_seq_length": args.max_seq_length},
        "arms": summary,
        "rows": normalized_rows,
        "claim_boundary": "Silver frontier labels only; raw page text is not emitted, and labels do not establish enterprise relevance or causality.",
        "next_gate": "Repeat with blinded SME labels and random/lexical controls on identifier, alias, NIL, and changed-system slices.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"arms": summary, "rows": len(normalized_rows), "output": str(args.output)}, sort_keys=True))
    return 0 if all(row["valid_call_count"] == args.repeats for row in normalized_rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
