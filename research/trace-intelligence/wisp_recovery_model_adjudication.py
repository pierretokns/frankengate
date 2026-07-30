"""Bounded local-model stability study over blinded Wisp recovery packets."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


class AdjudicationError(ValueError):
    """Raised when a packet, response, or experiment contract is invalid."""


PROMPT_VARIANTS = {
    "rubric_first": (
        "Apply the closed rubric literally. Do not infer facts outside the bounded "
        "episode. A later successful tool call does not by itself prove task recovery."
    ),
    "evidence_first": (
        "First identify direct candidate-local evidence, then apply the closed rubric. "
        "Prefer insufficient_evidence over an unsupported causal or outcome claim."
    ),
    "skeptical": (
        "Act as a skeptical replication adjudicator. Try to falsify recovery, causal, "
        "and usefulness claims before selecting a supported closed-enum label."
    ),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def stable_key(seed: str, blind_id: str) -> str:
    return hashlib.sha256(f"{seed}\0{blind_id}".encode("utf-8")).hexdigest()


def count_by_family(candidates: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(item["controlled_tool_family"] for item in candidates).items()))


def select_stratified(
    candidates: list[dict[str, Any]],
    quota: dict[str, int],
    seed: str,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in candidates:
        grouped[item["controlled_tool_family"]].append(item)
    selected: list[dict[str, Any]] = []
    for family, count in sorted(quota.items()):
        if len(grouped[family]) < count:
            raise AdjudicationError(
                f"quota for {family} requires {count}, found {len(grouped[family])}"
            )
        ordered = sorted(
            grouped[family],
            key=lambda item: stable_key(f"{seed}:{family}", item["blind_id"]),
        )
        selected.extend(ordered[:count])
    return sorted(selected, key=lambda item: stable_key(seed, item["blind_id"]))


def strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        first_newline = stripped.find("\n")
        if first_newline < 0 or not stripped.endswith("```"):
            raise AdjudicationError("malformed fenced JSON")
        stripped = stripped[first_newline + 1 : -3].strip()
    return stripped


def parse_and_validate(
    text: str,
    candidate: dict[str, Any],
    label_contract: dict[str, list[str]],
) -> dict[str, dict[str, Any]]:
    try:
        value = json.loads(strip_code_fence(text))
    except json.JSONDecodeError as exc:
        raise AdjudicationError("response is not JSON") from exc
    if not isinstance(value, dict) or set(value) != set(label_contract):
        raise AdjudicationError("response fields do not match label contract")
    allowed_refs = {
        event["evidence_ref"]
        for event in candidate["context"]
        if isinstance(event, dict) and isinstance(event.get("evidence_ref"), str)
    }
    normalized: dict[str, dict[str, Any]] = {}
    for field, allowed_labels in label_contract.items():
        item = value[field]
        if not isinstance(item, dict) or set(item) != {"label", "evidence_refs"}:
            raise AdjudicationError(f"{field}: invalid label object")
        label = item["label"]
        refs = item["evidence_refs"]
        if label not in allowed_labels:
            raise AdjudicationError(f"{field}: invalid label {label!r}")
        if (
            not isinstance(refs, list)
            or any(not isinstance(ref, str) for ref in refs)
            or len(refs) != len(set(refs))
            or len(refs) > 3
        ):
            raise AdjudicationError(
                f"{field}: evidence_refs must contain at most three unique strings"
            )
        if any(ref not in allowed_refs for ref in refs):
            raise AdjudicationError(f"{field}: evidence reference is not candidate-local")
        if label != "insufficient_evidence" and not refs:
            raise AdjudicationError(f"{field}: supported label requires evidence")
        normalized[field] = {"label": label, "evidence_refs": refs}
    return normalized


def rotate(values: list[str], offset: int) -> list[str]:
    if not values:
        return []
    normalized = offset % len(values)
    return values[normalized:] + values[:normalized]


def build_prompt(
    candidate: dict[str, Any],
    label_contract: dict[str, list[str]],
    variant: str,
) -> str:
    if variant not in PROMPT_VARIANTS:
        raise AdjudicationError(f"unknown prompt variant: {variant}")
    variant_index = list(PROMPT_VARIANTS).index(variant)
    ordered_contract = {
        field: rotate(list(labels), variant_index + field_index)
        for field_index, (field, labels) in enumerate(sorted(label_contract.items()))
    }
    response_shape = {
        field: {"label": f"<one of {labels}>", "evidence_refs": ["<evidence_ref>"]}
        for field, labels in ordered_contract.items()
    }
    return "\n".join(
        [
            "You are labeling one blinded bounded agent-trace episode.",
            PROMPT_VARIANTS[variant],
            "Return JSON only, with exactly the requested fields.",
            (
                "Every non-insufficient label must cite one to three decisive, "
                "candidate-local evidence_refs; never cite more than three."
            ),
            "Do not provide prose, a person-level judgment, or a label outside the enums.",
            "",
            "LABEL CONTRACT:",
            json.dumps(ordered_contract, ensure_ascii=False, sort_keys=True),
            "",
            "RESPONSE SHAPE:",
            json.dumps(response_shape, ensure_ascii=False, sort_keys=True),
            "",
            "CANDIDATE:",
            json.dumps(
                {
                    "blind_id": candidate["blind_id"],
                    "controlled_tool_family": candidate["controlled_tool_family"],
                    "context": candidate["context"],
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
        ]
    )


def call_chat_completion(
    *,
    endpoint: str,
    model: str,
    prompt: str,
    timeout_seconds: float,
    max_tokens: int,
) -> tuple[str, dict[str, Any]]:
    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Follow the closed annotation contract. Output strict JSON only."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "top_p": 1,
            "max_tokens": max_tokens,
            "stream": False,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        endpoint.rstrip("/") + "/chat/completions",
        data=payload,
        headers={
            "Authorization": "Bearer loopback-no-secret",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    start = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise AdjudicationError(f"model request failed: {type(exc).__name__}") from exc
    elapsed_ms = (time.monotonic() - start) * 1000
    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise AdjudicationError("model response lacks assistant content") from exc
    if not isinstance(content, str):
        raise AdjudicationError("model assistant content is not text")
    usage = body.get("usage") if isinstance(body.get("usage"), dict) else {}
    return content, {
        "latency_ms": elapsed_ms,
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
    }


def fleiss_kappa(rows: list[list[str]]) -> float:
    if not rows:
        raise AdjudicationError("kappa requires at least one item")
    rater_count = len(rows[0])
    if rater_count < 2 or any(len(row) != rater_count for row in rows):
        raise AdjudicationError("kappa requires a rectangular matrix with >=2 raters")
    categories = sorted({label for row in rows for label in row})
    item_agreements = []
    category_totals = Counter()
    for row in rows:
        counts = Counter(row)
        category_totals.update(counts)
        item_agreements.append(
            (sum(count * count for count in counts.values()) - rater_count)
            / (rater_count * (rater_count - 1))
        )
    observed = statistics.fmean(item_agreements)
    total = len(rows) * rater_count
    expected = sum((category_totals[category] / total) ** 2 for category in categories)
    if math.isclose(expected, 1.0):
        return 1.0 if math.isclose(observed, 1.0) else 0.0
    return (observed - expected) / (1.0 - expected)


def aggregate(
    *,
    selected: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    label_contract: dict[str, list[str]],
    pass_ids: list[str],
) -> dict[str, Any]:
    valid_rows = [row for row in rows if row["status"] == "valid"]
    by_case: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in valid_rows:
        by_case[row["blind_id"]][row["pass_id"]] = row["labels"]
    agreement: dict[str, Any] = {}
    label_counts: dict[str, dict[str, int]] = {}
    complete_case_count = 0
    for blind_id in [item["blind_id"] for item in selected]:
        if all(pass_id in by_case[blind_id] for pass_id in pass_ids):
            complete_case_count += 1
    for field in sorted(label_contract):
        matrix = []
        counts = Counter()
        unanimous = 0
        for item in selected:
            case = by_case[item["blind_id"]]
            if not all(pass_id in case for pass_id in pass_ids):
                continue
            labels = [case[pass_id][field]["label"] for pass_id in pass_ids]
            matrix.append(labels)
            counts.update(labels)
            unanimous += int(len(set(labels)) == 1)
        agreement[field] = {
            "complete_candidate_count": len(matrix),
            "unanimous_count": unanimous,
            "unanimous_fraction": unanimous / len(matrix) if matrix else None,
            "fleiss_kappa": fleiss_kappa(matrix) if matrix else None,
        }
        label_counts[field] = dict(sorted(counts.items()))
    latencies = [
        row["runtime"]["latency_ms"]
        for row in rows
        if isinstance(row.get("runtime"), dict)
        and isinstance(row["runtime"].get("latency_ms"), (int, float))
    ]
    error_count = len(rows) - len(valid_rows)
    return {
        "schema_version": "frankengate.wisp-recovery-model-stability-aggregate.v1",
        "claim_boundary": (
            "same-model prompt-perturbation stability; not human gold, independent "
            "model agreement, causal diagnosis, or prospective enterprise evidence"
        ),
        "sample": {
            "candidate_count": len(selected),
            "controlled_tool_family_counts": count_by_family(selected),
            "selection_ids_committed": False,
        },
        "execution": {
            "pass_count": len(pass_ids),
            "expected_decision_count": len(selected) * len(pass_ids),
            "valid_decision_count": len(valid_rows),
            "complete_candidate_count": complete_case_count,
            "error_count": error_count,
            "errored_fraction": error_count / len(rows) if rows else None,
            "latency_ms": {
                "median": statistics.median(latencies) if latencies else None,
                "maximum": max(latencies) if latencies else None,
            },
        },
        "agreement": agreement,
        "aggregate_label_counts": label_counts,
        "raw_candidate_level_rows_committed": False,
    }


def write_raw_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    os.chmod(path, 0o600)


def render_summary(result: dict[str, Any]) -> str:
    lines = [
        "# Wisp recovery local-model adjudication stability",
        "",
        "## Outcome",
        "",
        (
            f"Ran {result['execution']['valid_decision_count']} valid decisions across "
            f"{result['sample']['candidate_count']} blinded natural recovery candidates "
            f"and {result['execution']['pass_count']} prompt-order/skepticism variants."
        ),
        "",
        "| Field | Complete | Unanimous | Fraction | Fleiss kappa |",
        "|---|---:|---:|---:|---:|",
    ]
    for field, item in result["agreement"].items():
        fraction = item["unanimous_fraction"]
        kappa = item["fleiss_kappa"]
        lines.append(
            f"| `{field}` | {item['complete_candidate_count']} | "
            f"{item['unanimous_count']} | "
            f"{'n/a' if fraction is None else f'{fraction:.3f}'} | "
            f"{'n/a' if kappa is None else f'{kappa:.3f}'} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "This is a same-model stability diagnostic under three prompt variants. "
            "It is not human gold, independent-model agreement, causal diagnosis, "
            "or evidence that an enterprise intervention works. Low-stability fields "
            "must be sent to independent review; high stability only establishes that "
            "this pinned model is internally consistent on the sampled packet.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--packet-sha256", required=True)
    parser.add_argument("--model-manifest", type=Path, required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--model", default="default_model")
    parser.add_argument("--raw-output", type=Path, required=True)
    parser.add_argument("--aggregate-output", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path, required=True)
    parser.add_argument("--seed", default="wisp-recovery-model-stability-v1")
    parser.add_argument("--shell", type=int, default=6)
    parser.add_argument("--file-change", type=int, default=6)
    parser.add_argument("--file-read", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=float, default=120)
    parser.add_argument("--max-tokens", type=int, default=768)
    args = parser.parse_args()

    if sha256_file(args.packet) != args.packet_sha256:
        raise AdjudicationError("packet SHA-256 mismatch")
    packet = json.loads(args.packet.read_text(encoding="utf-8"))
    label_contract = packet["label_contract"]
    selected = select_stratified(
        packet["candidates"],
        {
            "shell": args.shell,
            "file_change": args.file_change,
            "file_read": args.file_read,
        },
        args.seed,
    )
    rows: list[dict[str, Any]] = []
    for variant in PROMPT_VARIANTS:
        for item in selected:
            prompt = build_prompt(item, label_contract, variant)
            row: dict[str, Any] = {
                "blind_id": item["blind_id"],
                "controlled_tool_family": item["controlled_tool_family"],
                "pass_id": variant,
                "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
            }
            try:
                content, runtime = call_chat_completion(
                    endpoint=args.endpoint,
                    model=args.model,
                    prompt=prompt,
                    timeout_seconds=args.timeout_seconds,
                    max_tokens=args.max_tokens,
                )
                row["runtime"] = runtime
                row["raw_response"] = content
                row["raw_response_sha256"] = hashlib.sha256(
                    content.encode("utf-8")
                ).hexdigest()
                row["labels"] = parse_and_validate(content, item, label_contract)
                row["status"] = "valid"
            except AdjudicationError as exc:
                row["status"] = "errored"
                row["error_type"] = str(exc)
            rows.append(row)
            write_raw_jsonl(args.raw_output, rows)
    result = aggregate(
        selected=selected,
        rows=rows,
        label_contract=label_contract,
        pass_ids=list(PROMPT_VARIANTS),
    )
    result.update(
        {
            "study_id": "wisp-recovery-model-adjudication-stability-2026-07-30",
            "packet_sha256": args.packet_sha256,
            "dataset": packet["dataset"],
            "model": {
                "request_model": args.model,
                "manifest": str(args.model_manifest),
                "manifest_sha256": sha256_file(args.model_manifest),
                "endpoint_location": "loopback",
                "temperature": 0,
            },
            "prompt_variants": [
                {
                    "id": variant,
                    "instruction_sha256": hashlib.sha256(
                        PROMPT_VARIANTS[variant].encode("utf-8")
                    ).hexdigest(),
                }
                for variant in PROMPT_VARIANTS
            ],
            "raw_output": {
                "committed": False,
                "sha256": sha256_file(args.raw_output),
                "mode": oct(args.raw_output.stat().st_mode & 0o777),
            },
        }
    )
    args.aggregate_output.parent.mkdir(parents=True, exist_ok=True)
    args.summary_output.parent.mkdir(parents=True, exist_ok=True)
    args.aggregate_output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    args.summary_output.write_text(render_summary(result), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
