import importlib.util
import json
import pathlib
import platform
import sys
import tempfile
import unittest


MODULE_PATH = pathlib.Path(__file__).parents[1] / "governed_tool_sandbox.py"
SPEC = importlib.util.spec_from_file_location("governed_tool_sandbox", MODULE_PATH)
sandbox = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = sandbox
SPEC.loader.exec_module(sandbox)


@unittest.skipUnless(
    platform.system() == "Darwin" and pathlib.Path("/usr/bin/sandbox-exec").exists(),
    "Seatbelt conformance requires macOS sandbox-exec",
)
class GovernedToolSandboxTest(unittest.TestCase):
    def test_can_read_and_write_inside_task_root(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            (root / "input.txt").write_text("allowed\n", encoding="utf-8")
            shell = sandbox.SandboxedShell(
                sandbox.SandboxPolicy(working_dir=root, timeout_seconds=5)
            )
            result = shell.execute("cat input.txt && printf 'made\\n' > output.txt")
            self.assertEqual(0, result.exit_code)
            self.assertEqual("allowed\n", result.stdout)
            self.assertEqual("made\n", (root / "output.txt").read_text())
            self.assertFalse(result.sandbox_violation)

    def test_denies_reads_outside_declared_roots(self):
        with tempfile.TemporaryDirectory() as task, tempfile.TemporaryDirectory() as secret:
            task_root = pathlib.Path(task)
            secret_file = pathlib.Path(secret) / "secret.txt"
            secret_file.write_text("must-not-leak\n", encoding="utf-8")
            shell = sandbox.SandboxedShell(
                sandbox.SandboxPolicy(working_dir=task_root, timeout_seconds=5)
            )
            result = shell.execute(f"cat '{secret_file}'")
            self.assertNotEqual(0, result.exit_code)
            self.assertNotIn("must-not-leak", result.stdout)
            self.assertTrue(result.sandbox_violation)

    def test_denies_network_and_does_not_inherit_api_keys(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            shell = sandbox.SandboxedShell(
                sandbox.SandboxPolicy(working_dir=root, timeout_seconds=5)
            )
            env_result = shell.execute("env")
            self.assertNotIn("OPENAI_API_KEY", env_result.stdout)
            self.assertNotIn("ANTHROPIC_API_KEY", env_result.stdout)
            network_result = shell.execute(
                "python3 -c 'import socket; socket.socket().connect((\"127.0.0.1\", 9))'"
            )
            self.assertNotEqual(0, network_result.exit_code)
            self.assertTrue(network_result.sandbox_violation)

    def test_audit_preserves_full_tool_call_outside_aggregate_results(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            audit_path = root / "raw-tool-audit.jsonl"
            shell = sandbox.SandboxedShell(
                sandbox.SandboxPolicy(working_dir=root, timeout_seconds=5),
                audit_path=audit_path,
            )
            command = "printf 'trace-me\\n'"
            result = shell.execute(command)
            receipt = json.loads(audit_path.read_text(encoding="utf-8"))
            self.assertEqual(command, receipt["command"])
            self.assertEqual(result.command_sha256, receipt["command_sha256"])
            self.assertIn("trace-me", receipt["stdout"])


class GovernedToolSandboxPureTest(unittest.TestCase):
    def test_profile_is_deny_by_default_and_networkless(self):
        with tempfile.TemporaryDirectory() as temp:
            policy = sandbox.SandboxPolicy(working_dir=pathlib.Path(temp))
            profile = sandbox.build_macos_profile(policy)
            self.assertIn("(deny default)", profile)
            self.assertIn("(deny network*)", profile)
            self.assertIn("(allow file-write*", profile)
            self.assertIn(str(pathlib.Path(temp).resolve()), profile)

    def test_render_observation_surfaces_policy_harms(self):
        result = sandbox.ToolExecution(
            command="cat /secret",
            command_sha256="a" * 64,
            exit_code=1,
            timed_out=False,
            sandbox_violation=True,
            network_denied=False,
            elapsed_ms=1.0,
            stdout="",
            stderr="Operation not permitted",
            stdout_truncated=False,
            stderr_truncated=False,
        )
        rendered = sandbox.render_tool_observation(result)
        self.assertIn("[SANDBOX_VIOLATION]", rendered)
        self.assertIn("[Exit code: 1]", rendered)

    def test_dyld_sandbox_denial_is_classified_as_a_harm(self):
        stderr = "Reason: tried runtime dylib (file system sandbox blocked open())"
        self.assertTrue(sandbox.is_sandbox_violation(stderr))

    def test_network_denial_is_classified_as_a_harm(self):
        output = "Failed to establish a new connection: nodename nor servname provided"
        self.assertTrue(sandbox.is_network_denial(output))


if __name__ == "__main__":
    unittest.main()
