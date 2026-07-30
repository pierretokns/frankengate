import json
import pathlib
import unittest


MANIFEST_DIR = pathlib.Path(__file__).parents[1] / "configs" / "datasets"


class DatasetManifestTest(unittest.TestCase):
    def test_manifests_pin_revision_license_and_raw_data_policy(self):
        manifests = sorted(MANIFEST_DIR.glob("*.json"))
        self.assertGreaterEqual(len(manifests), 2)
        for path in manifests:
            with self.subTest(path=path.name):
                manifest = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(
                    "trace-dataset-manifest-v1", manifest["schema_version"]
                )
                self.assertTrue(manifest["dataset_revision"])
                self.assertTrue(manifest["license"])
                policy = manifest.get("download_policy", {})
                raw_committed = policy.get(
                    "raw_data_committed",
                    manifest.get("pilot_sample", {}).get("raw_data_committed"),
                )
                self.assertFalse(raw_committed)


if __name__ == "__main__":
    unittest.main()
