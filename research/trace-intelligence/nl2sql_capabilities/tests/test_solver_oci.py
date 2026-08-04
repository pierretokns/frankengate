from __future__ import annotations

import copy
import pathlib
import sys
import unittest


TRACE_INTELLIGENCE_ROOT = pathlib.Path(__file__).parents[2]
sys.path.insert(0, str(TRACE_INTELLIGENCE_ROOT))

from nl2sql_capabilities.solver_oci import (  # noqa: E402
    BROKER_FD,
    LOCAL_TESTS_PROVE_LINUX_ENFORCEMENT,
    MODEL_FD,
    OCIProfileError,
    build_runc_argv,
    build_solver_oci_config,
    validate_solver_oci_config,
)


class SolverOCIContractTest(unittest.TestCase):
    def test_profile_requires_every_linux_isolation_control(self) -> None:
        config = build_solver_oci_config(
            command=("/opt/frankengate/solverd", "--one-episode")
        )
        validate_solver_oci_config(config)

        self.assertTrue(config["root"]["readonly"])
        process = config["process"]
        self.assertTrue(process["noNewPrivileges"])
        self.assertEqual("/work", process["cwd"])
        self.assertEqual(65532, process["user"]["uid"])
        self.assertNotIn(
            "RLIMIT_NPROC",
            {item["type"] for item in process["rlimits"]},
        )
        self.assertEqual(16, config["linux"]["resources"]["pids"]["limit"])
        for capability_set in (
            "bounding",
            "effective",
            "inheritable",
            "permitted",
            "ambient",
        ):
            self.assertEqual(
                [],
                process["capabilities"][capability_set],
                capability_set,
            )

        namespaces = {
            item["type"] for item in config["linux"]["namespaces"]
        }
        self.assertIn("network", namespaces)
        self.assertEqual(
            "SCMP_ACT_ERRNO",
            config["linux"]["seccomp"]["defaultAction"],
        )
        allowed_syscalls = {
            name
            for entry in config["linux"]["seccomp"]["syscalls"]
            if entry["action"] == "SCMP_ACT_ALLOW"
            for name in entry["names"]
        }
        self.assertNotIn("socket", allowed_syscalls)
        self.assertNotIn("connect", allowed_syscalls)
        self.assertNotIn("clone", allowed_syscalls)
        self.assertNotIn("execveat", allowed_syscalls)
        self.assertIn("fstatfs", allowed_syscalls)

        tmpfs = {
            mount["destination"]: mount
            for mount in config["mounts"]
            if mount["type"] == "tmpfs"
        }
        self.assertEqual({"/home", "/tmp", "/work"}, set(tmpfs))
        for mount in tmpfs.values():
            self.assertTrue(
                {
                    "nodev",
                    "nosuid",
                    "noexec",
                    "mode=0700",
                    "uid=65532",
                    "gid=65532",
                }.issubset(
                    set(mount["options"])
                )
            )
        self.assertEqual(
            str(BROKER_FD),
            config["annotations"]["frankengate.local/broker-fd"],
        )
        self.assertEqual(
            str(MODEL_FD),
            config["annotations"]["frankengate.local/model-fd"],
        )
        self.assertFalse(LOCAL_TESTS_PROVE_LINUX_ENFORCEMENT)
        self.assertEqual(
            "required-on-linux",
            config["annotations"][
                "frankengate.local/enforcement-verification"
            ],
        )

    def test_launcher_preserves_exactly_broker_and_model_fds(self) -> None:
        argv = build_runc_argv(
            bundle=pathlib.Path("/srv/fg/solver-bundle"),
            container_id="fg-solver-episode-0123",
        )
        self.assertEqual("runc", argv[0])
        self.assertEqual("2", argv[argv.index("--preserve-fds") + 1])
        self.assertEqual(
            "fg-solver-episode-0123",
            argv[-1],
        )

    def test_mutated_or_credential_bearing_profiles_fail_validation(self) -> None:
        baseline = build_solver_oci_config(command=("/opt/solverd",))
        mutations = []
        writable = copy.deepcopy(baseline)
        writable["root"]["readonly"] = False
        mutations.append(writable)
        network_missing = copy.deepcopy(baseline)
        network_missing["linux"]["namespaces"] = [
            item
            for item in network_missing["linux"]["namespaces"]
            if item["type"] != "network"
        ]
        mutations.append(network_missing)
        privileged = copy.deepcopy(baseline)
        privileged["process"]["capabilities"]["effective"] = ["CAP_NET_ADMIN"]
        mutations.append(privileged)
        no_seccomp = copy.deepcopy(baseline)
        no_seccomp["linux"].pop("seccomp")
        mutations.append(no_seccomp)
        secret_env = copy.deepcopy(baseline)
        secret_env["process"]["env"].append(
            "DATABASE_URL=postgres://secret"
        )
        mutations.append(secret_env)
        weak_syscall = copy.deepcopy(baseline)
        weak_syscall["linux"]["seccomp"]["syscalls"][0]["names"].append(
            "process_vm_readv"
        )
        mutations.append(weak_syscall)
        missing_rlimit = copy.deepcopy(baseline)
        missing_rlimit["process"]["rlimits"].pop()
        mutations.append(missing_rlimit)
        wrong_tmpfs_owner = copy.deepcopy(baseline)
        next(
            mount
            for mount in wrong_tmpfs_owner["mounts"]
            if mount["destination"] == "/work"
        )["options"].remove("uid=65532")
        mutations.append(wrong_tmpfs_owner)
        for mutation in mutations:
            with self.subTest():
                with self.assertRaises(OCIProfileError):
                    validate_solver_oci_config(mutation)


if __name__ == "__main__":
    unittest.main()
