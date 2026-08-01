#!/usr/bin/env python3
"""Run a bounded Termolator foreground/background termhood probe.

The Wisp corpus and Termolator intermediate files stay outside Git.  The
receipt contains only hashes, counts, and aggregate candidate statistics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any


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


def record_text(record: dict[str, Any]) -> str:
    message = record.get("message")
    if isinstance(message, dict):
        content = strings_from_content(message.get("content"))
        if content:
            return "\n".join(content)
    for key in ("content", "lastPrompt", "result"):
        content = strings_from_content(record.get(key))
        if content:
            return "\n".join(content)
    return ""


def load_docs(root: Path) -> list[tuple[str, str]]:
    docs: list[tuple[str, str]] = []
    for path in sorted(root.rglob("*.jsonl")):
        text: list[str] = []
        for line in path.read_bytes().splitlines():
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            value = record_text(record)
            if value:
                text.append(value)
        if text:
            docs.append((hashlib.sha256(str(path.relative_to(root)).encode()).hexdigest(), "\n".join(text)))
    return docs


def write_inputs(root: Path, docs: list[tuple[str, str]], split: int) -> tuple[Path, Path, Path]:
    work = Path(tempfile.mkdtemp(prefix="frankengate-termolator-", dir="/private/tmp"))
    fg = work / "foreground"
    bg = work / "background"
    fg.mkdir()
    bg.mkdir()
    lists: list[Path] = []
    for name, rows in (("foreground", docs[:split]), ("background", docs[split:])):
        paths: list[str] = []
        directory = fg if name == "foreground" else bg
        for index, (_, text) in enumerate(rows):
            path = directory / f"{index}.txt"
            path.write_text(text + "\n", encoding="utf-8")
            paths.append(str(path))
        list_path = work / f"{name}.list"
        list_path.write_text("\n".join(paths) + "\n", encoding="utf-8")
        lists.append(list_path)
    return work, lists[0], lists[1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus-root", type=Path, required=True)
    parser.add_argument("--termolator-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-docs", type=int, default=49)
    args = parser.parse_args()
    docs = load_docs(args.corpus_root)[: args.max_docs]
    if len(docs) < 4:
        raise SystemExit("need at least four non-empty documents")
    split = len(docs) // 2
    work, foreground, background = write_inputs(args.corpus_root, docs, split)
    output = work / "termolator"
    command = [
        "bash", str(args.termolator_root / "run_termolator.sh"),
        str(foreground), str(background), ".txt", str(output),
        "True", "False", "30000", "5000", str(args.termolator_root),
        "False", "False", "False", "False", "False",
    ]
    completed = subprocess.run(command, cwd=work, capture_output=True, text=True, check=False)
    terms_path = Path(str(output) + ".out_term_list")
    terms = [line.strip() for line in terms_path.read_text(encoding="utf-8").splitlines() if line.strip()] if terms_path.exists() else []
    result = {
        "schema_version": "frankengate-termolator-wisp-benchmark-v1",
        "dataset": {
            "dataset_id": "crispwisp/wisp-claude-code-sessions",
            "dataset_revision": "c2c90b59174318ab0b163ec9c9ac82bb879288ce",
            "document_count": len(docs),
            "foreground_count": split,
            "background_count": len(docs) - split,
            "document_path_hash": stable_hash([path_hash for path_hash, _ in docs]),
        },
        "tool": {"name": "Termolator", "returncode": completed.returncode},
        "candidates": {
            "count": len(terms),
            "top_term_hashes": [stable_hash(term.lower()) for term in terms[:100]],
            "mean_tokens_top_100": (sum(len(term.split()) for term in terms[:100]) / min(100, len(terms))) if terms else 0.0,
        },
        "claim_boundary": {
            "enterprise_term_quality_established": False,
            "retrieval_impact_evaluated": False,
            "raw_text_committed": False,
            "raw_candidate_strings_committed": False,
            "reason": "Public single-contributor Wisp corpus and unreviewed foreground/background termhood ranking; candidate precision requires blinded labels and retrieval replay.",
        },
    }
    result["result_sha256"] = stable_hash(result)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"documents": len(docs), "candidates": len(terms), "returncode": completed.returncode, "work": str(work)}, sort_keys=True))
    return 0 if completed.returncode == 0 and terms_path.exists() else 1


if __name__ == "__main__":
    raise SystemExit(main())
