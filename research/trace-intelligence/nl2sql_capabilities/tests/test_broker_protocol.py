from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import struct
import sys
import unittest


TRACE_INTELLIGENCE_ROOT = pathlib.Path(__file__).parents[2]
sys.path.insert(0, str(TRACE_INTELLIGENCE_ROOT))

from nl2sql_capabilities.broker_protocol import (  # noqa: E402
    MAX_FRAME_BYTES,
    BrokerProtocolError,
    ToolRequestDTO,
    ToolResponseDTO,
    decode_frame,
    encode_frame,
)
from nl2sql_capabilities.dto import encode_base64url  # noqa: E402


NONCE = encode_base64url(bytes(range(16)))
OTHER_NONCE = encode_base64url(bytes(range(1, 17)))
HANDLE = encode_base64url(bytes(range(32)))
ATTEMPT_ID = encode_base64url(bytes(range(24)))
SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64


def _request(operation: str) -> dict[str, object]:
    arguments: dict[str, object]
    if operation == "describe_schema":
        arguments = {}
    elif operation == "execute_sql":
        arguments = {"sql": "SELECT COUNT(*) AS n FROM public.accounts"}
    elif operation == "submit_sql":
        arguments = {"attempt_id": ATTEMPT_ID}
    elif operation == "abstain":
        arguments = {"reason_code": "insufficient_schema"}
    else:
        raise AssertionError(operation)
    return {
        "schema_version": "fg-tool-request-v1",
        "request_nonce": NONCE,
        "database_handle": HANDLE,
        "operation": operation,
        "arguments": arguments,
    }


def _remaining() -> dict[str, int]:
    return {"schema_calls": 1, "sql_attempts": 2, "model_turns": 4}


def _response(operation: str) -> dict[str, object]:
    if operation == "describe_schema":
        return {
            "schema_version": "fg-tool-response-v1",
            "request_nonce": NONCE,
            "status": "ok",
            "observation": {
                "tables": {
                    "public.accounts": ["account_id", "status"],
                },
                "catalog_sha256": SHA_A,
            },
            "authority_receipt_sha256": SHA_B,
            "remaining": _remaining(),
        }
    if operation == "execute_sql":
        return {
            "schema_version": "fg-tool-response-v1",
            "request_nonce": NONCE,
            "status": "ok",
            "attempt_id": ATTEMPT_ID,
            "observation": {
                "columns": ["n"],
                "rows": [[{"kind": "int", "value": "2"}]],
                "row_count": 1,
                "preview_truncated": False,
                "result_sha256": SHA_A,
            },
            "authority_receipt_sha256": SHA_B,
            "policy_receipt_sha256": SHA_C,
            "remaining": _remaining(),
        }
    if operation == "submit_sql":
        return {
            "schema_version": "fg-tool-response-v1",
            "request_nonce": NONCE,
            "status": "accepted",
            "terminal": True,
            "submission_receipt_sha256": SHA_A,
        }
    if operation == "abstain":
        return {
            "schema_version": "fg-tool-response-v1",
            "request_nonce": NONCE,
            "status": "accepted",
            "terminal": True,
            "abstention_receipt_sha256": SHA_A,
        }
    raise AssertionError(operation)


class BrokerProtocolTest(unittest.TestCase):
    def test_all_request_operations_are_closed_and_operation_specific(self) -> None:
        for operation in (
            "describe_schema",
            "execute_sql",
            "submit_sql",
            "abstain",
        ):
            with self.subTest(operation=operation):
                payload = _request(operation)
                parsed = ToolRequestDTO.from_dict(payload)
                self.assertEqual(payload, parsed.to_dict())
                self.assertEqual(payload, decode_frame(encode_frame(payload)))

        cross_operation_arguments = (
            ("describe_schema", {"sql": "SELECT 1"}),
            ("execute_sql", {}),
            ("execute_sql", {"attempt_id": ATTEMPT_ID}),
            ("submit_sql", {"sql": "SELECT 1"}),
            ("abstain", {}),
            ("abstain", {"reason_code": "invented"}),
        )
        for operation, arguments in cross_operation_arguments:
            with self.subTest(operation=operation, arguments=arguments):
                payload = _request(operation)
                payload["arguments"] = arguments
                with self.assertRaises(BrokerProtocolError):
                    ToolRequestDTO.from_dict(payload)

    def test_response_echoes_nonce_and_shape_is_bound_to_request(self) -> None:
        for operation in (
            "describe_schema",
            "execute_sql",
            "submit_sql",
            "abstain",
        ):
            with self.subTest(operation=operation):
                request = ToolRequestDTO.from_dict(_request(operation))
                payload = _response(operation)
                parsed = ToolResponseDTO.from_dict(payload, request=request)
                self.assertEqual(payload, parsed.to_dict())

                wrong_nonce = copy.deepcopy(payload)
                wrong_nonce["request_nonce"] = OTHER_NONCE
                with self.assertRaisesRegex(BrokerProtocolError, "nonce"):
                    ToolResponseDTO.from_dict(wrong_nonce, request=request)

                other_operation = (
                    "execute_sql"
                    if operation != "execute_sql"
                    else "describe_schema"
                )
                with self.assertRaises(BrokerProtocolError):
                    ToolResponseDTO.from_dict(
                        _response(other_operation),
                        request=request,
                    )

    def test_error_response_status_is_closed_and_content_free(self) -> None:
        request = ToolRequestDTO.from_dict(_request("execute_sql"))
        payload = {
            "schema_version": "fg-tool-response-v1",
            "request_nonce": NONCE,
            "status": "policy_denied",
            "code": "sensitive_column_reference",
            "message_sha256": SHA_A,
            "remaining": _remaining(),
        }
        self.assertEqual(
            payload,
            ToolResponseDTO.from_dict(payload, request=request).to_dict(),
        )
        for status in ("denied", "failure", "unknown"):
            with self.subTest(status=status):
                candidate = {**payload, "status": status}
                with self.assertRaises(BrokerProtocolError):
                    ToolResponseDTO.from_dict(candidate, request=request)
        leaked = {**payload, "message": "raw policy details"}
        with self.assertRaisesRegex(BrokerProtocolError, "unknown field"):
            ToolResponseDTO.from_dict(leaked, request=request)

    def test_frames_duplicate_members_floats_and_bounds_fail_closed(self) -> None:
        payload = _request("describe_schema")
        encoded = json.dumps(payload, separators=(",", ":"))
        duplicate = encoded.replace(
            '"request_nonce":',
            '"request_nonce":"shadow","request_nonce":',
            1,
        ).encode("utf-8")
        duplicate_frame = struct.pack(">I", len(duplicate)) + duplicate
        with self.assertRaisesRegex(BrokerProtocolError, "duplicate"):
            decode_frame(duplicate_frame)

        float_payload = b'{"value":1.5}'
        float_frame = struct.pack(">I", len(float_payload)) + float_payload
        with self.assertRaisesRegex(BrokerProtocolError, "float"):
            decode_frame(float_frame)

        for frame in (
            b"\x00\x00\x00",
            struct.pack(">I", 10) + b"{}",
            struct.pack(">I", 2) + b"{}trailing",
            struct.pack(">I", MAX_FRAME_BYTES + 1),
        ):
            with self.subTest(frame_length=len(frame)):
                with self.assertRaises(BrokerProtocolError):
                    decode_frame(frame)

        with self.assertRaisesRegex(BrokerProtocolError, "frame"):
            encode_frame({"oversize": "x" * MAX_FRAME_BYTES})

    def test_observations_and_remaining_budgets_are_bounded(self) -> None:
        request = ToolRequestDTO.from_dict(_request("execute_sql"))

        extra = copy.deepcopy(_response("execute_sql"))
        extra["observation"]["unknown"] = "leak"  # type: ignore[index]
        with self.assertRaisesRegex(BrokerProtocolError, "unknown field"):
            ToolResponseDTO.from_dict(extra, request=request)

        float_cell = copy.deepcopy(_response("execute_sql"))
        float_cell["observation"]["rows"][0][0]["value"] = 1.5  # type: ignore[index]
        with self.assertRaises(BrokerProtocolError):
            ToolResponseDTO.from_dict(float_cell, request=request)

        too_many_rows = copy.deepcopy(_response("execute_sql"))
        too_many_rows["observation"]["rows"] = [  # type: ignore[index]
            [{"kind": "int", "value": str(index)}]
            for index in range(10_001)
        ]
        too_many_rows["observation"]["row_count"] = 10_001  # type: ignore[index]
        with self.assertRaisesRegex(BrokerProtocolError, "rows"):
            ToolResponseDTO.from_dict(too_many_rows, request=request)

        negative_remaining = copy.deepcopy(_response("execute_sql"))
        negative_remaining["remaining"]["sql_attempts"] = -1  # type: ignore[index]
        with self.assertRaisesRegex(BrokerProtocolError, "sql_attempts"):
            ToolResponseDTO.from_dict(negative_remaining, request=request)

        inconsistent_count = copy.deepcopy(_response("execute_sql"))
        inconsistent_count["observation"]["row_count"] = 2  # type: ignore[index]
        with self.assertRaisesRegex(BrokerProtocolError, "row_count"):
            ToolResponseDTO.from_dict(inconsistent_count, request=request)


if __name__ == "__main__":
    unittest.main()
