from dataclaw_zhiyaowang_audit import inspect_row


def test_inspect_row_counts_outputs_errors_and_repeated_shapes_without_content():
    result = inspect_row(
        {
            "session_id": "s",
            "project": "p",
            "source": "codex",
            "model": "frontier",
            "git_branch": "main",
            "messages": [
                {"role": "user", "content": "question", "timestamp": "t"},
                {
                    "role": "assistant",
                    "tool_uses": [
                        {"tool": "bash", "input": {"command": "x"}, "status": "success", "output": {"text": "ok"}},
                        {"tool": "bash", "input": {"command": "y"}, "status": "error", "output": {"text": "bad", "raw": {"stderr": "err"}}},
                    ],
                },
            ],
        }
    )
    assert result["message_count"] == 2
    assert result["user_text_count"] == 1
    assert result["tool_use_count"] == 2
    assert result["tool_family_counts"]["shell"] == 2
    assert result["error_tool_count"] == 1
    assert result["output_text_count"] == 2
    assert result["output_raw_count"] == 1
    assert result["has_branch"] is True
    assert result["session_id_digest"] != "s"
