import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from postgres_benchmark import latency_summary, percentile


class PostgresBenchmarkTest(unittest.TestCase):
    def test_percentile_interpolates(self) -> None:
        self.assertEqual(percentile([1.0, 2.0, 3.0], 0.5), 2.0)
        self.assertAlmostEqual(percentile([1.0, 3.0], 0.25), 1.5)

    def test_latency_summary_records_every_iteration(self) -> None:
        calls = []

        def run() -> None:
            calls.append(True)

        summary = latency_summary(run, 4)
        self.assertEqual(summary["iterations"], 4)
        self.assertEqual(len(calls), 4)
        self.assertGreaterEqual(summary["max_ms"], 0.0)


if __name__ == "__main__":
    unittest.main()
