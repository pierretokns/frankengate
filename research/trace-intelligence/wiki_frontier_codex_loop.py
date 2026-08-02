#!/usr/bin/env python3
"""Run a bounded Codex/Luna structured-action loop over the wiki contract.

This is intentionally separate from native MCP: the Codex model emits a typed
action and this runner executes the same search/get_page/expand_links contract.
It gives us frontier-agent incorporation metrics even when non-interactive
Codex MCP approval cancels native tool calls.
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
        "action": {"type": "string", "enum": ["search", "get_page", "expand_links", "finish"]},
        "arguments": {"type": "object", "additionalProperties": False, "properties": {"query": {"type": ["string", "null"]}, "k": {"type": ["integer", "null"]}, "page_id": {"type": ["string", "null"]}, "depth": {"type": ["integer", "null"]}}, "required": ["query", "k", "page_id", "depth"]},
        "answer": {"type": ["string", "null"]},
    },
}


def prompt(question: dict[str, Any], transcript: list[dict[str, Any]]) -> str:
    return f"""You are a careful wiki retrieval agent in a benchmark. You have exactly three read-only tools described below. Do not use filesystem, shell, web, or any other tools.

Tools:
- search(query: string, k: integer): rank wiki pages. Always search before guessing.
- get_page(page_id: string): read the complete page by stable ID.
- expand_links(page_id: string, depth: integer): read bounded linked pages.

Choose exactly one next action and return only the requested JSON object. Use `finish` only after reading enough evidence. For a NIL/not-found question, finish with an explicit abstention rather than inventing an answer.

Question:
{question['question']}

Prior trace:
{json.dumps(transcript, ensure_ascii=True)}
"""


def invoke(prompt_text: str, schema_path: Path, output_path: Path, timeout: int, model: str) -> dict[str, Any]:
    command = ["codex", "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules", "--skip-git-repo-check", "-s", "read-only", "-m", model, "--output-schema", str(schema_path), "--output-last-message", str(output_path)]
    completed = subprocess.run(command, input=prompt_text, text=True, capture_output=True, timeout=timeout, cwd="/private/tmp", check=False)
    if completed.returncode:
        raise RuntimeError(completed.stderr[-2000:] or completed.stdout[-2000:])
    return json.loads(output_path.read_text(encoding="utf-8"))


def answer_matches(question: dict[str, Any], answer: str, target_page: dict[str, Any] | None) -> bool:
    text = answer.lower()
    if question["slice"] == "nil":
        return any(marker in text for marker in ("not found", "no evidence", "cannot determine", "does not exist", "unable to retrieve", "unknown", "no wiki page", "no page", "no matching", "not documented", "no deployment"))
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


def run_case(index: WikiIndex, question: dict[str, Any], max_steps: int, timeout: int, model: str) -> dict[str, Any]:
    transcript: list[dict[str, Any]] = []
    searched: list[str] = []
    loaded: list[str] = []
    started = time.perf_counter_ns()
    error: str | None = None
    final_answer = ""
    with tempfile.TemporaryDirectory(prefix="frankengate-wiki-codex-") as directory:
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
            if name == "finish":
                final_answer = str(action.get("answer") or "")
                transcript.append({"step": step, "action": name, "answer": final_answer})
                break
            if name == "search":
                query = str(args.get("query") or question["question"])
                result = index.search(query, int(args.get("k", 5)))
                searched.extend(row["page_id"] for row in result)
            elif name == "get_page":
                page_id = str(args.get("page_id") or "")
                result = index.get_page(page_id)
                if result:
                    loaded.append(page_id)
            elif name == "expand_links":
                page_id = str(args.get("page_id") or "")
                result = index.expand_links(page_id, int(args.get("depth", 1)))
                loaded.extend(page["page_id"] for page in result)
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
        "answer": final_answer,
        "answer_matches_gold": answer_matches(question, final_answer, target_page),
        "steps": len(transcript),
        "latency_ms": elapsed_ms,
        "error": error,
        "trace": transcript,
    }


def select_questions(data: dict[str, Any], sizes: list[int], per_size: int) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    for size in sizes:
        selected = {f"wiki-{number:02d}" for number in range(size)}
        candidates = [question for question in data["questions"] if (not question["gold_page_ids"] or question["wiki_id"] in selected)]
        # Keep identical first-wiki slices plus one NIL query at every scale.
        questions.extend(candidates[:per_size])
        nil = next((question for question in candidates if question["slice"] == "nil"), None)
        if nil and nil not in questions[-per_size:]:
            questions.append(nil)
    return questions


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
        "schema_version": "frankengate-wiki-frontier-codex-structured-loop-v1",
        "protocol": {"model": args.model, "harness": "Codex CLI structured JSON action loop", "backend": "hybrid raw", "max_steps": args.max_steps, "workers": args.workers, "native_mcp": False, "raw_traces_committed": False},
        "corpus": {"sha256": sha256(args.corpus), "pages": len(data["pages"]), "wikis": len({page["wiki_id"] for page in data["pages"]})},
        "records": records,
        "claim_boundary": "Frontier-agent structured-action loop over a synthetic fixture. It measures retrieval incorporation and answer handling, not native MCP approval behavior, Wikipedia quality, or enterprise transfer.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"schema_version": result["schema_version"], "records": len(records), "errors": sum(bool(row["error"]) for row in records), "answer_matches": sum(row["answer_matches_gold"] for row in records)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
