#!/usr/bin/env python3
"""Causal protocol primitives for composed trace-intelligence experiments.

This module designs experiments; it does not execute retrieval, models, judges,
or tools.  Every mechanism is an independently switchable treatment so the
design can measure both isolated effects and interactions.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import enum
import hashlib
import itertools
import math
import re
import statistics
from typing import Dict, FrozenSet, Iterable, Optional, Sequence, Tuple


SCHEMA_VERSION = "frankengate-composed-system-factorial-v3"


class ProtocolError(ValueError):
    """The proposed experiment cannot support its claimed estimands."""


class Mechanism(str, enum.Enum):
    CHEAP_SIGNALS = "cheap_signals"
    EXACT_FTS_RETRIEVAL = "exact_fts_retrieval"
    SEMANTIC_RETRIEVAL = "semantic_retrieval"
    TEMPORAL_GRAPH_LEDGER = "temporal_graph_ledger"
    FAILURE_DIAGNOSIS = "failure_diagnosis"
    RELEASED_MEMORY_DREAM = "released_memory_dream"
    SKILL_SUGGESTIONS = "skill_suggestions"
    LLM_REASONING = "llm_reasoning"


ALL_MECHANISMS: Tuple[Mechanism, ...] = tuple(Mechanism)


@dataclasses.dataclass(frozen=True)
class FactorialArm:
    arm_id: str
    enabled: FrozenSet[Mechanism]


@dataclasses.dataclass(frozen=True)
class AuthorityContext:
    authority_epoch_ref: str
    tenant_id: str
    capabilities: FrozenSet[str]
    clearance: int
    purpose: str


@dataclasses.dataclass(frozen=True)
class EvidenceRecord:
    record_id: str
    source_id: str
    project_id: str
    tenant_id: str
    valid_at: dt.datetime
    known_at: dt.datetime
    allowed_purposes: FrozenSet[str]
    required_capabilities: FrozenSet[str]
    classification: int
    provenance_refs: Tuple[str, ...]
    origin_unit_id: Optional[str] = None
    tool_call_ids: Tuple[str, ...] = ()
    tool_outcome_ids: Tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True)
class ExperimentalUnit:
    unit_id: str
    source_id: str
    project_id: str
    split: str
    decision_at: dt.datetime
    target_available_at: dt.datetime
    target_ref: str
    authority: AuthorityContext
    evidence_record_ids: Tuple[str, ...]
    provenance_refs: Tuple[str, ...]
    tool_call_ids: Tuple[str, ...] = ()
    tool_outcome_ids: Tuple[str, ...] = ()

    @property
    def cluster_key(self) -> Tuple[str, str]:
        return (self.source_id, self.project_id)


@dataclasses.dataclass(frozen=True)
class MechanismArtifact:
    artifact_id: str
    mechanism: Mechanism
    manifest_sha256: str
    released_at: dt.datetime
    tenant_id: str
    allowed_purposes: FrozenSet[str]
    required_capabilities: FrozenSet[str]
    classification: int
    training_record_ids: Tuple[str, ...]
    provenance_refs: Tuple[str, ...]
    immutable: bool = True
    query_independent: bool = True
    required_upstreams: FrozenSet[Mechanism] = frozenset()


@dataclasses.dataclass(frozen=True)
class ProtocolSpec:
    seed: str
    repeats: int
    mechanisms: Tuple[Mechanism, ...] = ALL_MECHANISMS
    evaluation_splits: FrozenSet[str] = frozenset({"test"})


@dataclasses.dataclass(frozen=True)
class TreatmentOrder:
    unit_id: str
    repeat_index: int
    arm_ids: Tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class FactorialDesign:
    schema_version: str
    spec: ProtocolSpec
    arms: Tuple[FactorialArm, ...]
    analysis_unit_ids: Tuple[str, ...]
    cluster_keys: Tuple[Tuple[str, str], ...]
    treatment_orders: Tuple[TreatmentOrder, ...]
    units: Tuple[ExperimentalUnit, ...]
    records: Tuple[EvidenceRecord, ...]
    artifacts: Tuple[MechanismArtifact, ...]


@dataclasses.dataclass(frozen=True)
class ComponentOutcome:
    mechanism: Mechanism
    score: float
    success: bool
    provenance_refs: Tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class EndToEndOutcome:
    score: float
    success: bool
    abstained: bool
    provenance_refs: Tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class InvocationOutcome:
    unit_id: str
    arm_id: str
    repeat_index: int
    component_outcomes: Tuple[ComponentOutcome, ...]
    end_to_end: EndToEndOutcome
    tool_call_ids: Tuple[str, ...] = ()
    tool_outcome_ids: Tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True)
class CellAggregate:
    unit_id: str
    cluster_key: Tuple[str, str]
    arm_id: str
    enabled: FrozenSet[Mechanism]
    repeat_count: int
    end_to_end_score: float
    success_rate: float
    abstention_rate: float
    component_scores: Tuple[Tuple[Mechanism, float], ...]


@dataclasses.dataclass(frozen=True)
class AnalysisDataset:
    cells: Tuple[CellAggregate, ...]
    independent_unit_n: int
    source_project_cluster_n: int
    invocation_n: int
    repeats_are_precision_only: bool = True


@dataclasses.dataclass(frozen=True)
class EffectEstimate:
    kind: str
    mechanisms: Tuple[Mechanism, ...]
    estimate: float
    cluster_standard_error: Optional[float]
    independent_unit_n: int
    source_project_cluster_n: int
    weighting: str = "equal_source_project_cluster"


def _arm_id(
    enabled: FrozenSet[Mechanism],
    mechanism_order: Sequence[Mechanism],
) -> str:
    bits = "".join("1" if item in enabled else "0" for item in mechanism_order)
    return "arm-" + bits


def full_factorial_arms(
    mechanisms: Sequence[Mechanism],
) -> Tuple[FactorialArm, ...]:
    """Return the complete 2^k treatment lattice in a stable order."""

    order = tuple(mechanisms)
    if len(order) != len(set(order)):
        raise ProtocolError("mechanisms must be unique")
    if any(not isinstance(item, Mechanism) for item in order):
        raise ProtocolError("unknown mechanism")
    arms = []
    for assignment in itertools.product((False, True), repeat=len(order)):
        enabled = frozenset(
            mechanism
            for mechanism, active in zip(order, assignment)
            if active
        )
        arms.append(
            FactorialArm(
                arm_id=_arm_id(enabled, order),
                enabled=enabled,
            )
        )
    return tuple(arms)


def _require_aware(value: dt.datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ProtocolError(f"{field} must be timezone-aware")


def _unique_index(values: Iterable[object], field: str) -> Dict[str, object]:
    result: Dict[str, object] = {}
    for value in values:
        key = str(getattr(value, field))
        if not key:
            raise ProtocolError(f"{field} must not be empty")
        if key in result:
            raise ProtocolError(f"duplicate {field}: {key}")
        result[key] = value
    return result


def _validate_tool_completeness(
    call_ids: Sequence[str],
    outcome_ids: Sequence[str],
    owner: str,
) -> None:
    if len(call_ids) != len(set(call_ids)):
        raise ProtocolError(f"{owner}: duplicate tool call IDs")
    if len(outcome_ids) != len(set(outcome_ids)):
        raise ProtocolError(f"{owner}: duplicate tool outcome IDs")
    if set(call_ids) != set(outcome_ids):
        missing = sorted(set(call_ids) - set(outcome_ids))
        unexpected = sorted(set(outcome_ids) - set(call_ids))
        raise ProtocolError(
            f"{owner}: incomplete tool trace "
            f"(missing={missing}, unexpected={unexpected})"
        )


def _validate_authorized(
    authority: AuthorityContext,
    *,
    tenant_id: str,
    allowed_purposes: FrozenSet[str],
    required_capabilities: FrozenSet[str],
    classification: int,
    owner: str,
) -> None:
    if not authority.authority_epoch_ref:
        raise ProtocolError(f"{owner}: authority epoch is required")
    if authority.tenant_id != tenant_id:
        raise ProtocolError(f"{owner}: cross-tenant input")
    if authority.purpose not in allowed_purposes:
        raise ProtocolError(f"{owner}: purpose is not authorized")
    if not required_capabilities.issubset(authority.capabilities):
        raise ProtocolError(f"{owner}: required capability is missing")
    if classification > authority.clearance:
        raise ProtocolError(f"{owner}: classification exceeds clearance")


def _validate_common(
    spec: ProtocolSpec,
    units: Tuple[ExperimentalUnit, ...],
    records: Tuple[EvidenceRecord, ...],
    artifacts: Tuple[MechanismArtifact, ...],
) -> Tuple[
    Dict[str, ExperimentalUnit],
    Dict[str, EvidenceRecord],
    Dict[Mechanism, MechanismArtifact],
]:
    if not spec.seed:
        raise ProtocolError("a frozen randomization seed is required")
    if spec.repeats < 1:
        raise ProtocolError("repeats must be positive")
    if not spec.evaluation_splits:
        raise ProtocolError("at least one evaluation split is required")
    if len(spec.mechanisms) != len(set(spec.mechanisms)):
        raise ProtocolError("mechanisms must be unique")

    unit_by_id = _unique_index(units, "unit_id")
    record_by_id = _unique_index(records, "record_id")
    _unique_index(artifacts, "artifact_id")
    artifact_by_mechanism: Dict[Mechanism, MechanismArtifact] = {}
    for artifact in artifacts:
        if artifact.mechanism in artifact_by_mechanism:
            raise ProtocolError(
                f"duplicate artifact for {artifact.mechanism.value}"
            )
        artifact_by_mechanism[artifact.mechanism] = artifact
    if set(artifact_by_mechanism) != set(spec.mechanisms):
        raise ProtocolError(
            "exactly one frozen artifact is required per mechanism"
        )

    cluster_splits: Dict[Tuple[str, str], str] = {}
    allowed_splits = {"train", "selection", "test"}
    for unit in units:
        if not unit.source_id or not unit.project_id:
            raise ProtocolError(
                f"{unit.unit_id}: source_id and project_id are required"
            )
        if unit.split not in allowed_splits:
            raise ProtocolError(f"{unit.unit_id}: unknown split {unit.split}")
        prior = cluster_splits.setdefault(unit.cluster_key, unit.split)
        if prior != unit.split:
            raise ProtocolError(
                f"{unit.cluster_key}: source/project cluster crosses splits"
            )
        _require_aware(unit.decision_at, f"{unit.unit_id}.decision_at")
        _require_aware(
            unit.target_available_at,
            f"{unit.unit_id}.target_available_at",
        )
        if unit.target_available_at <= unit.decision_at:
            raise ProtocolError(
                f"{unit.unit_id}: target is available at decision time"
            )
        if not unit.provenance_refs:
            raise ProtocolError(f"{unit.unit_id}: provenance is required")
        if unit.target_ref in unit.provenance_refs:
            raise ProtocolError(
                f"{unit.unit_id}: target leaked into unit provenance"
            )
        _validate_tool_completeness(
            unit.tool_call_ids,
            unit.tool_outcome_ids,
            unit.unit_id,
        )

    for record in records:
        if not record.source_id or not record.project_id:
            raise ProtocolError(
                f"{record.record_id}: source_id and project_id are required"
            )
        _require_aware(record.valid_at, f"{record.record_id}.valid_at")
        _require_aware(record.known_at, f"{record.record_id}.known_at")
        if not record.provenance_refs:
            raise ProtocolError(
                f"{record.record_id}: provenance is required"
            )
        _validate_tool_completeness(
            record.tool_call_ids,
            record.tool_outcome_ids,
            record.record_id,
        )
        if record.origin_unit_id is not None:
            origin = unit_by_id.get(record.origin_unit_id)
            if origin is None:
                raise ProtocolError(
                    f"{record.record_id}: unknown origin unit "
                    f"{record.origin_unit_id}"
                )
            if (record.source_id, record.project_id) != origin.cluster_key:
                raise ProtocolError(
                    f"{record.record_id}: origin cluster mismatch"
                )

    for artifact in artifacts:
        _require_aware(
            artifact.released_at,
            f"{artifact.artifact_id}.released_at",
        )
        if not re.fullmatch(r"[0-9a-f]{64}", artifact.manifest_sha256):
            raise ProtocolError(
                f"{artifact.artifact_id}: manifest SHA-256 is invalid"
            )
        if not artifact.immutable:
            raise ProtocolError(
                f"{artifact.artifact_id}: release must be immutable"
            )
        if not artifact.provenance_refs:
            raise ProtocolError(
                f"{artifact.artifact_id}: provenance is required"
            )
        if artifact.required_upstreams:
            raise ProtocolError(
                f"{artifact.artifact_id}: hard upstream dependencies "
                "break independent factorial activation"
            )
        if (
            artifact.mechanism is Mechanism.RELEASED_MEMORY_DREAM
            and not artifact.query_independent
        ):
            raise ProtocolError(
                f"{artifact.artifact_id}: memory/dream release must be "
                "query-independent"
            )
        for record_id in artifact.training_record_ids:
            record = record_by_id.get(record_id)
            if record is None:
                raise ProtocolError(
                    f"{artifact.artifact_id}: unknown training record "
                    f"{record_id}"
                )
            if (
                record.valid_at > artifact.released_at
                or record.known_at > artifact.released_at
            ):
                raise ProtocolError(
                    f"{artifact.artifact_id}: trained on future evidence"
                )
            if record.origin_unit_id is not None:
                origin = unit_by_id[record.origin_unit_id]
                if origin.split != "train":
                    raise ProtocolError(
                        f"{artifact.artifact_id}: circular training from "
                        f"{origin.split} unit {origin.unit_id}"
                    )

    return unit_by_id, record_by_id, artifact_by_mechanism


def _treatment_orders(
    spec: ProtocolSpec,
    units: Sequence[ExperimentalUnit],
    arms: Sequence[FactorialArm],
) -> Tuple[TreatmentOrder, ...]:
    result = []
    for unit in units:
        ranked = sorted(
            arms,
            key=lambda arm: hashlib.sha256(
                (
                    spec.seed
                    + "\x1f"
                    + unit.unit_id
                    + "\x1f"
                    + arm.arm_id
                ).encode("utf-8")
            ).hexdigest(),
        )
        if not ranked:
            continue
        step_seed = int(
            hashlib.sha256(
                (spec.seed + "\x1f" + unit.unit_id + "\x1forder").encode(
                    "utf-8"
                )
            ).hexdigest(),
            16,
        )
        candidate = (step_seed % len(ranked)) or 1
        while math.gcd(candidate, len(ranked)) != 1:
            candidate = (candidate + 1) % len(ranked) or 1
        for repeat_index in range(spec.repeats):
            offset = (repeat_index * candidate) % len(ranked)
            ordered = ranked[offset:] + ranked[:offset]
            result.append(
                TreatmentOrder(
                    unit_id=unit.unit_id,
                    repeat_index=repeat_index,
                    arm_ids=tuple(arm.arm_id for arm in ordered),
                )
            )
    return tuple(result)


def compile_design(
    spec: ProtocolSpec,
    units: Sequence[ExperimentalUnit],
    records: Sequence[EvidenceRecord],
    artifacts: Sequence[MechanismArtifact],
) -> FactorialDesign:
    """Validate governance and time boundaries, then freeze the factorial."""

    frozen_units = tuple(units)
    frozen_records = tuple(records)
    frozen_artifacts = tuple(artifacts)
    _, record_by_id, artifact_by_mechanism = _validate_common(
        spec,
        frozen_units,
        frozen_records,
        frozen_artifacts,
    )
    analysis_units = tuple(
        unit
        for unit in frozen_units
        if unit.split in spec.evaluation_splits
    )
    if not analysis_units:
        raise ProtocolError("no units are present in the evaluation splits")

    eval_clusters = {unit.cluster_key for unit in analysis_units}
    for artifact in frozen_artifacts:
        for record_id in artifact.training_record_ids:
            record = record_by_id[record_id]
            if (record.source_id, record.project_id) in eval_clusters:
                raise ProtocolError(
                    f"{artifact.artifact_id}: training cluster overlaps "
                    "an evaluation source/project cluster"
                )

    for unit in analysis_units:
        if len(unit.evidence_record_ids) != len(
            set(unit.evidence_record_ids)
        ):
            raise ProtocolError(
                f"{unit.unit_id}: duplicate evidence record reference"
            )
        for record_id in unit.evidence_record_ids:
            record = record_by_id.get(record_id)
            if record is None:
                raise ProtocolError(
                    f"{unit.unit_id}: unknown evidence record {record_id}"
                )
            if (
                record.valid_at > unit.decision_at
                or record.known_at > unit.decision_at
            ):
                raise ProtocolError(
                    f"{unit.unit_id}: future evidence {record.record_id}"
                )
            if record.record_id == unit.target_ref:
                raise ProtocolError(
                    f"{unit.unit_id}: target supplied as evidence"
                )
            if unit.target_ref in record.provenance_refs:
                raise ProtocolError(
                    f"{unit.unit_id}: target leaked through evidence provenance"
                )
            _validate_authorized(
                unit.authority,
                tenant_id=record.tenant_id,
                allowed_purposes=record.allowed_purposes,
                required_capabilities=record.required_capabilities,
                classification=record.classification,
                owner=record.record_id,
            )
        for mechanism in spec.mechanisms:
            artifact = artifact_by_mechanism[mechanism]
            if artifact.released_at > unit.decision_at:
                raise ProtocolError(
                    f"{unit.unit_id}: unreleased artifact "
                    f"{artifact.artifact_id}"
                )
            _validate_authorized(
                unit.authority,
                tenant_id=artifact.tenant_id,
                allowed_purposes=artifact.allowed_purposes,
                required_capabilities=artifact.required_capabilities,
                classification=artifact.classification,
                owner=artifact.artifact_id,
            )
            if unit.target_ref in artifact.provenance_refs:
                raise ProtocolError(
                    f"{unit.unit_id}: target leaked through artifact provenance"
                )
            for training_record_id in artifact.training_record_ids:
                training_record = record_by_id[training_record_id]
                if (
                    training_record.record_id == unit.target_ref
                    or unit.target_ref in training_record.provenance_refs
                ):
                    raise ProtocolError(
                        f"{unit.unit_id}: target leaked into artifact training"
                    )

    arms = full_factorial_arms(spec.mechanisms)
    return FactorialDesign(
        schema_version=SCHEMA_VERSION,
        spec=spec,
        arms=arms,
        analysis_unit_ids=tuple(sorted(unit.unit_id for unit in analysis_units)),
        cluster_keys=tuple(sorted({unit.cluster_key for unit in analysis_units})),
        treatment_orders=_treatment_orders(spec, analysis_units, arms),
        units=frozen_units,
        records=frozen_records,
        artifacts=frozen_artifacts,
    )


def _validate_score(score: float, owner: str) -> None:
    if not math.isfinite(score) or score < 0.0 or score > 1.0:
        raise ProtocolError(f"{owner}: score must be finite and in [0, 1]")


def aggregate_outcomes(
    design: FactorialDesign,
    outcomes: Sequence[InvocationOutcome],
) -> AnalysisDataset:
    """Validate complete run receipts and collapse repeats within each cell."""

    unit_by_id = {unit.unit_id: unit for unit in design.units}
    record_by_id = {record.record_id: record for record in design.records}
    arm_by_id = {arm.arm_id: arm for arm in design.arms}
    artifact_by_mechanism = {
        artifact.mechanism: artifact for artifact in design.artifacts
    }
    expected = {
        (order.unit_id, arm_id, order.repeat_index)
        for order in design.treatment_orders
        for arm_id in order.arm_ids
    }
    outcome_by_key: Dict[
        Tuple[str, str, int],
        InvocationOutcome,
    ] = {}
    for outcome in outcomes:
        key = (outcome.unit_id, outcome.arm_id, outcome.repeat_index)
        if key in outcome_by_key:
            raise ProtocolError(f"duplicate invocation outcome: {key}")
        if key not in expected:
            raise ProtocolError(f"unexpected invocation outcome: {key}")
        outcome_by_key[key] = outcome

        unit = unit_by_id[outcome.unit_id]
        arm = arm_by_id[outcome.arm_id]
        _validate_tool_completeness(
            outcome.tool_call_ids,
            outcome.tool_outcome_ids,
            str(key),
        )
        components = {
            component.mechanism: component
            for component in outcome.component_outcomes
        }
        if len(components) != len(outcome.component_outcomes):
            raise ProtocolError(f"{key}: duplicate component outcome")
        if set(components) != set(arm.enabled):
            raise ProtocolError(
                f"{key}: component outcomes do not match active treatments"
            )

        allowed_refs = set(unit.provenance_refs)
        required_end_refs = set(unit.provenance_refs)
        for record_id in unit.evidence_record_ids:
            record = record_by_id[record_id]
            allowed_refs.add(record_id)
            allowed_refs.update(record.provenance_refs)
            required_end_refs.add(record_id)
        for mechanism in arm.enabled:
            artifact = artifact_by_mechanism[mechanism]
            allowed_refs.add(artifact.artifact_id)
            allowed_refs.update(artifact.provenance_refs)
            required_end_refs.add(artifact.artifact_id)

        for mechanism, component in components.items():
            _validate_score(
                component.score,
                f"{key}:{mechanism.value}",
            )
            refs = set(component.provenance_refs)
            artifact_id = artifact_by_mechanism[mechanism].artifact_id
            if artifact_id not in refs:
                raise ProtocolError(
                    f"{key}:{mechanism.value}: artifact provenance missing"
                )
            if unit.target_ref in refs:
                raise ProtocolError(
                    f"{key}:{mechanism.value}: target provenance leaked"
                )
            if not refs.issubset(allowed_refs):
                raise ProtocolError(
                    f"{key}:{mechanism.value}: undeclared provenance input"
                )

        _validate_score(outcome.end_to_end.score, f"{key}:end_to_end")
        end_refs = set(outcome.end_to_end.provenance_refs)
        if unit.target_ref in end_refs:
            raise ProtocolError(f"{key}: target provenance leaked")
        if not required_end_refs.issubset(end_refs):
            raise ProtocolError(
                f"{key}: end-to-end provenance is incomplete"
            )
        if not end_refs.issubset(allowed_refs):
            raise ProtocolError(
                f"{key}: end-to-end provenance has undeclared inputs"
            )

    missing = expected - set(outcome_by_key)
    if missing:
        first = sorted(missing)[0]
        raise ProtocolError(
            f"incomplete factorial run; first missing invocation: {first}"
        )

    by_cell: Dict[
        Tuple[str, str],
        list,
    ] = {}
    for outcome in outcomes:
        by_cell.setdefault(
            (outcome.unit_id, outcome.arm_id),
            [],
        ).append(outcome)

    cells = []
    for (unit_id, arm_id), repeats in sorted(by_cell.items()):
        unit = unit_by_id[unit_id]
        arm = arm_by_id[arm_id]
        component_scores = []
        for mechanism in sorted(arm.enabled, key=lambda item: item.value):
            component_scores.append(
                (
                    mechanism,
                    statistics.fmean(
                        next(
                            component.score
                            for component in repeat.component_outcomes
                            if component.mechanism is mechanism
                        )
                        for repeat in repeats
                    ),
                )
            )
        cells.append(
            CellAggregate(
                unit_id=unit_id,
                cluster_key=unit.cluster_key,
                arm_id=arm_id,
                enabled=arm.enabled,
                repeat_count=len(repeats),
                end_to_end_score=statistics.fmean(
                    item.end_to_end.score for item in repeats
                ),
                success_rate=statistics.fmean(
                    float(item.end_to_end.success) for item in repeats
                ),
                abstention_rate=statistics.fmean(
                    float(item.end_to_end.abstained) for item in repeats
                ),
                component_scores=tuple(component_scores),
            )
        )
    return AnalysisDataset(
        cells=tuple(cells),
        independent_unit_n=len(design.analysis_unit_ids),
        source_project_cluster_n=len(design.cluster_keys),
        invocation_n=len(outcomes),
    )


def _cluster_weighted_estimate(
    unit_contrasts: Dict[str, float],
    unit_by_id: Dict[str, ExperimentalUnit],
) -> Tuple[float, Optional[float], int]:
    by_cluster: Dict[Tuple[str, str], list] = {}
    for unit_id, contrast in unit_contrasts.items():
        by_cluster.setdefault(
            unit_by_id[unit_id].cluster_key,
            [],
        ).append(contrast)
    cluster_contrasts = [
        statistics.fmean(values)
        for _, values in sorted(by_cluster.items())
    ]
    estimate = statistics.fmean(cluster_contrasts)
    standard_error = None
    if len(cluster_contrasts) >= 2:
        standard_error = statistics.stdev(cluster_contrasts) / math.sqrt(
            len(cluster_contrasts)
        )
    return estimate, standard_error, len(cluster_contrasts)


def estimate_effects(
    design: FactorialDesign,
    dataset: AnalysisDataset,
) -> Tuple[EffectEstimate, ...]:
    """Estimate cluster-weighted main effects and pairwise interactions.

    Each repeat has already been collapsed inside a unit-by-arm cell.  Thus
    neither treatment repeats nor prolific projects inflate the denominator.
    """

    unit_by_id = {
        unit.unit_id: unit
        for unit in design.units
        if unit.unit_id in design.analysis_unit_ids
    }
    expected_enabled = {arm.enabled for arm in design.arms}
    scores: Dict[str, Dict[FrozenSet[Mechanism], float]] = {}
    for cell in dataset.cells:
        if cell.unit_id not in unit_by_id:
            raise ProtocolError(
                f"effect dataset contains unknown unit {cell.unit_id}"
            )
        unit_scores = scores.setdefault(cell.unit_id, {})
        if cell.enabled in unit_scores:
            raise ProtocolError(
                f"duplicate aggregate cell: {cell.unit_id}/{cell.arm_id}"
            )
        unit_scores[cell.enabled] = cell.end_to_end_score
    if set(scores) != set(design.analysis_unit_ids):
        raise ProtocolError("effect dataset has incomplete unit coverage")
    for unit_id, unit_scores in scores.items():
        if set(unit_scores) != expected_enabled:
            raise ProtocolError(
                f"{unit_id}: effect dataset has incomplete arm coverage"
            )

    estimates = []
    for mechanism in design.spec.mechanisms:
        contrasts = {}
        for unit_id, unit_scores in scores.items():
            active = [
                score
                for enabled, score in unit_scores.items()
                if mechanism in enabled
            ]
            inactive = [
                score
                for enabled, score in unit_scores.items()
                if mechanism not in enabled
            ]
            contrasts[unit_id] = (
                statistics.fmean(active) - statistics.fmean(inactive)
            )
        estimate, standard_error, cluster_n = _cluster_weighted_estimate(
            contrasts,
            unit_by_id,
        )
        estimates.append(
            EffectEstimate(
                kind="main_effect",
                mechanisms=(mechanism,),
                estimate=estimate,
                cluster_standard_error=standard_error,
                independent_unit_n=len(contrasts),
                source_project_cluster_n=cluster_n,
            )
        )

    for left, right in itertools.combinations(design.spec.mechanisms, 2):
        contrasts = {}
        for unit_id, unit_scores in scores.items():
            by_assignment = {}
            for left_active, right_active in itertools.product(
                (False, True),
                repeat=2,
            ):
                values = [
                    score
                    for enabled, score in unit_scores.items()
                    if (left in enabled) is left_active
                    and (right in enabled) is right_active
                ]
                by_assignment[(left_active, right_active)] = (
                    statistics.fmean(values)
                )
            contrasts[unit_id] = (
                by_assignment[(True, True)]
                - by_assignment[(True, False)]
                - by_assignment[(False, True)]
                + by_assignment[(False, False)]
            )
        estimate, standard_error, cluster_n = _cluster_weighted_estimate(
            contrasts,
            unit_by_id,
        )
        estimates.append(
            EffectEstimate(
                kind="pairwise_interaction",
                mechanisms=(left, right),
                estimate=estimate,
                cluster_standard_error=standard_error,
                independent_unit_n=len(contrasts),
                source_project_cluster_n=cluster_n,
            )
        )
    return tuple(estimates)
