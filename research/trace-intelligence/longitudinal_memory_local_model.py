#!/usr/bin/env python3
"""Run cutoff-safe longitudinal-memory state selection on a local model.

Raw trace content, evidence packs, and model responses are written only to an
explicit external audit directory. The committed result is aggregate-only.
The runner refuses non-loopback model endpoints.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
import time
from typing import Any, Mapping, Optional, Protocol, Sequence, Union
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import trace_commons_memory_composition as composition
import trace_commons_memory_conformance as native


SCHEMA_VERSION = "longitudinal-memory-local-model-result-v1"
RUNNER_VERSION = "longitudinal-memory-local-model-v1"
ARMS = (
    "no_memory",
    "verbatim",
    "latest_only",
    "contextual_bitemporal",
    "proposal_only_dream",
)
DECISIONS = {"select", "abstain"}
REASONS = {
    "exact_supported",
    "conflict",
    "interval_uncertainty",
    "insufficient",
    "wrong_context",
}
LOCAL_TOOL_ADAPTER_PROMPT = """For this loopback local runtime, do not answer in plain text.
Call submit_state_decision exactly once. Supply all three arguments. Use a
JSON null evidence_ref for abstain and one supplied evidence_ref for select."""
DECISION_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "submit_state_decision",
            "description": (
                "Submit the final contextual artifact state decision."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "decision": {
                        "type": "string",
                        "enum": sorted(DECISIONS),
                    },
                    "evidence_ref": {
                        "anyOf": [
                            {"type": "string"},
                            {"type": "null"},
                        ]
                    },
                    "reason": {
                        "type": "string",
                        "enum": sorted(REASONS),
                    },
                },
                "required": [
                    "decision",
                    "evidence_ref",
                    "reason",
                ],
                "additionalProperties": False,
            },
        },
    }
]


class LocalModelExperimentError(RuntimeError):
    """Content-free failure for a governed local-model experiment."""


def stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def require_external_path(path: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(repository_root())
    except ValueError:
        return resolved
    raise LocalModelExperimentError(
        "raw audit directory must be outside the repository"
    )


def require_loopback_endpoint(endpoint: str) -> str:
    parsed = urlparse(endpoint)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise LocalModelExperimentError(
            "model endpoint must be an explicit loopback HTTP endpoint"
        )
    return endpoint.rstrip("/")


def _write_raw(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
                default=str,
            )
            + "\n"
        )


@dataclass(frozen=True)
class EvidenceItem:
    evidence_ref: str
    canonical_content: str
    content_sha256: str
    observed_at: str
    source_kind: str
    project_key: str
    artifact_key: str


@dataclass(frozen=True)
class EvaluationLabel:
    target_content_sha256: str
    target_project_key: str
    interval_censored_change: bool


@dataclass(frozen=True)
class ModelUnit:
    unit_id: str
    source_label: str
    target_query: Mapping[str, Any]
    evidence_by_arm: Mapping[str, tuple[EvidenceItem, ...]]
    label: EvaluationLabel


@dataclass(frozen=True)
class ParsedDecision:
    decision: str
    evidence_ref: Optional[str]
    reason: str


class LocalChatAPI:
    def __init__(
        self,
        *,
        endpoint: str,
        request_model_id: str,
        timeout_seconds: int,
        max_completion_tokens: int,
    ) -> None:
        self.url = (
            require_loopback_endpoint(endpoint)
            + "/v1/chat/completions"
        )
        if not request_model_id:
            raise LocalModelExperimentError(
                "request model id is required"
            )
        self.request_model_id = request_model_id
        self.timeout_seconds = timeout_seconds
        self.max_completion_tokens = max_completion_tokens

    def complete(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        seed: int,
        tools: Optional[Sequence[Mapping[str, Any]]] = None,
    ) -> tuple[dict[str, Any], float]:
        payload = {
            "model": self.request_model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0,
            "top_p": 1,
            "seed": seed,
            "max_completion_tokens": self.max_completion_tokens,
            "stream": False,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        if tools:
            payload["tools"] = list(tools)
            payload["tool_choice"] = "required"
        request = Request(
            self.url,
            data=stable_json(payload).encode("utf-8"),
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        started = time.perf_counter()
        try:
            with urlopen(
                request,
                timeout=self.timeout_seconds,
            ) as response:
                body = response.read()
        except HTTPError as exc:
            exc.read()
            raise LocalModelExperimentError(
                f"local model returned HTTP status {exc.code}"
            ) from exc
        except (URLError, TimeoutError) as exc:
            raise LocalModelExperimentError(
                "local model request failed"
            ) from exc
        elapsed_ms = (time.perf_counter() - started) * 1_000
        try:
            value = json.loads(body)
        except json.JSONDecodeError as exc:
            raise LocalModelExperimentError(
                "local model returned invalid transport JSON"
            ) from exc
        if (
            not isinstance(value, dict)
            or not isinstance(value.get("choices"), list)
            or not value["choices"]
        ):
            raise LocalModelExperimentError(
                "local model response contains no choice"
            )
        return value, elapsed_ms


class TokenCounter(Protocol):
    def count(self, text: str) -> int:
        ...


class LocalTokenizerWorker:
    """One offline tokenizer subprocess shared by the complete experiment."""

    def __init__(
        self,
        *,
        python_executable: Path,
        worker_path: Path,
        model_snapshot: Path,
    ) -> None:
        if not python_executable.is_absolute():
            raise LocalModelExperimentError(
                "tokenizer Python path must be absolute"
            )
        if not model_snapshot.resolve(strict=True).is_dir():
            raise LocalModelExperimentError(
                "model snapshot must be a directory"
            )
        environment = {
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "PYTHONUNBUFFERED": "1",
        }
        self._process = subprocess.Popen(
            [
                str(python_executable),
                str(worker_path),
                "--snapshot",
                str(model_snapshot),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            env=environment,
        )

    def count(self, text: str) -> int:
        if (
            self._process.poll() is not None
            or self._process.stdin is None
            or self._process.stdout is None
        ):
            raise LocalModelExperimentError(
                "local tokenizer worker is unavailable"
            )
        self._process.stdin.write(
            json.dumps(
                {"text": text},
                ensure_ascii=False,
                separators=(",", ":"),
            )
            + "\n"
        )
        self._process.stdin.flush()
        response_line = self._process.stdout.readline()
        try:
            response = json.loads(response_line)
        except json.JSONDecodeError as exc:
            raise LocalModelExperimentError(
                "local tokenizer returned invalid protocol data"
            ) from exc
        if (
            not isinstance(response, dict)
            or response.get("status") != "ok"
            or not isinstance(response.get("tokens"), int)
            or response["tokens"] < 0
        ):
            raise LocalModelExperimentError(
                "local tokenizer rejected a request"
            )
        return int(response["tokens"])

    def close(self) -> None:
        if self._process.stdin is not None:
            self._process.stdin.close()
        try:
            self._process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self._process.terminate()
            self._process.wait(timeout=10)


def _cohort_state(
    manifest_path: Path,
    source_root: Path,
) -> tuple[
    native.VerifiedMemoryCohort,
    list[composition.QualifiedInteraction],
    list[composition.StateObservation],
    Mapping[str, Mapping[str, Optional[str]]],
    set[tuple[str, str]],
]:
    cohort = native.load_verified_memory_cohort(
        manifest_path,
        source_root,
        default_authority=composition.FIXED_IMPORT_AUTHORITY,
    )
    verified_receipt = composition._receipt_root(cohort.receipts)
    identity_key = hashlib.sha256(
        (
            verified_receipt
            + ":"
            + composition.ANALYSIS_VERSION
        ).encode("utf-8")
    ).digest()
    source_order = {
        str(receipt["path"]): index
        for index, receipt in enumerate(cohort.receipts)
    }
    interactions, _ = composition._qualifying_interactions(
        cohort,
        identity_key,
        source_order,
    )
    parents = composition._parent_maps(cohort.records)
    serial_pairs = composition._serial_session_pairs(cohort.records)
    observations, _ = composition._state_observations(
        interactions,
        parents,
        serial_pairs,
    )
    return cohort, interactions, observations, parents, serial_pairs


def build_model_units(
    source_specs: Sequence[tuple[str, Path, Path]],
) -> tuple[list[ModelUnit], dict[str, Any]]:
    """Build 17 cutoff-safe units and keep target labels separate."""

    units: list[ModelUnit] = []
    source_receipts: list[dict[str, Any]] = []
    for source_label, manifest_path, source_root in source_specs:
        (
            cohort,
            interactions,
            observations,
            parents,
            serial_pairs,
        ) = _cohort_state(manifest_path, source_root)
        interaction_by_event = {
            item.event_key: item for item in interactions
        }
        source_receipts.append(
            {
                "source_label": source_label,
                "manifest_sha256": sha256_file(manifest_path),
                "verified_source_set_sha256": (
                    composition._receipt_root(cohort.receipts)
                ),
                "records": len(cohort.records),
            }
        )
        for target in observations:
            if target.source_kind != "read":
                continue
            target_interaction = interaction_by_event[target.event_key]
            contextual = composition._online_candidates(
                observations,
                target,
                target_interaction,
                parents,
                serial_pairs,
                contextual=True,
            )
            if not contextual:
                continue
            latest = composition._online_candidates(
                observations,
                target,
                target_interaction,
                parents,
                serial_pairs,
                contextual=False,
            )[:1]
            if any(
                item.result_order >= target_interaction.call_order
                for item in [*contextual, *latest]
            ):
                raise LocalModelExperimentError(
                    "candidate cutoff invariant failed"
                )

            ordered_union = sorted(
                {
                    item.event_key: item
                    for item in [*contextual, *latest]
                }.values(),
                key=lambda item: item.result_order,
            )
            refs = {
                item.event_key: f"E{index:03d}"
                for index, item in enumerate(ordered_union, start=1)
            }

            def materialize(
                values: Sequence[composition.StateObservation],
            ) -> tuple[EvidenceItem, ...]:
                return tuple(
                    EvidenceItem(
                        evidence_ref=refs[item.event_key],
                        canonical_content=item.canonical_content,
                        content_sha256=item.content_sha256,
                        observed_at=item.observed_at.isoformat(),
                        source_kind=item.source_kind,
                        project_key=item.project_key,
                        artifact_key=item.artifact_key,
                    )
                    for item in values
                )

            contextual_items = materialize(contextual)
            unit_id = sha256_bytes(
                (
                    source_label
                    + "\0"
                    + target.event_key
                    + "\0"
                    + RUNNER_VERSION
                ).encode("utf-8")
            )
            target_query = {
                "request": (
                    "Select the pre-cutoff evidence item that best "
                    "establishes the current content of this requested "
                    "context artifact, or abstain."
                ),
                "artifact_path": target_interaction.path,
                "source_stratum": source_label,
                "project_context": target.project_key,
                "cutoff_observed_at": (
                    target_interaction.call.observed_at.isoformat()
                ),
            }
            units.append(
                ModelUnit(
                    unit_id=unit_id,
                    source_label=source_label,
                    target_query=target_query,
                    evidence_by_arm={
                        "no_memory": (),
                        "verbatim": contextual_items,
                        "latest_only": materialize(latest),
                        "contextual_bitemporal": contextual_items,
                        "proposal_only_dream": contextual_items,
                    },
                    label=EvaluationLabel(
                        target_content_sha256=target.content_sha256,
                        target_project_key=target.project_key,
                        interval_censored_change=(
                            target.interval_censored_change
                        ),
                    ),
                )
            )
    units.sort(key=lambda unit: (unit.source_label, unit.unit_id))
    return units, {
        "source_receipts": source_receipts,
        "units": len(units),
        "source_counts": dict(
            sorted(Counter(unit.source_label for unit in units).items())
        ),
    }


def model_pack(
    unit: ModelUnit,
    arm: str,
    evidence: Optional[Sequence[EvidenceItem]] = None,
) -> dict[str, Any]:
    """Return only pre-cutoff model material, never evaluator labels."""

    if arm not in ARMS:
        raise LocalModelExperimentError("unknown arm")
    selected_evidence = (
        tuple(evidence)
        if evidence is not None
        else unit.evidence_by_arm[arm]
    )
    if arm == "verbatim":
        serialized_evidence = [
            {
                "evidence_ref": item.evidence_ref,
                "content": item.canonical_content,
            }
            for item in selected_evidence
        ]
    else:
        serialized_evidence = [
            {
                "evidence_ref": item.evidence_ref,
                "content": item.canonical_content,
                "observed_at": item.observed_at,
                "source_kind": item.source_kind,
                "project_context": item.project_key,
                "artifact_context": item.artifact_key,
            }
            for item in selected_evidence
        ]
    return {
        "task": "context_artifact_state_selection",
        "arm": arm,
        "target_query": dict(unit.target_query),
        "eligible_pre_cutoff_evidence": serialized_evidence,
        "response_contract": {
            "decision": ["select", "abstain"],
            "evidence_ref": (
                "one supplied evidence_ref for select; null for abstain"
            ),
            "reason": sorted(REASONS),
            "additional_properties": False,
        },
    }


def budget_model_pack(
    unit: ModelUnit,
    arm: str,
    counter: TokenCounter,
    *,
    token_budget: int,
    candidate_limit: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply the frozen whole-item then UTF-8-safe tail policy."""

    if token_budget < 1 or candidate_limit < 1:
        raise LocalModelExperimentError(
            "evidence budget and candidate limit must be positive"
        )
    original = list(unit.evidence_by_arm[arm])
    selected = original[:candidate_limit]
    dropped_for_limit = max(0, len(original) - len(selected))

    def build(
        items: Sequence[EvidenceItem],
        *,
        truncated: bool,
        dropped_for_budget: int,
    ) -> dict[str, Any]:
        pack = model_pack(unit, arm, items)
        pack["evidence_budget_receipt"] = {
            "token_budget": token_budget,
            "candidate_limit": candidate_limit,
            "original_candidates": len(original),
            "included_candidates": len(items),
            "dropped_for_candidate_limit": dropped_for_limit,
            "dropped_for_token_budget": dropped_for_budget,
            "last_item_utf8_tail_truncated": truncated,
            # Reserve the final field during every budget decision so the
            # receipt itself cannot push an otherwise valid pack over limit.
            "final_pack_tokens": token_budget,
        }
        return pack

    dropped_for_budget = 0
    pack = build(
        selected,
        truncated=False,
        dropped_for_budget=dropped_for_budget,
    )
    count = counter.count(stable_json(pack))
    while count > token_budget and len(selected) > 1:
        selected.pop()
        dropped_for_budget += 1
        pack = build(
            selected,
            truncated=False,
            dropped_for_budget=dropped_for_budget,
        )
        count = counter.count(stable_json(pack))

    truncated = False
    if count > token_budget and selected:
        item = selected[-1]
        low = 0
        high = len(item.canonical_content)
        marker = "\n[UTF8_TAIL_TRUNCATED]"
        best: Optional[tuple[dict[str, Any], int]] = None
        while low <= high:
            midpoint = (low + high) // 2
            shortened = EvidenceItem(
                evidence_ref=item.evidence_ref,
                canonical_content=(
                    item.canonical_content[:midpoint] + marker
                ),
                content_sha256=item.content_sha256,
                observed_at=item.observed_at,
                source_kind=item.source_kind,
                project_key=item.project_key,
                artifact_key=item.artifact_key,
            )
            candidate_items = [*selected[:-1], shortened]
            candidate_pack = build(
                candidate_items,
                truncated=True,
                dropped_for_budget=dropped_for_budget,
            )
            candidate_count = counter.count(
                stable_json(candidate_pack)
            )
            if candidate_count <= token_budget:
                best = (candidate_pack, candidate_count)
                low = midpoint + 1
            else:
                high = midpoint - 1
        if best is None:
            selected = []
            dropped_for_budget += 1
            pack = build(
                selected,
                truncated=False,
                dropped_for_budget=dropped_for_budget,
            )
            count = counter.count(stable_json(pack))
        else:
            pack, count = best
            truncated = True

    if count > token_budget:
        raise LocalModelExperimentError(
            "target query and schema exceed evidence token budget"
        )
    pack["evidence_budget_receipt"][
        "last_item_utf8_tail_truncated"
    ] = truncated
    for _ in range(8):
        pack["evidence_budget_receipt"]["final_pack_tokens"] = count
        recount = counter.count(stable_json(pack))
        if recount == count:
            break
        count = recount
    else:
        raise LocalModelExperimentError(
            "evidence token receipt did not reach a fixed point"
        )
    if count > token_budget:
        raise LocalModelExperimentError(
            "budget receipt pushed pack over token ceiling"
        )
    return pack, dict(pack["evidence_budget_receipt"])


def parse_decision(response: Mapping[str, Any]) -> ParsedDecision:
    try:
        message = response["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LocalModelExperimentError(
            "local model response is missing content"
        ) from exc
    tool_calls = message.get("tool_calls") or []
    if tool_calls:
        if len(tool_calls) != 1:
            raise LocalModelExperimentError(
                "local model returned multiple decision tools"
            )
        function = tool_calls[0].get("function") or {}
        if function.get("name") != "submit_state_decision":
            raise LocalModelExperimentError(
                "local model called an unexpected decision tool"
            )
        arguments = function.get("arguments")
        if isinstance(arguments, str):
            candidate = arguments
        elif isinstance(arguments, dict):
            candidate = stable_json(arguments)
        else:
            raise LocalModelExperimentError(
                "local model tool arguments are invalid"
            )
    else:
        content = message.get("content")
        if not isinstance(content, str):
            raise LocalModelExperimentError(
                "local model content is not text"
            )
        candidate = content.strip()
        if candidate.startswith("```"):
            lines = candidate.splitlines()
            if len(lines) >= 3 and lines[-1].strip() == "```":
                candidate = "\n".join(lines[1:-1])
                if candidate.lstrip().startswith("json"):
                    candidate = candidate.lstrip()[4:].lstrip()
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise LocalModelExperimentError(
            "local model decision is not strict JSON"
        ) from exc
    if (
        isinstance(value, dict)
        and set(value) == {"decision", "reason"}
        and value.get("decision") == "abstain"
    ):
        # Frozen after the bounded local protocol smoke. MLX/Qwen omitted an
        # explicit JSON null in otherwise valid abstentions. This adapter is
        # semantic-preserving and is reported as a protocol accommodation.
        value = {**value, "evidence_ref": None}
    if not isinstance(value, dict) or set(value) != {
        "decision",
        "evidence_ref",
        "reason",
    }:
        raise LocalModelExperimentError(
            "local model decision has the wrong fields"
        )
    decision = value["decision"]
    evidence_ref = value["evidence_ref"]
    reason = value["reason"]
    if decision not in DECISIONS or reason not in REASONS:
        raise LocalModelExperimentError(
            "local model decision uses an invalid enum"
        )
    if decision == "select":
        if not isinstance(evidence_ref, str) or not evidence_ref:
            raise LocalModelExperimentError(
                "selected decision has no evidence reference"
            )
    elif evidence_ref is not None:
        raise LocalModelExperimentError(
            "abstention must have a null evidence reference"
        )
    return ParsedDecision(
        decision=decision,
        evidence_ref=evidence_ref,
        reason=reason,
    )


def evaluate_decision(
    unit: ModelUnit,
    arm: str,
    decision: ParsedDecision,
    supplied_refs: Optional[set[str]] = None,
) -> dict[str, Any]:
    supplied = {
        item.evidence_ref: item
        for item in unit.evidence_by_arm[arm]
        if supplied_refs is None or item.evidence_ref in supplied_refs
    }
    exact_refs = {
        ref
        for ref, item in supplied.items()
        if item.content_sha256 == unit.label.target_content_sha256
    }
    valid_reference = (
        decision.evidence_ref in supplied
        if decision.decision == "select"
        else decision.evidence_ref is None
    )
    selected = supplied.get(decision.evidence_ref or "")
    selected_exact = bool(
        selected is not None
        and selected.content_sha256
        == unit.label.target_content_sha256
    )
    selected_wrong_context = bool(
        selected is not None
        and selected.project_key != unit.label.target_project_key
    )
    correct_abstention = bool(
        decision.decision == "abstain" and not exact_refs
    )
    return {
        "valid_reference": valid_reference,
        "selected_exact": selected_exact,
        "selected_stale": bool(
            selected is not None and not selected_exact
        ),
        "selected_wrong_context": selected_wrong_context,
        "correct_abstention": correct_abstention,
        "exact_evidence_available": bool(exact_refs),
        "abstained": decision.decision == "abstain",
        "reason": decision.reason,
    }


def _mean(values: Sequence[float]) -> Optional[float]:
    return round(statistics.fmean(values), 6) if values else None


def _rate(numerator: int, denominator: int) -> dict[str, Any]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": (
            round(numerator / denominator, 12)
            if denominator
            else None
        ),
    }


def aggregate_runs(
    run_receipts: Sequence[Mapping[str, Any]],
    *,
    independent_runs: int,
) -> dict[str, Any]:
    by_arm: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    by_unit_arm: dict[
        tuple[str, str],
        list[Mapping[str, Any]],
    ] = defaultdict(list)
    for item in run_receipts:
        by_arm[str(item["arm"])].append(item)
        by_unit_arm[
            (str(item["unit_id"]), str(item["arm"]))
        ].append(item)
    result: dict[str, Any] = {}
    for arm in ARMS:
        values = by_arm[arm]
        valid = [item for item in values if item["status"] == "valid"]
        result[arm] = {
            "attempts": len(values),
            "valid_structured_outputs": _rate(len(valid), len(values)),
            "selected_exact": _rate(
                sum(bool(item.get("selected_exact")) for item in valid),
                len(valid),
            ),
            "selected_stale": _rate(
                sum(bool(item.get("selected_stale")) for item in valid),
                len(valid),
            ),
            "selected_wrong_context": _rate(
                sum(
                    bool(item.get("selected_wrong_context"))
                    for item in valid
                ),
                len(valid),
            ),
            "correct_abstention": _rate(
                sum(bool(item.get("correct_abstention")) for item in valid),
                len(valid),
            ),
            "valid_reference": _rate(
                sum(bool(item.get("valid_reference")) for item in valid),
                len(valid),
            ),
            "mean_elapsed_ms": _mean(
                [float(item["elapsed_ms"]) for item in values]
            ),
            "prompt_tokens": sum(
                int(item["prompt_tokens"]) for item in values
            ),
            "completion_tokens": sum(
                int(item["completion_tokens"]) for item in values
            ),
        }
    stability_units = 0
    complete_units = 0
    for values in by_unit_arm.values():
        valid = [item for item in values if item["status"] == "valid"]
        if len(valid) == independent_runs:
            complete_units += 1
            outputs = {
                str(item["normalized_decision_sha256"])
                for item in valid
            }
            stability_units += len(outputs) == 1
    return {
        "arms": result,
        "five_run_stability": _rate(
            stability_units,
            complete_units,
        ),
        "valid_complete_unit_arms": complete_units,
    }


def aggregate_budgets(
    receipts: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    by_arm: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for item in receipts:
        by_arm[str(item["arm"])].append(item)
    return {
        arm: {
            "packs": len(values),
            "token_budget": (
                int(values[0]["token_budget"]) if values else None
            ),
            "minimum_pack_tokens": (
                min(int(item["final_pack_tokens"]) for item in values)
                if values
                else None
            ),
            "maximum_pack_tokens": (
                max(int(item["final_pack_tokens"]) for item in values)
                if values
                else None
            ),
            "last_item_truncated": sum(
                bool(item["last_item_utf8_tail_truncated"])
                for item in values
            ),
            "items_dropped_for_candidate_limit": sum(
                int(item["dropped_for_candidate_limit"])
                for item in values
            ),
            "items_dropped_for_token_budget": sum(
                int(item["dropped_for_token_budget"])
                for item in values
            ),
        }
        for arm in ARMS
        for values in [by_arm[arm]]
    }


def run_experiment(
    *,
    source_specs: Sequence[tuple[str, Path, Path]],
    experiment_config_path: Path,
    model_manifest_path: Path,
    endpoint: str,
    raw_audit_dir: Path,
    independent_runs: int,
    timeout_seconds: int,
    max_completion_tokens: int,
    tokenizer_python: Path,
    model_snapshot: Path,
    unit_limit: Optional[int] = None,
) -> dict[str, Any]:
    raw_root = require_external_path(raw_audit_dir)
    raw_root.mkdir(parents=True, exist_ok=True)
    if any(raw_root.iterdir()):
        raise LocalModelExperimentError(
            "raw audit directory must start empty"
        )
    experiment_config = json.loads(
        experiment_config_path.read_text(encoding="utf-8")
    )
    model_manifest = json.loads(
        model_manifest_path.read_text(encoding="utf-8")
    )
    if (
        experiment_config.get("privacy_and_egress", {}).get(
            "authorized_internal_raw_analysis_allowed"
        )
        is not True
    ):
        raise LocalModelExperimentError(
            "experiment does not authorize internal raw analysis"
        )
    if (
        model_manifest.get("runtime", {}).get("server_binding")
        != "127.0.0.1"
    ):
        raise LocalModelExperimentError(
            "model manifest is not loopback-bound"
        )
    api = LocalChatAPI(
        endpoint=endpoint,
        request_model_id=str(model_manifest["request_model_id"]),
        timeout_seconds=timeout_seconds,
        max_completion_tokens=max_completion_tokens,
    )
    ranker_config_path = (
        Path(__file__).resolve().parent
        / "configs"
        / "experiments"
        / "trace-commons-memory-composition-2026.json"
    )
    ranker_config = json.loads(
        ranker_config_path.read_text(encoding="utf-8")
    )["ranker"]
    token_budget = int(ranker_config["evidence_pack_token_budget"])
    candidate_limit = int(ranker_config["candidate_limit"])
    tokenizer = LocalTokenizerWorker(
        python_executable=tokenizer_python,
        worker_path=(
            Path(__file__).resolve().parent
            / "local_tokenizer_worker.py"
        ),
        model_snapshot=model_snapshot,
    )
    units, unit_receipt = build_model_units(source_specs)
    if len(units) != 17:
        raise LocalModelExperimentError(
            "frozen census must contain exactly 17 model units"
        )
    selected_units = units[:unit_limit] if unit_limit else units
    system_prompt = str(
        experiment_config["model"]["state_decision_system_prompt"]
    )
    expected_prompt_sha = experiment_config["model"][
        "state_decision_system_prompt_sha256"
    ]
    if sha256_bytes(system_prompt.encode("utf-8")) != expected_prompt_sha:
        raise LocalModelExperimentError(
            "state decision prompt hash mismatch"
        )
    local_system_prompt = (
        system_prompt + "\n\n" + LOCAL_TOOL_ADAPTER_PROMPT
    )
    receipts: list[dict[str, Any]] = []
    budget_receipts: list[dict[str, Any]] = []
    try:
        for unit in selected_units:
            for arm in ARMS:
                pack, budget_receipt = budget_model_pack(
                    unit,
                    arm,
                    tokenizer,
                    token_budget=token_budget,
                    candidate_limit=candidate_limit,
                )
                budget_receipts.append(
                    {
                        "arm": arm,
                        **budget_receipt,
                    }
                )
                user_prompt = stable_json(pack)
                supplied_refs = {
                    str(item["evidence_ref"])
                    for item in pack["eligible_pre_cutoff_evidence"]
                }
                for run_index in range(independent_runs):
                    seed = 20260730 + run_index
                    raw_path = (
                        raw_root
                        / f"{unit.unit_id}-{arm}-{run_index}.jsonl"
                    )
                    _write_raw(
                        raw_path,
                        {
                            "event": "model_request",
                            "unit_id": unit.unit_id,
                            "source_label": unit.source_label,
                            "arm": arm,
                            "run_index": run_index,
                            "seed": seed,
                            "system_prompt": local_system_prompt,
                            "pack": pack,
                            "budget_receipt": budget_receipt,
                        },
                    )
                    started = time.perf_counter()
                    try:
                        response, elapsed_ms = api.complete(
                            system_prompt=local_system_prompt,
                            user_prompt=user_prompt,
                            seed=seed,
                            tools=DECISION_TOOLS,
                        )
                        _write_raw(
                            raw_path,
                            {
                                "event": "model_response",
                                "response": response,
                            },
                        )
                        decision = parse_decision(response)
                        if (
                            decision.decision == "select"
                            and decision.evidence_ref
                            not in supplied_refs
                        ):
                            raise LocalModelExperimentError(
                                "model selected an unsupplied evidence reference"
                            )
                        evaluated = evaluate_decision(
                            unit,
                            arm,
                            decision,
                            supplied_refs,
                        )
                        normalized = {
                            "decision": decision.decision,
                            "evidence_ref": decision.evidence_ref,
                            "reason": decision.reason,
                        }
                        usage = response.get("usage") or {}
                        receipt = {
                            "unit_id": unit.unit_id,
                            "source_label": unit.source_label,
                            "arm": arm,
                            "run_index": run_index,
                            "status": "valid",
                            **evaluated,
                            "normalized_decision_sha256": sha256_bytes(
                                stable_json(normalized).encode("utf-8")
                            ),
                            "elapsed_ms": round(elapsed_ms, 6),
                            "prompt_tokens": int(
                                usage.get("prompt_tokens") or 0
                            ),
                            "completion_tokens": int(
                                usage.get("completion_tokens") or 0
                            ),
                            "evidence_pack_tokens": int(
                                budget_receipt["final_pack_tokens"]
                            ),
                        }
                        _write_raw(
                            raw_path,
                            {
                                "event": "parsed_decision",
                                "parsed_decision": normalized,
                                "evaluation": evaluated,
                            },
                        )
                    except LocalModelExperimentError as exc:
                        elapsed_ms = (
                            time.perf_counter() - started
                        ) * 1_000
                        receipt = {
                            "unit_id": unit.unit_id,
                            "source_label": unit.source_label,
                            "arm": arm,
                            "run_index": run_index,
                            "status": "invalid",
                            "failure_class": type(exc).__name__,
                            "elapsed_ms": round(elapsed_ms, 6),
                            "prompt_tokens": 0,
                            "completion_tokens": 0,
                            "evidence_pack_tokens": int(
                                budget_receipt["final_pack_tokens"]
                            ),
                            "failure_code": str(exc),
                        }
                        _write_raw(
                            raw_path,
                            {
                                "event": "model_failure",
                                "failure_class": type(exc).__name__,
                                "failure_code": str(exc),
                            },
                        )
                    receipt["raw_audit_sha256"] = sha256_file(
                        raw_path
                    )
                    receipts.append(receipt)
    finally:
        tokenizer.close()

    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "runner_version": RUNNER_VERSION,
        "phase": (
            "bounded_mechanics_smoke"
            if unit_limit
            else "full_17_cutoff_local_model_replication"
        ),
        "input_receipts": {
            "experiment_config_sha256": sha256_file(
                experiment_config_path
            ),
            "model_manifest_sha256": sha256_file(model_manifest_path),
            "ranker_config_sha256": sha256_file(ranker_config_path),
            **unit_receipt,
        },
        "execution": {
            "endpoint_scope": "loopback_only",
            "model_id": model_manifest["model_id"],
            "model_revision": model_manifest["revision"],
            "request_model_id": model_manifest["request_model_id"],
            "independent_runs": independent_runs,
            "arms": list(ARMS),
            "units_executed": len(selected_units),
            "attempts": len(receipts),
            "raw_audit_external": True,
            "raw_content_committed": False,
            "third_party_egress": False,
            "evidence_pack_token_budget": token_budget,
            "candidate_limit": candidate_limit,
            "missing_abstention_null_normalized": True,
            "native_decision_tool_required": True,
            "local_tool_adapter_prompt_sha256": sha256_bytes(
                LOCAL_TOOL_ADAPTER_PROMPT.encode("utf-8")
            ),
            "decision_tool_schema_sha256": sha256_bytes(
                stable_json(DECISION_TOOLS).encode("utf-8")
            ),
        },
        "aggregate": aggregate_runs(
            receipts,
            independent_runs=independent_runs,
        ),
        "evidence_budget": aggregate_budgets(budget_receipts),
        "claim_boundary": {
            "exploratory_within_corpus": True,
            "model_is_pilot_only": True,
            "human_review_completed": False,
            "enterprise_generalization_allowed": False,
            "automatic_memory_promotion_allowed": False,
            "later_observation_is_hindsight_score_not_online_ground_truth": True,
        },
    }
    result["result_sha256"] = sha256_bytes(
        stable_json(result).encode("utf-8")
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace-commons-manifest", type=Path, required=True)
    parser.add_argument("--trace-commons-root", type=Path, required=True)
    parser.add_argument("--fable-manifest", type=Path, required=True)
    parser.add_argument("--fable-root", type=Path, required=True)
    parser.add_argument("--experiment-config", type=Path, required=True)
    parser.add_argument("--model-manifest", type=Path, required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8765")
    parser.add_argument("--raw-audit-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--independent-runs", type=int, default=5)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--max-completion-tokens", type=int, default=256)
    parser.add_argument("--tokenizer-python", type=Path, required=True)
    parser.add_argument("--model-snapshot", type=Path, required=True)
    parser.add_argument("--unit-limit", type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.independent_runs < 1:
        raise LocalModelExperimentError(
            "independent runs must be positive"
        )
    result = run_experiment(
        source_specs=(
            (
                "trace_commons",
                args.trace_commons_manifest,
                args.trace_commons_root,
            ),
            (
                "fable5_top_level",
                args.fable_manifest,
                args.fable_root,
            ),
        ),
        experiment_config_path=args.experiment_config,
        model_manifest_path=args.model_manifest,
        endpoint=args.endpoint,
        raw_audit_dir=args.raw_audit_dir,
        independent_runs=args.independent_runs,
        timeout_seconds=args.timeout_seconds,
        max_completion_tokens=args.max_completion_tokens,
        tokenizer_python=args.tokenizer_python,
        model_snapshot=args.model_snapshot,
        unit_limit=args.unit_limit,
    )
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        stable_json(
            {
                "status": "ok",
                "phase": result["phase"],
                "result_sha256": result["result_sha256"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
