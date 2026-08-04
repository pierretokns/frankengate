#!/usr/bin/env python3
"""Bounded frontier benchmark for A-RAG-style hierarchical retrieval.

The A-RAG paper exposes retrieval decisions to the agent through separate
keyword, semantic, and chunk-read tools.  This runner implements that contract
over the existing synthetic enterprise-shaped wiki fixture.  It deliberately
does not claim native MCP behavior: the Codex process emits one typed action at
a time and this process executes the action locally.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

from wiki_agentic_rag_benchmark import WikiIndex, sha256


SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["action", "arguments", "answer"],
    "properties": {
        "action": {
            "type": "string",
            "enum": ["keyword_search", "semantic_search", "read_chunk", "finish"],
        },
        "arguments": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "query": {"type": ["string", "null"]},
                "k": {"type": ["integer", "null"]},
                "page_id": {"type": ["string", "null"]},
                "chunk_index": {"type": ["integer", "null"]},
            },
            "required": ["query", "k", "page_id", "chunk_index"],
        },
        "answer": {"type": ["string", "null"]},
    },
}


def prompt(question: dict[str, Any], transcript: list[dict[str, Any]]) -> str:
    return f"""You are a careful enterprise wiki retrieval agent in a benchmark.
You have exactly three read-only retrieval tools.  Retrieval is hierarchical:
use keyword_search for exact identifiers, aliases, acronyms, and dates; use
semantic_search for paraphrases; then use read_chunk to inspect only the
relevant portion of a retrieved page.  You may call either search tool more
than once when ambiguity remains.  Do not guess, and for NIL questions finish
with an explicit abstention.

Tools:
- keyword_search(query: string, k: integer): exact/lexical ranking.
- semantic_search(query: string, k: integer): semantic/paraphrase ranking.
- read_chunk(page_id: string, chunk_index: integer): read one bounded chunk;
  chunks are zero-indexed and contain at most 320 characters.

Return only the requested JSON object and choose exactly one next action.
Use finish only after enough evidence has been read.

Question:
{question['question']}

Prior trace:
{json.dumps(transcript, ensure_ascii=True)}
"""


def invoke(prompt_text: str, schema_path: Path, output_path: Path, timeout: int, model: str) -> dict[str, Any]:
    command = [
        "codex",
        "exec",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--skip-git-repo-check",
        "-s",
        "read-only",
        "-m",
        model,
        "--output-schema",
        str(schema_path),
        "--output-last-message",
        str(output_path),
    ]
    completed = subprocess.run(
        command,
        input=prompt_text,
        text=True,
        capture_output=True,
        timeout=timeout,
        cwd="/private/tmp",
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(completed.stderr[-2000:] or completed.stdout[-2000:])
    return json.loads(output_path.read_text(encoding="utf-8"))


def answer_matches(question: dict[str, Any], answer: str, target_page: dict[str, Any] | None) -> bool:
    text = answer.lower()
    if question["slice"] == "nil":
        return any(
            marker in text
            for marker in (
                "not found",
                "no evidence",
                "cannot determine",
                "does not exist",
                "unable to retrieve",
                "unknown",
                "no wiki page",
                "no page",
                "no matching",
                "not documented",
                "no deployment",
            )
        )
    if not target_page:
        return False
    source = target_page["text"].lower()
    if question["slice"] in {"exact_identifier", "cross_wiki_disambiguation"}:
        endpoint = re.search(r"preferred endpoint is ([^ ]+)", source)
        if endpoint and endpoint.group(1).rstrip(".") in text:
            return True
        return "02:00" in text and "03:00" in text
    if question["slice"] == "semantic_paraphrase":
        return "tuesday" in text and ("02:00" in text or "03:00" in text)
    if question["slice"] == "alias":
        return "team-" in text and "us-east-" in text
    return False


def _chunks(page: dict[str, Any], width: int = 320) -> list[str]:
    text = f"{page['title']}\n{page['text']}"
    return [text[offset : offset + width] for offset in range(0, len(text), width)] or [""]


def _search_observation(index: WikiIndex, query: str, k: int, backend: str) -> list[dict[str, Any]]:
    original = index.backend
    index.backend = backend
    try:
        ranked = index.search(query, k=max(1, min(k, 10)))
    finally:
        index.backend = original
    observations: list[dict[str, Any]] = []
    for row in ranked:
        page = index.get_page(row["page_id"])
        observations.append(
            {
                "page_id": row["page_id"],
                "wiki_id": row["wiki_id"],
                "score": row["score"],
                "title": page["title"] if page else "",
                "snippet": (page["text"][:180] if page else ""),
            }
        )
    return observations


def run_case(index: WikiIndex, question: dict[str, Any], max_steps: int, timeout: int, model: str) -> dict[str, Any]:
    transcript: list[dict[str, Any]] = []
    searched: list[str] = []
    loaded: list[str] = []
    tool_counts: dict[str, int] = {}
    started = time.perf_counter_ns()
    error: str | None = None
    final_answer = ""
    with tempfile.TemporaryDirectory(prefix="frankengate-wiki-arag-") as directory:
        root = Path(directory)
        schema_path = root / "schema.json"
        schema_path.write_text(json.dumps(SCHEMA), encoding="utf-8")
        for step in range(1, max_steps + 1):
            output_path = root / f"output-{step}.json"
            try:
                action = invoke(prompt(question, transcript), schema_path, output_path, timeout, model)
            except Exception as exc:
                error = str(exc)
                break
            name = action["action"]
            args = dict(action.get("arguments") or {})
            tool_counts[name] = tool_counts.get(name, 0) + 1
            if name == "finish":
                final_answer = str(action.get("answer") or "")
                transcript.append({"step": step, "action": name, "answer": final_answer})
                break
            if name in {"keyword_search", "semantic_search"}:
                query = str(args.get("query") or question["question"])
                backend = "fts" if name == "keyword_search" else "tfidf"
                result = _search_observation(index, query, int(args.get("k") or 5), backend)
                searched.extend(row["page_id"] for row in result)
            elif name == "read_chunk":
                page_id = str(args.get("page_id") or "")
                page = index.get_page(page_id)
                chunks = _chunks(page) if page else []
                chunk_index = max(0, int(args.get("chunk_index") or 0))
                result = {
                    "page_id": page_id,
                    "chunk_index": chunk_index,
                    "chunk_count": len(chunks),
                    "text": chunks[chunk_index] if chunk_index < len(chunks) else "",
                }
                if page and chunk_index < len(chunks):
                    loaded.append(page_id)
            else:
                error = f"unsupported action: {name}"
                break
            transcript.append({"step": step, "action": name, "arguments": args, "observation": result})
        else:
            error = "step_limit"
    target = set(question["gold_page_ids"])
    target_page = index.get_page(next(iter(target))) if target else None
    elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
    return {
        "question_id": question["question_id"],
        "corpus_size": question.get("_corpus_size"),
        "wiki_id": question["wiki_id"],
        "slice": question["slice"],
        "gold_page_ids": question["gold_page_ids"],
        "searched_gold": bool(target & set(searched)),
        "loaded_gold": bool(target & set(loaded)),
        "finished": bool(final_answer),
        "answer_matches_gold": answer_matches(question, final_answer, target_page),
        "steps": len(transcript),
        "tool_counts": tool_counts,
        "latency_ms": elapsed_ms,
        "error": error,
        "trace": transcript,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--sizes", default="1,5,10,25")
    parser.add_argument("--per-size", type=int, default=4)
    parser.add_argument("--max-steps", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    data = json.loads(args.corpus.read_text(encoding="utf-8"))
    sizes = [int(value) for value in args.sizes.split(",") if value.strip()]
    cases: list[tuple[WikiIndex, dict[str, Any]]] = []
    for size in sizes:
        selected = {f"wiki-{number:02d}" for number in range(size)}
        pages = [page for page in data["pages"] if page["wiki_id"] in selected]
        index = WikiIndex(pages, backend="hybrid", compiled=False)
        candidates = [question for question in data["questions"] if (not question["gold_page_ids"] or question["wiki_id"] in selected)]
        chosen = [dict(question, _corpus_size=size) for question in candidates[: args.per_size]]
        nil = next((question for question in candidates if question["slice"] == "nil"), None)
        if nil is not None:
            chosen.append(dict(nil, _corpus_size=size))
        cases.extend((index, question) for question in chosen)
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run_case, index, question, args.max_steps, args.timeout, args.model) for index, question in cases]
        records = [future.result() for future in futures]
    result = {
        "schema_version": "frankengate-wiki-arag-codex-structured-loop-v1",
        "protocol": {
            "model": args.model,
            "harness": "Codex CLI structured JSON action loop",
            "retrieval_tools": ["keyword_search", "semantic_search", "read_chunk"],
            "backend": "fts+tfidf",
            "max_steps": args.max_steps,
            "workers": args.workers,
            "native_mcp": False,
            "raw_traces_committed": False,
        },
        "corpus": {"sha256": sha256(args.corpus), "pages": len(data["pages"]), "wikis": len({page["wiki_id"] for page in data["pages"]})},
        "records": records,
        "claim_boundary": "A-RAG-style hierarchical tool-choice loop over a synthetic fixture. It measures adaptive retrieval and answer handling, not native MCP approval behavior, Wikipedia quality, or enterprise transfer.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"schema_version": result["schema_version"], "records": len(records), "errors": sum(bool(row["error"]) for row in records), "answer_matches": sum(row["answer_matches_gold"] for row in records)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
