"""Run a bounded GEPA arm over the governed native-tool protocol fixture.

The adapter deliberately exposes only content-free episode identifiers,
terminal outcomes, and failure codes to GEPA's reflective dataset.  The model
and raw request/response records remain in an external audit directory.  This
is an optimizer-integration and protocol-quality experiment; it is not a
semantic SQL or enterprise-skill result.

GEPA is loaded from the separately pinned v0.1.4 checkout at runtime.  Keeping
that dependency external prevents an optimizer's transitive dependencies from
silently becoming part of Frankengate's production runtime.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import native_tool_protocol_compliance as protocol


SCHEMA_VERSION = "frankengate-gepa-native-tool-protocol.v1"
GEPA_REVISION = "8b0ce6cd99a234f6b74daf37558a2ac0ce18f975"
GEPA_TAG = "v0.1.4"
OPTIMIZER_VARIANT = "trace_mined_terminal_discipline"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    )


def _content_free_fixture(fixture: protocol.Fixture) -> dict[str, Any]:
    return {
        "fixture_id_sha256": sha256_bytes(fixture.fixture_id.encode()),
        "executor_mode": fixture.executor_mode,
        "expected_terminal_action": fixture.expected_terminal_action,
        "seed": fixture.seed,
    }


class ProtocolAdapter:
    """Minimal GEPA adapter for the synthetic governed tool protocol."""

    # Explicitly advertise that the default GEPA reflective proposer should be
    # used.  GEPA accesses this optional protocol member at runtime rather than
    # through a structural ``hasattr`` guard.
    propose_new_texts = None

    def __init__(
        self,
        *,
        fixtures: Sequence[protocol.Fixture],
        limits: protocol.ProtocolLimits,
        api: protocol.ModelAPI,
        raw_dir: Path,
    ) -> None:
        self.fixtures = {item.fixture_id: item for item in fixtures}
        self.limits = limits
        self.api = api
        self.raw_dir = raw_dir
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self._counter = 0

    def _run_one(self, fixture: protocol.Fixture, candidate_text: str) -> protocol.EpisodeReceipt:
        candidate_hash = sha256_bytes(candidate_text.encode())[:16]
        fixture_hash = sha256_bytes(fixture.fixture_id.encode())[:16]
        raw = self.raw_dir / f"{self._counter:04d}-{fixture_hash}-{candidate_hash}.jsonl"
        self._counter += 1
        # GEPA evaluates one candidate at a time.  The fixed variant keeps the
        # tool schedule identical across candidates; only the candidate text
        # changes.
        old_prompt = protocol.BASE_SYSTEM_PROMPT
        old_variants = protocol.VARIANT_IDS
        try:
            protocol.VARIANT_IDS = (
                "no_skill",
                "formatting_placebo",
                OPTIMIZER_VARIANT,
            )
            protocol.BASE_SYSTEM_PROMPT = (
                old_prompt
                + ("\n\n" + candidate_text.strip() if candidate_text.strip() else "")
            )
            return protocol.run_episode(
                fixture=fixture,
                variant=OPTIMIZER_VARIANT,
                limits=self.limits,
                api=self.api,
                executor=protocol.SyntheticProtocolExecutor(fixture.executor_mode),
                raw_audit_path=raw,
            )
        finally:
            protocol.BASE_SYSTEM_PROMPT = old_prompt
            protocol.VARIANT_IDS = old_variants

    def evaluate(
        self,
        batch: list[dict[str, Any]],
        candidate: dict[str, str],
        capture_traces: bool = False,
    ) -> Any:
        from gepa.core.adapter import EvaluationBatch

        text = str(candidate.get("instruction", ""))
        outputs: list[dict[str, Any]] = []
        scores: list[float] = []
        trajectories: list[dict[str, Any]] | None = [] if capture_traces else None
        for item in batch:
            fixture_id = str(item["fixture_id"])
            fixture = self.fixtures[fixture_id]
            receipt = self._run_one(fixture, text)
            score = 1.0 if receipt.expected_terminal_match else 0.0
            scores.append(score)
            outputs.append(
                {
                    "terminal_action": receipt.terminal_action,
                    "expected_terminal_match": receipt.expected_terminal_match,
                    "terminal_failure_code": receipt.terminal_failure_code,
                }
            )
            if trajectories is not None:
                trajectories.append(
                    {
                        "fixture": _content_free_fixture(fixture),
                        "terminal_action": receipt.terminal_action,
                        "expected_terminal_action": receipt.expected_terminal_action,
                        "expected_terminal_match": receipt.expected_terminal_match,
                        "terminal_failure_code": receipt.terminal_failure_code,
                        "model_calls": receipt.model_calls,
                        "native_tool_calls": receipt.native_tool_calls,
                    }
                )
        return EvaluationBatch(outputs=outputs, scores=scores, trajectories=trajectories)

    def make_reflective_dataset(
        self,
        candidate: dict[str, str],
        eval_batch: Any,
        components_to_update: list[str],
    ) -> Mapping[str, Sequence[Mapping[str, Any]]]:
        if components_to_update != ["instruction"]:
            raise ValueError("the experiment has exactly one optimizable component")
        rows: list[dict[str, Any]] = []
        for trajectory in eval_batch.trajectories or []:
            if trajectory["expected_terminal_match"]:
                continue
            rows.append(
                {
                    "Inputs": trajectory["fixture"],
                    "Generated Outputs": {
                        "terminal_action": trajectory["terminal_action"],
                        "expected_terminal_action": trajectory["expected_terminal_action"],
                    },
                    "Feedback": {
                        "failure_code": trajectory["terminal_failure_code"],
                        "model_calls": trajectory["model_calls"],
                        "native_tool_calls": trajectory["native_tool_calls"],
                    },
                }
            )
        if not rows:
            rows.append({"Inputs": {"status": "all_passed"}, "Generated Outputs": {}, "Feedback": {}})
        return {"instruction": rows}


class OllamaReflection:
    """Small local `/api/chat` reflection callable; no external egress."""

    def __init__(self, *, endpoint: str, model: str, timeout_seconds: int = 120) -> None:
        self.url = endpoint.rstrip("/") + "/api/chat"
        self.model = model
        self.timeout_seconds = timeout_seconds

    def __call__(self, prompt: str) -> str:
        from urllib.request import Request, urlopen

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You propose one short, general instruction for a synthetic "
                        "tool-protocol agent. Return only the instruction text."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": {"temperature": 0, "seed": 17},
        }
        request = Request(
            self.url,
            data=json.dumps(payload, sort_keys=True).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=self.timeout_seconds) as response:
            value = json.loads(response.read())
        message = value.get("message") if isinstance(value, dict) else None
        content = message.get("content") if isinstance(message, dict) else ""
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("reflection model returned no text")
        return content.strip()


def _run_baseline(adapter: ProtocolAdapter, rows: list[dict[str, Any]]) -> dict[str, Any]:
    result = adapter.evaluate(rows, {"instruction": ""}, capture_traces=False)
    return {
        "tasks": len(rows),
        "matches": sum(result.scores),
        "match_rate": sum(result.scores) / len(rows) if rows else None,
    }


def run_experiment(
    *,
    fixture_path: Path,
    endpoint: str,
    model: str,
    reflection_model: str,
    raw_dir: Path,
    output: Path,
    run_dir: Path,
    max_metric_calls: int,
) -> dict[str, Any]:
    old_variants = protocol.VARIANT_IDS
    protocol.VARIANT_IDS = (
        "no_skill",
        "formatting_placebo",
        OPTIMIZER_VARIANT,
    )
    try:
        fixture_manifest, limits, fixtures = protocol.load_fixture(fixture_path)
    finally:
        protocol.VARIANT_IDS = old_variants
    # Fixed family-disjoint split over the synthetic fixture: the first three
    # episodes train proposals and the last three are held out until selection.
    train_fixtures = fixtures[:3]
    val_fixtures = fixtures[3:]
    train = [{"fixture_id": item.fixture_id} for item in train_fixtures]
    val = [{"fixture_id": item.fixture_id} for item in val_fixtures]
    api = protocol.ChatAPI(endpoint=endpoint, request_model_id=model)
    adapter = ProtocolAdapter(fixtures=fixtures, limits=limits, api=api, raw_dir=raw_dir)
    baseline_train = _run_baseline(adapter, train)
    baseline_val = _run_baseline(adapter, val)

    import gepa

    result = gepa.optimize(
        seed_candidate={"instruction": ""},
        trainset=train,
        valset=val,
        adapter=adapter,
        reflection_lm=OllamaReflection(endpoint=endpoint, model=reflection_model),
        max_metric_calls=max_metric_calls,
        reflection_minibatch_size=min(2, len(train)),
        candidate_selection_strategy="pareto",
        frontier_type="instance",
        acceptance_criterion="strict_improvement",
        skip_perfect_score=False,
        seed=17,
        run_dir=str(run_dir),
        display_progress_bar=False,
        raise_on_exception=True,
    )

    best = dict(result.best_candidate)
    optimized_train = _run_baseline(adapter, train) if not best.get("instruction") else None
    # Evaluate the selected candidate independently after optimization.  The
    # helper is named baseline for its compact aggregate shape only.
    selected = adapter.evaluate(val, best, capture_traces=False)
    selected_val = {
        "tasks": len(val),
        "matches": sum(selected.scores),
        "match_rate": sum(selected.scores) / len(val) if val else None,
    }
    candidate_text = str(best.get("instruction", ""))
    output_value = {
        "schema_version": SCHEMA_VERSION,
        "experiment_class": "gepa_bounded_optimizer_protocol_quality",
        "optimizer": {
            "name": "GEPA",
            "tag": GEPA_TAG,
            "source_revision": GEPA_REVISION,
            "source_checkout": "/private/tmp/gepa-v0.1.4-research",
            "max_metric_calls": max_metric_calls,
            "train_count": len(train),
            "holdout_count": len(val),
        },
        "model": {
            "task_model": model,
            "reflection_model": reflection_model,
            "harness": "ollama-openai-compatible-task-plus-native-reflection",
            "endpoint_scope": "loopback-only",
        },
        "fixture": {
            "manifest_sha256": sha256_bytes(fixture_path.read_bytes()),
            "train": [_content_free_fixture(item) for item in train_fixtures],
            "holdout": [_content_free_fixture(item) for item in val_fixtures],
        },
        "baseline": {"train": baseline_train, "holdout": baseline_val},
        "selected": {
            "train": optimized_train,
            "holdout": selected_val,
            "candidate_sha256": sha256_bytes(candidate_text.encode()),
            "candidate_characters": len(candidate_text),
            "gepa_total_metric_calls": result.total_metric_calls,
        },
        "claim_boundary": {
            "optimizer_executed": True,
            "holdout_split_used": True,
            "semantic_quality_estimated": False,
            "enterprise_skill_benefit_confirmed": False,
            "automatic_promotion_authorized": False,
            "raw_model_content_committed": False,
            "reason": (
                "The fixture measures only native terminal-tool protocol compliance. "
                "A positive holdout result would validate optimizer plumbing, not "
                "enterprise task quality or causal user-skill improvement."
            ),
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(output_value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--reflection-model", required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-metric-calls", type=int, default=8)
    args = parser.parse_args()
    result = run_experiment(
        fixture_path=args.fixture,
        endpoint=args.endpoint,
        model=args.model,
        reflection_model=args.reflection_model,
        raw_dir=args.raw_dir,
        output=args.output,
        run_dir=args.run_dir,
        max_metric_calls=args.max_metric_calls,
    )
    print(json.dumps({"status": "ok", "result_sha256": sha256_json(result)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
