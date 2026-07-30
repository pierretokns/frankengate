import base64
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from otel_collector_roundtrip import (  # noqa: E402
    COLLECTOR_DARWIN_ARM64_ARCHIVE_SHA256,
    COLLECTOR_DARWIN_ARM64_BINARY_SHA256,
    COLLECTOR_VERSION,
    OTEL_GO_VERSION,
    SDK_MANIFEST_VERSION,
    _normalize_id,
    _stable_json,
    analyze_roundtrip,
    build_sdk_manifest,
    run_experiment,
)


FIXTURES = ROOT / "fixtures" / "governed-v1"


def collector_batch(manifest):
    spans = []
    for source in manifest["spans"]:
        span = copy.deepcopy(source)
        is_error = span.pop("statusError")
        span["kind"] = 1
        span["status"] = {
            "code": "STATUS_CODE_ERROR" if is_error else "STATUS_CODE_UNSET"
        }
        spans.append(span)
    return [
        {
            "resourceSpans": [
                {
                    "resource": {
                        "attributes": copy.deepcopy(
                            manifest["resourceAttributes"]
                        )
                    },
                    "schemaUrl": manifest["resourceSchemaUrl"],
                    "scopeSpans": [
                        {
                            "scope": {
                                "name": manifest["scopeName"],
                                "version": manifest["scopeVersion"],
                            },
                            "spans": spans,
                        }
                    ],
                }
            ]
        }
    ]


class OTelCollectorRoundTripTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, cls.oracle = build_sdk_manifest(FIXTURES)

    def test_manifest_is_content_minimized_and_complete(self):
        serialized = _stable_json(self.manifest)
        self.assertEqual(SDK_MANIFEST_VERSION, self.manifest["schemaVersion"])
        self.assertEqual(48, len(self.manifest["spans"]))
        for fixture in FIXTURES.glob("*.json"):
            source = json.loads(fixture.read_text())
            for event in source["events"]:
                content = event.get("content")
                if isinstance(content, str) and content:
                    self.assertNotIn(content, serialized)
                for field in (
                    "subject_id",
                    "scope",
                    "authorized_principals",
                    "authorization_epoch",
                    "classification",
                ):
                    value = event.get(field)
                    if isinstance(value, str) and len(value) >= 8:
                        self.assertNotIn(value, serialized)
        span_keys = {
            attribute["key"]
            for span in self.manifest["spans"]
            for attribute in span["attributes"]
        }
        self.assertNotIn("content", span_keys)
        self.assertNotIn("subject_id", span_keys)
        self.assertNotIn("authorization_epoch", span_keys)
        self.assertIn("frankengate.projection.receipt_id", span_keys)
        self.assertIn(
            "frankengate.projection.source_event_count", span_keys
        )

    def test_analyzer_accepts_exact_otlp_storage_round_trip(self):
        result = analyze_roundtrip(
            collector_batch(self.manifest), self.oracle
        )
        self.assertTrue(result["all_main_invariants_passed"])
        self.assertEqual(12, result["trace_ids_retained"])
        self.assertEqual(48, result["span_ids_retained"])
        self.assertEqual(34, result["parent_edges_retained"])
        self.assertEqual(16, result["links_retained"])
        self.assertEqual(48, result["timestamps_retained_exactly"])
        self.assertEqual(8, result["tool_lifecycle_semantics_retained"])
        self.assertEqual(12, result["receipt_identities_retained"])
        self.assertEqual(0, result["authority_attribute_keys_found"])
        self.assertEqual(0, result["content_attribute_keys_found"])

    def test_analyzer_detects_collector_root_drop(self):
        batches = collector_batch(self.manifest)
        spans = batches[0]["resourceSpans"][0]["scopeSpans"][0]["spans"]
        batches[0]["resourceSpans"][0]["scopeSpans"][0]["spans"] = [
            span
            for span in spans
            if next(
                (
                    int(attribute["value"]["intValue"])
                    for attribute in span["attributes"]
                    if attribute["key"]
                    == "frankengate.canonical.sequence"
                ),
                -1,
            )
            != 0
        ]
        result = analyze_roundtrip(batches, self.oracle)
        self.assertFalse(result["all_main_invariants_passed"])
        self.assertEqual(12, result["missing_span_ids"])
        self.assertEqual(12, result["trace_event_count_mismatches"])
        self.assertEqual(0, result["reimport_receipt_silent_drop_count"])

    def test_identifier_normalization_accepts_otlp_hex_and_base64(self):
        raw = bytes.fromhex("00112233445566778899aabbccddeeff")
        self.assertEqual(raw.hex(), _normalize_id(raw.hex(), 16))
        self.assertEqual(
            raw.hex(),
            _normalize_id(base64.b64encode(raw).decode("ascii"), 16),
        )

    def test_runtime_and_configs_are_pinned(self):
        self.assertEqual("0.153.0", COLLECTOR_VERSION)
        self.assertEqual("1.43.0", OTEL_GO_VERSION)
        self.assertEqual(64, len(COLLECTOR_DARWIN_ARM64_ARCHIVE_SHA256))
        self.assertEqual(64, len(COLLECTOR_DARWIN_ARM64_BINARY_SHA256))
        normal = (
            ROOT
            / "configs"
            / "otel"
            / "collector-roundtrip-v0.153.0.yaml"
        ).read_text()
        dropped = (
            ROOT
            / "configs"
            / "otel"
            / "collector-drop-v0.153.0.yaml"
        ).read_text()
        self.assertIn("receivers: [otlp]", normal)
        self.assertIn("processors: [batch]", normal)
        self.assertIn("exporters: [file/roundtrip]", normal)
        self.assertIn("filter/drop_roots", dropped)
        self.assertIn(
            'attributes["frankengate.canonical.sequence"] == 0', dropped
        )
        go_mod = (ROOT / "otel-roundtrip-sdk" / "go.mod").read_text()
        self.assertIn(
            "go.opentelemetry.io/otel/exporters/otlp/otlptrace/"
            "otlptracehttp v1.43.0",
            go_mod,
        )

    def test_high_entropy_content_and_authority_values_do_not_enter_manifest(self):
        content_marker = "CONTENT-CANARY-7714A60B"
        authority_marker = "AUTHORITY-CANARY-60DC9912"
        source = {
            "schema_version": "canonical-trajectory-v1",
            "trace_id": "a" * 64,
            "source": {
                "dataset_id": "test",
                "dataset_revision": "v1",
                "adapter": "test",
            },
            "task": {"task_id": "privacy"},
            "events": [
                {
                    "event_id": "event-a",
                    "sequence": 0,
                    "kind": "authorization_decision",
                    "observation_status": "observed",
                    "source_role": "governance",
                    "content": content_marker,
                    "subject_id": authority_marker,
                    "scope": authority_marker,
                }
            ],
            "outcome": {"value": None, "source": "missing"},
        }
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)
            (path / "fixture.json").write_text(json.dumps(source))
            manifest, oracle = build_sdk_manifest(path)
        serialized = _stable_json(manifest)
        self.assertNotIn(content_marker, serialized)
        self.assertNotIn(authority_marker, serialized)
        self.assertEqual(1, oracle["source_content_field_count"])
        self.assertEqual(2, oracle["source_authority_field_count"])

    @unittest.skipUnless(
        os.environ.get("FRANKENGATE_OTELCOL_BIN")
        and os.environ.get("FRANKENGATE_OTEL_SENDER_BIN"),
        "set pinned Collector and SDK sender paths for live integration",
    )
    def test_live_sdk_collector_storage_reimport(self):
        result = run_experiment(
            fixtures_root=FIXTURES,
            collector=Path(os.environ["FRANKENGATE_OTELCOL_BIN"]),
            sender=Path(os.environ["FRANKENGATE_OTEL_SENDER_BIN"]),
            normal_config=(
                ROOT
                / "configs"
                / "otel"
                / "collector-roundtrip-v0.153.0.yaml"
            ),
            drop_config=(
                ROOT
                / "configs"
                / "otel"
                / "collector-drop-v0.153.0.yaml"
            ),
        )
        self.assertTrue(result["all_acceptance_checks_passed"])


if __name__ == "__main__":
    unittest.main()
