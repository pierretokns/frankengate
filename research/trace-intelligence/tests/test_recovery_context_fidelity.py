import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))

from recovery_context_fidelity import run  # noqa: E402


def test_context_fidelity_records_structural_retention_without_content(tmp_path):
    runs = tmp_path / "runs"
    trajectory = runs / "t" / "agent" / "trajectory.json"
    trajectory.parent.mkdir(parents=True)
    trajectory.write_text(
        json.dumps(
            {
                "steps": [
                    {"source": "user", "message": "task"},
                    {
                        "source": "agent",
                        "message": "failed",
                        "tool_calls": [{"function_name": "bash", "arguments": {"keystrokes": "x"}}],
                        "observation": {"error": "failed"},
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"failures": [{"trajectory": "t/agent/trajectory.json"}]}),
        encoding="utf-8",
    )
    output = tmp_path / "result.json"
    result = run(manifest=manifest, runs_root=runs, output=output)
    assert result["aggregate"]["rows"] == 1
    assert result["aggregate"]["mean_fact_retention"] == 1.0
    assert result["summary_contract"]["command_text_preserved"] is False
