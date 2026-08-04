"""Run a real local-model skill sensitivity test on the governed tool loop.

The fixture is synthetic and content-free.  It intentionally tests only whether
an added trace-mined procedure changes terminal native-tool compliance.  It is
not a benchmark-quality or enterprise-generalization result.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import native_tool_protocol_compliance as protocol


VARIANTS = ("no_skill", "formatting_placebo", "trace_mined_terminal_discipline")
BASE_PROMPT = protocol.BASE_SYSTEM_PROMPT
ARTIFACTS = {
    "no_skill": "",
    "formatting_placebo": (
        " Use short headings. Keep tool arguments compact. Use one sentence "
        "per explanation. Preserve the supplied tool names exactly."
    ),
    "trace_mined_terminal_discipline": (
        " Trace-mined procedure: inspect each tool result before acting; keep "
        "the attempt identifier from a successful result; once the requested "
        "tool budget is consumed, make exactly one terminal native call "
        "(submit_sql or abstain) and emit no prose-only response. Never issue "
        "another execute_sql call after the budget is exhausted."
    ),
}


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def run_experiment(
    *, fixture_path: Path, endpoint: str, model: str, raw_audit_dir: Path, output: Path
) -> dict[str, Any]:
    protocol.require_external_raw_path(raw_audit_dir)
    if output.exists():
        raise protocol.ProtocolExperimentError(f"refusing to overwrite {output}")
    value, limits, fixtures = _load_fixture_with_variants(fixture_path)
    api = protocol.ChatAPI(endpoint=endpoint, request_model_id=model)
    receipts: list[protocol.EpisodeReceipt] = []
    original_variants = protocol.VARIANT_IDS
    original_prompt = protocol.BASE_SYSTEM_PROMPT
    try:
        protocol.VARIANT_IDS = VARIANTS
        for fixture in fixtures:
            for variant in fixture.variant_order:
                protocol.BASE_SYSTEM_PROMPT = BASE_PROMPT + ARTIFACTS[variant]
                fixture_hash = hashlib.sha256(fixture.fixture_id.encode()).hexdigest()[:16]
                raw_path = raw_audit_dir / f"{fixture_hash}-{variant}.jsonl"
                receipts.append(
                    protocol.run_episode(
                        fixture=fixture,
                        variant=variant,
                        limits=limits,
                        api=api,
                        executor=protocol.SyntheticProtocolExecutor(fixture.executor_mode),
                        raw_audit_path=raw_path,
                    )
                )
    finally:
        protocol.BASE_SYSTEM_PROMPT = original_prompt
    protocol.VARIANT_IDS = VARIANTS
    aggregate = protocol.aggregate_receipts(
        receipts=receipts,
        fixture_manifest=value,
        fixture_sha256=hashlib.sha256(fixture_path.read_bytes()).hexdigest(),
        request_model_id=model,
    )
    protocol.VARIANT_IDS = original_variants
    aggregate.update(
        {
            "schema_version": "frankengate-natural-trace-skill-protocol-intervention-v1",
            "model": {"endpoint": endpoint, "request_model_id": model},
            "candidate_artifacts": {
                name: {
                    "classification": "baseline" if name == "no_skill" else "placebo" if name == "formatting_placebo" else "trace_mined_candidate",
                    "sha256": _sha256_text(text),
                }
                for name, text in ARTIFACTS.items()
            },
            "claim_boundary": {
                "real_model_tool_loop_executed": True,
                "skill_protocol_sensitivity_measured": True,
                "natural_trace_skill_benefit_confirmed": False,
                "enterprise_quality_estimated": False,
                "reason": "Synthetic content-free protocol only; no benchmark question, SQL quality, or enterprise outcome was evaluated.",
            },
            "raw_data_committed": False,
        }
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(aggregate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return aggregate


def _load_fixture_with_variants(path: Path) -> tuple[dict[str, Any], protocol.ProtocolLimits, tuple[protocol.Fixture, ...]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema_version") != protocol.FIXTURE_SCHEMA_VERSION:
        raise protocol.ProtocolExperimentError("unexpected fixture schema")
    if tuple(item.get("id") for item in value.get("variants", [])) != VARIANTS:
        raise protocol.ProtocolExperimentError("skill fixture variant order changed")
    limits = protocol.ProtocolLimits(**value["limits"])
    fixtures = tuple(
        protocol.Fixture(
            fixture_id=str(item["fixture_id"]),
            executor_mode=str(item["executor_mode"]),
            expected_terminal_action=str(item["expected_terminal_action"]),
            seed=int(item["seed"]),
            variant_order=tuple(item["variant_order"]),
        )
        for item in value["episodes"]
    )
    if any(set(f.variant_order) != set(VARIANTS) for f in fixtures):
        raise protocol.ProtocolExperimentError("fixture schedules are incomplete")
    return value, limits, fixtures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--raw-audit-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_experiment(
        fixture_path=args.fixture,
        endpoint=args.endpoint,
        model=args.model,
        raw_audit_dir=args.raw_audit_dir,
        output=args.output,
    )
    print(json.dumps({"status": "ok", "aggregate_sha256": protocol.sha256_value(result), "variants": result["variant_results"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
