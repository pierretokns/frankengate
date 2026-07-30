import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest


MODULE_PATH = pathlib.Path(__file__).parents[1] / "hf_nl2sql_trace_audit.py"
SPEC = importlib.util.spec_from_file_location("hf_nl2sql_trace_audit", MODULE_PATH)
audit = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = audit
SPEC.loader.exec_module(audit)


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def span(trace_id, span_id, operation, attributes=None, error=False):
    values = [
        {
            "key": "gen_ai.operation.name",
            "value": {"stringValue": operation},
        }
    ]
    for key, value in (attributes or {}).items():
        values.append({"key": key, "value": {"stringValue": value}})
    return {
        "traceId": trace_id,
        "spanId": span_id,
        "parentSpanId": "",
        "name": operation,
        "startTimeUnixNano": 0 if span_id.endswith("a") else 2,
        "endTimeUnixNano": 1 if span_id.endswith("a") else 3,
        "status": {
            "code": "STATUS_CODE_ERROR" if error else "STATUS_CODE_OK"
        },
        "attributes": values,
    }


def make_corpus(root, dataset_id, dimension_key):
    train = [
        {
            "task_id": "train-0",
            "prompt": "private prompt",
            "data": {dimension_key: "family-a"},
        }
    ]
    test = [
        {
            "task_id": "test-0",
            "prompt": "private held-out prompt",
            "data": {dimension_key: "family-b"},
        }
    ]
    metadata = json.dumps(
        {
            "task_id": "train-0#run-1",
            "base_task_id": "train-0",
            "split": "train",
            "model": "model",
            "reward": 1.0,
            "final_answer": "private SQL",
        }
    )
    spans = [
        span(
            "trace",
            "spana",
            "chat",
            {
                "gen_ai.prompt": "private prompt",
                "gen_ai.tool.call.arguments": "private arguments",
                "wmh.trace.metadata": metadata,
            },
        ),
        span(
            "trace",
            "spanb",
            "execute_tool",
            {"gen_ai.tool.message": "private result"},
        ),
    ]
    write_jsonl(root / "train.jsonl", train)
    write_jsonl(root / "test.jsonl", test)
    write_jsonl(root / "traces.otel.jsonl", spans)
    manifest = {
        "schema_version": "trace-dataset-manifest-v1",
        "dataset_id": dataset_id,
        "dataset_revision": "revision",
        "license": "license",
        "source_adapter": "adapter",
        "task_dimension_key": dimension_key,
        "audit_files": {
            name: {
                "relative_path": f"{name}.jsonl",
                "sha256": audit.sha256_path(root / f"{name}.jsonl"),
            }
            for name in ("train", "test", "traces.otel")
        },
        "replay_classification": {
            "environment_reconstructable": True,
            "hf_snapshot_self_contained": False,
        },
        "claim_boundary": ["fixture"],
        "download_policy": {"raw_data_committed": False},
    }
    return manifest


class HuggingFaceNL2SQLTraceAuditTest(unittest.TestCase):
    def test_audit_keeps_only_aggregate_structure(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            manifest = make_corpus(root, "example/corpus", "db_name")
            result = audit.audit_corpus(
                name="example",
                root=root,
                manifest=manifest,
            )
        self.assertEqual(1, result["trace_inventory"]["distinct_traces"])
        self.assertEqual(1, result["trace_inventory"]["environment_transitions"])
        self.assertEqual(1, result["trace_inventory"]["captured_train_tasks"])
        self.assertEqual(0, result["trace_inventory"]["captured_test_tasks"])
        self.assertTrue(result["otel_loss_receipt"]["all_spans_are_roots"])
        self.assertFalse(
            result["otel_loss_receipt"]["real_wall_clock_timestamps_available"]
        )
        serialized = json.dumps(result)
        self.assertNotIn("private prompt", serialized)
        self.assertNotIn("private arguments", serialized)
        self.assertNotIn("private result", serialized)
        self.assertNotIn("private SQL", serialized)

    def test_hash_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            manifest = make_corpus(root, "example/corpus", "db_name")
            manifest["audit_files"]["train"]["sha256"] = "0" * 64
            with self.assertRaises(audit.AuditError):
                audit.audit_corpus(
                    name="example",
                    root=root,
                    manifest=manifest,
                )

    def test_malformed_metadata_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            manifest = make_corpus(root, "example/corpus", "db_name")
            spans = [
                span(
                    "trace",
                    "spana",
                    "chat",
                    {"wmh.trace.metadata": "{bad"},
                )
            ]
            write_jsonl(root / "traces.otel.jsonl", spans)
            manifest["audit_files"]["traces.otel"]["sha256"] = audit.sha256_path(
                root / "traces.otel.jsonl"
            )
            with self.assertRaises(audit.AuditError):
                audit.audit_corpus(
                    name="example",
                    root=root,
                    manifest=manifest,
                )


if __name__ == "__main__":
    unittest.main()
