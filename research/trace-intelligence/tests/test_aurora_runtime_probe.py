import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
import aurora_runtime_probe as probe  # noqa: E402


class AuroraRuntimeProbeTests(unittest.TestCase):
    def test_probe_never_claims_managed_aurora(self):
        result = probe.probe()
        self.assertFalse(result["aurora_like_database_reachable"])
        self.assertFalse(result["claim_boundary"]["managed_aurora_behavior_proven"])


if __name__ == "__main__":
    unittest.main()
