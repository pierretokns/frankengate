from __future__ import annotations

import datetime as dt
import dataclasses
import unittest

import composed_system_factorial_v3 as factorial


UTC = dt.timezone.utc


def valid_inputs(mechanisms=None, repeats=2):
    train_time = dt.datetime(2026, 1, 1, tzinfo=UTC)
    decision_time = dt.datetime(2026, 7, 1, tzinfo=UTC)
    authority = factorial.AuthorityContext(
        authority_epoch_ref="epoch-7",
        tenant_id="enterprise-a",
        capabilities=frozenset({"trace:read", "artifact:use"}),
        clearance=3,
        purpose="quality_improvement",
    )
    units = (
        factorial.ExperimentalUnit(
            unit_id="train-1",
            source_id="source-a",
            project_id="project-a",
            split="train",
            decision_at=train_time,
            target_available_at=train_time + dt.timedelta(days=1),
            target_ref="target:train-1",
            authority=authority,
            evidence_record_ids=(),
            provenance_refs=("trace:train-1",),
        ),
        factorial.ExperimentalUnit(
            unit_id="eval-1",
            source_id="source-b",
            project_id="project-b",
            split="test",
            decision_at=decision_time,
            target_available_at=decision_time + dt.timedelta(days=1),
            target_ref="target:eval-1",
            authority=authority,
            evidence_record_ids=("record:history",),
            provenance_refs=("trace:eval-1",),
            tool_call_ids=("call-1",),
            tool_outcome_ids=("call-1",),
        ),
    )
    records = (
        factorial.EvidenceRecord(
            record_id="record:training",
            source_id="source-a",
            project_id="project-a",
            tenant_id="enterprise-a",
            valid_at=train_time - dt.timedelta(days=2),
            known_at=train_time - dt.timedelta(days=1),
            allowed_purposes=frozenset({"quality_improvement"}),
            required_capabilities=frozenset({"trace:read"}),
            classification=2,
            provenance_refs=("raw:training",),
            origin_unit_id="train-1",
        ),
        factorial.EvidenceRecord(
            record_id="record:history",
            source_id="source-b",
            project_id="project-b",
            tenant_id="enterprise-a",
            valid_at=decision_time - dt.timedelta(days=2),
            known_at=decision_time - dt.timedelta(days=1),
            allowed_purposes=frozenset({"quality_improvement"}),
            required_capabilities=frozenset({"trace:read"}),
            classification=2,
            provenance_refs=("raw:history",),
            tool_call_ids=("historical-call",),
            tool_outcome_ids=("historical-call",),
        ),
    )
    if mechanisms is None:
        mechanisms = (
            factorial.Mechanism.CHEAP_SIGNALS,
            factorial.Mechanism.SEMANTIC_RETRIEVAL,
        )
    artifacts = tuple(
        factorial.MechanismArtifact(
            artifact_id=f"artifact:{mechanism.value}",
            mechanism=mechanism,
            manifest_sha256=(format(index + 1, "x") * 64)[:64],
            released_at=train_time + dt.timedelta(days=2),
            tenant_id="enterprise-a",
            allowed_purposes=frozenset({"quality_improvement"}),
            required_capabilities=frozenset({"artifact:use"}),
            classification=2,
            training_record_ids=("record:training",),
            provenance_refs=(f"manifest:{mechanism.value}",),
        )
        for index, mechanism in enumerate(mechanisms)
    )
    spec = factorial.ProtocolSpec(
        seed="frozen-seed-20260730",
        repeats=repeats,
        mechanisms=tuple(mechanisms),
    )
    return spec, units, records, artifacts


def complete_outcomes(design, score_for_arm=None):
    unit_by_id = {unit.unit_id: unit for unit in design.units}
    arm_by_id = {arm.arm_id: arm for arm in design.arms}
    artifact_by_mechanism = {
        artifact.mechanism: artifact for artifact in design.artifacts
    }
    outcomes = []
    for treatment_order in design.treatment_orders:
        unit = unit_by_id[treatment_order.unit_id]
        for arm_id in treatment_order.arm_ids:
            arm = arm_by_id[arm_id]
            score = (
                score_for_arm(arm)
                if score_for_arm is not None
                else len(arm.enabled) / max(1, len(design.spec.mechanisms))
            )
            artifact_ids = tuple(
                artifact_by_mechanism[mechanism].artifact_id
                for mechanism in sorted(arm.enabled, key=lambda item: item.value)
            )
            provenance = (
                unit.provenance_refs
                + unit.evidence_record_ids
                + artifact_ids
            )
            components = tuple(
                factorial.ComponentOutcome(
                    mechanism=mechanism,
                    score=score,
                    success=score >= 0.5,
                    provenance_refs=(
                        artifact_by_mechanism[mechanism].artifact_id,
                    ),
                )
                for mechanism in sorted(arm.enabled, key=lambda item: item.value)
            )
            outcomes.append(
                factorial.InvocationOutcome(
                    unit_id=unit.unit_id,
                    arm_id=arm.arm_id,
                    repeat_index=treatment_order.repeat_index,
                    component_outcomes=components,
                    end_to_end=factorial.EndToEndOutcome(
                        score=score,
                        success=score >= 0.5,
                        abstained=False,
                        provenance_refs=provenance,
                    ),
                    tool_call_ids=("runtime-call",),
                    tool_outcome_ids=("runtime-call",),
                )
            )
    return tuple(outcomes)


class ComposedSystemFactorialV3Test(unittest.TestCase):
    def test_full_factorial_exposes_every_mechanism_alone_and_together(self) -> None:
        arms = factorial.full_factorial_arms(factorial.ALL_MECHANISMS)

        self.assertEqual(2 ** len(factorial.ALL_MECHANISMS), len(arms))
        enabled_sets = {arm.enabled for arm in arms}
        self.assertIn(frozenset(), enabled_sets)
        self.assertIn(frozenset(factorial.ALL_MECHANISMS), enabled_sets)
        for mechanism in factorial.ALL_MECHANISMS:
            self.assertIn(frozenset({mechanism}), enabled_sets)

    def test_compiler_builds_reproducible_randomized_orders_for_test_units(self) -> None:
        spec, units, records, artifacts = valid_inputs()

        first = factorial.compile_design(spec, units, records, artifacts)
        second = factorial.compile_design(spec, units, records, artifacts)

        self.assertEqual(first, second)
        self.assertEqual(("eval-1",), first.analysis_unit_ids)
        self.assertEqual(4, len(first.arms))
        self.assertEqual(2, len(first.treatment_orders))
        for order in first.treatment_orders:
            self.assertEqual(
                {arm.arm_id for arm in first.arms},
                set(order.arm_ids),
            )
        self.assertNotEqual(
            first.treatment_orders[0].arm_ids,
            first.treatment_orders[1].arm_ids,
        )

    def test_repeats_are_precision_runs_not_independent_samples(self) -> None:
        spec, units, records, artifacts = valid_inputs(repeats=3)
        design = factorial.compile_design(spec, units, records, artifacts)

        dataset = factorial.aggregate_outcomes(
            design,
            complete_outcomes(design),
        )

        self.assertEqual(1, dataset.independent_unit_n)
        self.assertEqual(1, dataset.source_project_cluster_n)
        self.assertEqual(12, dataset.invocation_n)
        self.assertEqual(4, len(dataset.cells))
        self.assertTrue(dataset.repeats_are_precision_only)
        self.assertTrue(all(cell.repeat_count == 3 for cell in dataset.cells))

    def test_main_effects_and_interactions_use_cluster_level_contrasts(self) -> None:
        mechanisms = (
            factorial.Mechanism.CHEAP_SIGNALS,
            factorial.Mechanism.FAILURE_DIAGNOSIS,
        )
        spec, units, records, artifacts = valid_inputs(
            mechanisms=mechanisms,
            repeats=2,
        )
        design = factorial.compile_design(spec, units, records, artifacts)

        def score(arm):
            cheap = factorial.Mechanism.CHEAP_SIGNALS in arm.enabled
            diagnosis = (
                factorial.Mechanism.FAILURE_DIAGNOSIS in arm.enabled
            )
            return (
                0.1
                + 0.2 * cheap
                + 0.3 * diagnosis
                + 0.4 * cheap * diagnosis
            )

        dataset = factorial.aggregate_outcomes(
            design,
            complete_outcomes(design, score),
        )
        effects = factorial.estimate_effects(design, dataset)
        by_factors = {
            effect.mechanisms: effect for effect in effects
        }

        self.assertAlmostEqual(
            0.4,
            by_factors[
                (factorial.Mechanism.CHEAP_SIGNALS,)
            ].estimate,
        )
        self.assertAlmostEqual(
            0.5,
            by_factors[
                (factorial.Mechanism.FAILURE_DIAGNOSIS,)
            ].estimate,
        )
        interaction = by_factors[mechanisms]
        self.assertEqual("pairwise_interaction", interaction.kind)
        self.assertAlmostEqual(0.4, interaction.estimate)
        self.assertEqual(1, interaction.source_project_cluster_n)
        self.assertEqual(1, interaction.independent_unit_n)
        self.assertIsNone(interaction.cluster_standard_error)

    def test_target_cannot_hide_inside_evidence_provenance(self) -> None:
        spec, units, records, artifacts = valid_inputs()
        records = (
            records[0],
            dataclasses.replace(
                records[1],
                provenance_refs=("raw:history", "target:eval-1"),
            ),
        )

        with self.assertRaisesRegex(
            factorial.ProtocolError,
            "target.*evidence provenance",
        ):
            factorial.compile_design(spec, units, records, artifacts)

    def test_source_project_cluster_cannot_cross_train_and_test(self) -> None:
        spec, units, records, artifacts = valid_inputs()
        units = (
            units[0],
            dataclasses.replace(
                units[1],
                source_id=units[0].source_id,
                project_id=units[0].project_id,
            ),
        )

        with self.assertRaisesRegex(
            factorial.ProtocolError,
            "source/project cluster crosses splits",
        ):
            factorial.compile_design(spec, units, records, artifacts)

    def test_source_and_project_cluster_identifiers_are_required(self) -> None:
        spec, units, records, artifacts = valid_inputs()
        for field in ("source_id", "project_id"):
            with self.subTest(field=field):
                changed_units = (
                    units[0],
                    dataclasses.replace(units[1], **{field: ""}),
                )
                with self.assertRaisesRegex(
                    factorial.ProtocolError,
                    "source_id and project_id",
                ):
                    factorial.compile_design(
                        spec,
                        changed_units,
                        records,
                        artifacts,
                    )

    def test_future_valid_or_known_evidence_is_never_available(self) -> None:
        spec, units, records, artifacts = valid_inputs()
        future = units[1].decision_at + dt.timedelta(seconds=1)
        for field in ("valid_at", "known_at"):
            with self.subTest(field=field):
                changed = dataclasses.replace(records[1], **{field: future})
                with self.assertRaisesRegex(
                    factorial.ProtocolError,
                    "future evidence",
                ):
                    factorial.compile_design(
                        spec,
                        units,
                        (records[0], changed),
                        artifacts,
                    )

    def test_authority_epoch_tenant_purpose_and_clearance_are_enforced(self) -> None:
        spec, units, records, artifacts = valid_inputs()
        cases = {
            "epoch": (
                dataclasses.replace(
                    units[1].authority,
                    authority_epoch_ref="",
                ),
                "authority epoch",
            ),
            "tenant": (
                dataclasses.replace(
                    units[1].authority,
                    tenant_id="enterprise-b",
                ),
                "cross-tenant",
            ),
            "purpose": (
                dataclasses.replace(
                    units[1].authority,
                    purpose="unrelated_marketing",
                ),
                "purpose is not authorized",
            ),
            "classification": (
                dataclasses.replace(
                    units[1].authority,
                    clearance=1,
                ),
                "classification exceeds clearance",
            ),
        }
        for case, (authority, message) in cases.items():
            with self.subTest(case=case):
                changed_units = (
                    units[0],
                    dataclasses.replace(units[1], authority=authority),
                )
                with self.assertRaisesRegex(
                    factorial.ProtocolError,
                    message,
                ):
                    factorial.compile_design(
                        spec,
                        changed_units,
                        records,
                        artifacts,
                    )

    def test_trace_tool_calls_require_exact_terminal_outcomes(self) -> None:
        spec, units, records, artifacts = valid_inputs()
        units = (
            units[0],
            dataclasses.replace(units[1], tool_outcome_ids=()),
        )

        with self.assertRaisesRegex(
            factorial.ProtocolError,
            "incomplete tool trace",
        ):
            factorial.compile_design(spec, units, records, artifacts)

    def test_artifacts_must_be_released_before_each_decision(self) -> None:
        spec, units, records, artifacts = valid_inputs()
        artifacts = (
            dataclasses.replace(
                artifacts[0],
                released_at=units[1].decision_at + dt.timedelta(seconds=1),
            ),
            artifacts[1],
        )

        with self.assertRaisesRegex(
            factorial.ProtocolError,
            "unreleased artifact",
        ):
            factorial.compile_design(spec, units, records, artifacts)

    def test_artifact_training_cannot_use_future_valid_evidence(self) -> None:
        spec, units, records, artifacts = valid_inputs()
        records = (
            dataclasses.replace(
                records[0],
                valid_at=artifacts[0].released_at + dt.timedelta(seconds=1),
            ),
            records[1],
        )

        with self.assertRaisesRegex(
            factorial.ProtocolError,
            "trained on future evidence",
        ):
            factorial.compile_design(spec, units, records, artifacts)

    def test_memory_dream_release_must_be_query_independent(self) -> None:
        mechanisms = (factorial.Mechanism.RELEASED_MEMORY_DREAM,)
        spec, units, records, artifacts = valid_inputs(
            mechanisms=mechanisms,
        )
        artifacts = (
            dataclasses.replace(artifacts[0], query_independent=False),
        )

        with self.assertRaisesRegex(
            factorial.ProtocolError,
            "query-independent",
        ):
            factorial.compile_design(spec, units, records, artifacts)

    def test_evaluation_trace_cannot_train_a_treatment_artifact(self) -> None:
        spec, units, records, artifacts = valid_inputs()
        early_history = dataclasses.replace(
            records[1],
            valid_at=dt.datetime(2026, 1, 31, tzinfo=UTC),
            known_at=dt.datetime(2026, 2, 1, tzinfo=UTC),
            origin_unit_id="eval-1",
        )
        artifacts = (
            dataclasses.replace(
                artifacts[0],
                released_at=dt.datetime(2026, 3, 1, tzinfo=UTC),
                training_record_ids=("record:history",),
            ),
            artifacts[1],
        )

        with self.assertRaisesRegex(
            factorial.ProtocolError,
            "circular training",
        ):
            factorial.compile_design(
                spec,
                units,
                (records[0], early_history),
                artifacts,
            )

    def test_evidence_origin_must_match_its_source_project_cluster(self) -> None:
        spec, units, records, artifacts = valid_inputs()
        records = (
            dataclasses.replace(records[0], project_id="spoofed-project"),
            records[1],
        )

        with self.assertRaisesRegex(
            factorial.ProtocolError,
            "origin cluster mismatch",
        ):
            factorial.compile_design(spec, units, records, artifacts)

    def test_hard_component_dependency_is_invalid_for_full_factorial(self) -> None:
        spec, units, records, artifacts = valid_inputs()
        artifacts = (
            dataclasses.replace(
                artifacts[0],
                required_upstreams=frozenset(
                    {factorial.Mechanism.SEMANTIC_RETRIEVAL}
                ),
            ),
            artifacts[1],
        )

        with self.assertRaisesRegex(
            factorial.ProtocolError,
            "break independent factorial activation",
        ):
            factorial.compile_design(spec, units, records, artifacts)

    def test_missing_invocation_makes_the_factorial_incomplete(self) -> None:
        spec, units, records, artifacts = valid_inputs()
        design = factorial.compile_design(spec, units, records, artifacts)
        outcomes = complete_outcomes(design)

        with self.assertRaisesRegex(
            factorial.ProtocolError,
            "incomplete factorial run",
        ):
            factorial.aggregate_outcomes(design, outcomes[:-1])

    def test_duplicate_invocation_cannot_double_count_a_cell(self) -> None:
        spec, units, records, artifacts = valid_inputs()
        design = factorial.compile_design(spec, units, records, artifacts)
        outcomes = complete_outcomes(design)

        with self.assertRaisesRegex(
            factorial.ProtocolError,
            "duplicate invocation outcome",
        ):
            factorial.aggregate_outcomes(
                design,
                outcomes + (outcomes[0],),
            )

    def test_runtime_receipt_rejects_undeclared_provenance(self) -> None:
        spec, units, records, artifacts = valid_inputs()
        design = factorial.compile_design(spec, units, records, artifacts)
        outcomes = list(complete_outcomes(design))
        outcomes[0] = dataclasses.replace(
            outcomes[0],
            end_to_end=dataclasses.replace(
                outcomes[0].end_to_end,
                provenance_refs=(
                    outcomes[0].end_to_end.provenance_refs
                    + ("undeclared:oracle-label",)
                ),
            ),
        )

        with self.assertRaisesRegex(
            factorial.ProtocolError,
            "undeclared inputs",
        ):
            factorial.aggregate_outcomes(design, outcomes)

    def test_component_outcomes_must_match_the_active_arm(self) -> None:
        spec, units, records, artifacts = valid_inputs()
        design = factorial.compile_design(spec, units, records, artifacts)
        outcomes = list(complete_outcomes(design))
        baseline_index = next(
            index
            for index, outcome in enumerate(outcomes)
            if not next(
                arm
                for arm in design.arms
                if arm.arm_id == outcome.arm_id
            ).enabled
        )
        outcomes[baseline_index] = dataclasses.replace(
            outcomes[baseline_index],
            component_outcomes=(
                factorial.ComponentOutcome(
                    mechanism=factorial.Mechanism.CHEAP_SIGNALS,
                    score=0.0,
                    success=False,
                    provenance_refs=("artifact:cheap_signals",),
                ),
            ),
        )

        with self.assertRaisesRegex(
            factorial.ProtocolError,
            "do not match active treatments",
        ):
            factorial.aggregate_outcomes(design, outcomes)

    def test_runtime_tool_calls_also_require_terminal_outcomes(self) -> None:
        spec, units, records, artifacts = valid_inputs()
        design = factorial.compile_design(spec, units, records, artifacts)
        outcomes = list(complete_outcomes(design))
        outcomes[0] = dataclasses.replace(
            outcomes[0],
            tool_outcome_ids=(),
        )

        with self.assertRaisesRegex(
            factorial.ProtocolError,
            "incomplete tool trace",
        ):
            factorial.aggregate_outcomes(design, outcomes)


if __name__ == "__main__":
    unittest.main()
