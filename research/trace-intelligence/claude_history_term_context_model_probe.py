#!/usr/bin/env python3
"""Probe model adjudication of recurring terms with/without lexical context.

Pairs are sampled from a real Claude history export.  The low-context cohort
contains the same surface term with divergent local neighborhoods; the
high-context cohort contains recurring terms with substantially overlapping
neighborhoods.  Luna sees only normalized lexical tokens and anonymized sides.
The receipt contains labels and hashes, never snippets or source identifiers.

This is a silver-label signal study, not an alias ground-truth benchmark.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "frankengate-claude-history-term-context-model-probe-v1"
LABELS = {"same_concept", "related_context", "different", "unclear"}
STOP = frozenset(
    "the and for with that this from into have what when where which please need want use could would should about then than your you our their there just also does how i we a an to of in on is be as or it do not can are was were has have had this these those".split()
)
WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9_./:-]{2,}")

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["label", "confidence"],
    "properties": {
        "label": {"type": "string", "enum": sorted(LABELS)},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
}


def digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def manifest(root: Path) -> tuple[int, int, str]:
    rows = []
    total = 0
    for path in sorted(root.rglob("*.jsonl")):
        size = path.stat().st_size
        rows.append((str(path.relative_to(root)), size))
        total += size
    return len(rows), total, digest(rows)


def safe_tokens(text: str) -> list[str]:
    tokens = []
    for raw in WORD_RE.findall(text.lower()):
        token = raw
        if token.startswith(("/", "~", "http:", "https:")):
            continue
        if re.fullmatch(r"[0-9a-f]{8,}", token):
            continue
        if re.search(r"\d{3,}", token):
            token = re.sub(r"\d+", "#", token)
        if token not in STOP and len(token) > 3:
            tokens.append(token)
    return tokens


def text_parts(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(text_parts(item))
        return out
    if isinstance(value, dict):
        out: list[str] = []
        for key in ("text", "content", "input", "output"):
            if key in value:
                out.extend(text_parts(value[key]))
        return out
    return []


def load_project_terms(root: Path) -> tuple[dict[str, Counter[str]], dict[tuple[str, str], Counter[str]], int]:
    term_frequency: dict[str, Counter[str]] = defaultdict(Counter)
    document_frequency: dict[str, Counter[str]] = defaultdict(Counter)
    project_messages: dict[str, list[list[str]]] = defaultdict(list)
    message_count = 0
    for path in sorted(root.rglob("*.jsonl")):
        project = path.parent.name
        try:
            with path.open(encoding="utf-8", errors="ignore") as handle:
                for line in handle:
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    message = record.get("message") if isinstance(record, dict) else None
                    if not isinstance(message, dict):
                        continue
                    tokens = safe_tokens("\n".join(text_parts(message.get("content"))))
                    if not tokens:
                        continue
                    message_count += 1
                    project_messages[project].append(tokens)
                    term_frequency[project].update(tokens)
                    document_frequency[project].update(set(tokens))
        except OSError:
            continue

    selected: dict[str, set[str]] = {}
    for project, counts in document_frequency.items():
        frequencies = term_frequency[project]
        selected[project] = {
            term
            for term in sorted(counts, key=lambda value: (-counts[value], -frequencies[value], value))[:100]
        }
    contexts: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for project, messages in project_messages.items():
        terms = selected.get(project, set())
        for tokens in messages:
            for index, term in enumerate(tokens):
                if term not in terms:
                    continue
                left = max(0, index - 4)
                right = min(len(tokens), index + 5)
                contexts[(project, term)].update(token for token in tokens[left:index] + tokens[index + 1:right] if token != term)
    return term_frequency, contexts, message_count


def jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def parse_output(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8").strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON")
    value = json.loads(raw[start : end + 1])
    if value.get("label") not in LABELS:
        raise ValueError("invalid label")
    confidence = float(value.get("confidence"))
    if not 0 <= confidence <= 1:
        raise ValueError("invalid confidence")
    return {"label": value["label"], "confidence": confidence, "response_sha256": hashlib.sha256(raw.encode()).hexdigest()}


def ask(pair: dict[str, Any], arm: str, model: str, timeout: int, seed: int) -> dict[str, Any]:
    context = f"SURFACE TERM:\n{pair['term']}"
    if arm == "term_plus_context":
        context += f"\n\nSIDE A NEIGHBOR TOKENS:\n{', '.join(pair['left_context'])}\n\nSIDE B NEIGHBOR TOKENS:\n{', '.join(pair['right_context'])}"
    prompt = (
        "Classify whether the same surface term denotes the same enterprise concept in two anonymized trace contexts. "
        "Use only the provided term and (when present) local neighbor tokens. "
        "same_concept means likely identical referent; related_context means related work but not enough for identity; "
        "different means likely distinct referents; unclear means insufficient evidence. Never infer person, employer, or secret data. "
        "Return JSON only.\n\n"
        + json.dumps(SCHEMA, sort_keys=True)
        + "\n\n"
        + context
        + f"\n\nPROBE SEED: {seed}"
    )
    with tempfile.TemporaryDirectory(prefix="frankengate-term-context-luna-") as directory:
        root = Path(directory)
        schema = root / "schema.json"
        output = root / "output.json"
        schema.write_text(json.dumps(SCHEMA), encoding="utf-8")
        started = time.perf_counter()
        completed = subprocess.run(
            [
                "codex", "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
                "--skip-git-repo-check", "-s", "read-only", "-m", model,
                "--output-schema", str(schema), "--output-last-message", str(output),
            ],
            input=prompt,
            text=True,
            capture_output=True,
            timeout=timeout,
            cwd="/private/tmp",
            check=False,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        if completed.returncode != 0 or not output.exists():
            return {"error": f"exit_{completed.returncode}", "elapsed_ms": round(elapsed_ms, 3)}
        try:
            parsed = parse_output(output)
        except Exception as exc:
            return {"error": type(exc).__name__, "elapsed_ms": round(elapsed_ms, 3)}
        parsed["elapsed_ms"] = round(elapsed_ms, 3)
        return parsed


def run(root: Path, output: Path, pairs_per_cohort: int, repeats: int, model: str, timeout: int) -> dict[str, Any]:
    root = root.resolve(strict=True)
    file_count, byte_count, manifest_hash = manifest(root)
    _frequencies, contexts, message_count = load_project_terms(root)
    by_term: dict[str, list[str]] = defaultdict(list)
    for project, term in contexts:
        if project not in by_term[term]:
            by_term[term].append(project)
    candidates: list[dict[str, Any]] = []
    for term, projects in sorted(by_term.items()):
        if len(projects) < 2:
            continue
        for index, left in enumerate(sorted(projects)):
            for right in sorted(projects)[index + 1 :]:
                left_set = set(contexts[(left, term)])
                right_set = set(contexts[(right, term)])
                if not left_set or not right_set:
                    continue
                value = jaccard(left_set, right_set)
                if value < 0.05 or value >= 0.20:
                    candidates.append(
                        {
                            "term": term,
                            "term_hash": digest(term),
                            "left_context": sorted(left_set, key=lambda token: (-contexts[(left, term)][token], token))[:12],
                            "right_context": sorted(right_set, key=lambda token: (-contexts[(right, term)][token], token))[:12],
                            "context_jaccard": round(value, 6),
                            "left_project_hash": digest(left),
                            "right_project_hash": digest(right),
                        }
                    )
    low = sorted((row for row in candidates if row["context_jaccard"] < 0.05), key=lambda row: (row["term_hash"], row["left_project_hash"], row["right_project_hash"]))[:pairs_per_cohort]
    high = sorted((row for row in candidates if row["context_jaccard"] >= 0.20), key=lambda row: (row["term_hash"], row["left_project_hash"], row["right_project_hash"]))[:pairs_per_cohort]
    selected = [("low_context", row) for row in low] + [("high_context", row) for row in high]
    rows = []
    for index, (cohort, pair) in enumerate(selected):
        calls: dict[str, list[dict[str, Any]]] = {"term_only": [], "term_plus_context": []}
        for arm in calls:
            for repeat in range(repeats):
                calls[arm].append(ask(pair, arm, model, timeout, 730001 + index * 100 + repeat))
        rows.append({
            "pair_index": index,
            "cohort": cohort,
            "term_hash": pair["term_hash"],
            "left_project_hash": pair["left_project_hash"],
            "right_project_hash": pair["right_project_hash"],
            "context_jaccard": pair["context_jaccard"],
            "calls": calls,
        })
    summary: dict[str, Any] = {}
    for arm in ("term_only", "term_plus_context"):
        summary[arm] = {}
        for cohort in ("low_context", "high_context"):
            valid = [call for row in rows if row["cohort"] == cohort for call in row["calls"][arm] if "label" in call]
            labels = Counter(call["label"] for call in valid)
            pair_agreement = sum(
                1
                for row in rows
                if row["cohort"] == cohort
                and len(row["calls"][arm]) == repeats
                and all("label" in call for call in row["calls"][arm])
                and len({call["label"] for call in row["calls"][arm]}) == 1
            )
            summary[arm][cohort] = {
                "valid_call_count": len(valid),
                "label_counts": dict(sorted(labels.items())),
                "pair_agreement_count": pair_agreement,
                "pair_count": sum(1 for row in rows if row["cohort"] == cohort),
                "decisive_rate": round(sum(label in {"same_concept", "different"} for label in labels.elements()) / len(valid), 6) if valid else 0.0,
            }
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source": {"root_name": root.name, "file_count": file_count, "byte_count": byte_count, "manifest_sha256": manifest_hash, "message_count": message_count, "raw_content_committed": False},
        "protocol": {
            "candidate_cohorts": "low context Jaccard < 0.05 versus high context Jaccard >= 0.20",
            "context": "top local lexical neighbor tokens, paths/URLs/long hex/numeric runs removed",
            "arms": ["term_only", "term_plus_context"],
            "model": model,
            "repeats_per_arm": repeats,
            "harness": "codex-cli subscription",
        },
        "coverage": {"candidate_count": len(candidates), "low_context_selected": len(low), "high_context_selected": len(high), "pair_count": len(rows)},
        "summary": summary,
        "rows": rows,
        "claim_boundary": {
            "silver_model_labels": True,
            "independent_alias_ground_truth": False,
            "embedding_quality_established": False,
            "enterprise_ontology_promotion_authorized": False,
            "reason": "The lexical context cohorts and Luna labels are diagnostic silver signals; no adjudicated corporate alias/NIL ground truth or downstream replay outcome is available.",
        },
    }
    result["result_sha256"] = digest(result)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"coverage": result["coverage"], "summary": summary}, sort_keys=True))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pairs-per-cohort", type=int, default=6)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    run(args.input, args.output, args.pairs_per_cohort, args.repeats, args.model, args.timeout)
