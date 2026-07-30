import csv
import hashlib
import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest


MODULE_PATH = pathlib.Path(__file__).parents[1] / "defog_sql_cohort.py"
SPEC = importlib.util.spec_from_file_location("defog_sql_cohort", MODULE_PATH)
cohort = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = cohort
SPEC.loader.exec_module(cohort)


def write_csv(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_fixture(root):
    general = []
    basic = []
    advanced = []
    for database in cohort.ENTERPRISE_DATABASES:
        general.append(
            {
                "question": f"{database} general",
                "query": "SELECT 1",
                "db_name": database,
                "query_category": "general",
                "instructions": "",
            }
        )
        basic.append(
            {
                "db_name": database,
                "query_category": "basic",
                "question": f"{database} basic",
                "query": "SELECT 2",
            }
        )
        for category, quota in cohort.ADVANCED_QUOTAS.items():
            for index in range(quota + 1):
                advanced.append(
                    {
                        "db_name": database,
                        "query_category": category,
                        "question": f"{database} {category} {index}",
                        "instructions": f"instruction {index}",
                        "query": f"SELECT {index}",
                        "full_instructions": f"full {index}",
                    }
                )
    write_csv(
        root / "data/questions_gen_postgres.csv",
        ["question", "query", "db_name", "query_category", "instructions"],
        general,
    )
    write_csv(
        root / "data/instruct_basic_postgres.csv",
        ["db_name", "query_category", "question", "query"],
        basic,
    )
    write_csv(
        root / "data/instruct_advanced_postgres.csv",
        [
            "db_name",
            "query_category",
            "question",
            "instructions",
            "query",
            "full_instructions",
        ],
        advanced,
    )


class DefogSQLCohortTest(unittest.TestCase):
    def test_selection_is_deterministic_and_content_free(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            build_fixture(root)
            first = cohort.build_manifest(root)
            second = cohort.build_manifest(root)
        self.assertEqual(first, second)
        self.assertEqual(44, len(first["tasks"]))
        serialized = cohort.canonical_bytes(first)
        self.assertNotIn(b"SELECT", serialized)
        self.assertNotIn(b"instruction ", serialized)
        self.assertEqual(
            sorted(task["task_id"] for task in first["tasks"]),
            [task["task_id"] for task in first["tasks"]],
        )

    def test_advanced_selection_uses_declared_quotas(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            build_fixture(root)
            manifest = cohort.build_manifest(root)
        advanced = [
            task
            for task in manifest["tasks"]
            if task["source_file"].endswith("instruct_advanced_postgres.csv")
        ]
        for database in cohort.ENTERPRISE_DATABASES:
            for category, expected in cohort.ADVANCED_QUOTAS.items():
                actual = sum(
                    task["db_name"] == database
                    and task["query_category"] == category
                    for task in advanced
                )
                self.assertEqual(expected, actual)

    def test_committed_manifest_matches_pinned_digest(self):
        manifest_path = (
            pathlib.Path(__file__).parents[1]
            / "experiments/manifests/defog-sql-eval-enterprise-96-2026-07-30.json"
        )
        payload = manifest_path.read_bytes()
        self.assertEqual(
            "454a3e4eb7b5e9ddc3c75068148028cdd9361cc745bf0859dc79e97e944b6767",
            hashlib.sha256(payload).hexdigest(),
        )
        manifest = json.loads(payload)
        self.assertEqual(96, len(manifest["tasks"]))
        self.assertNotIn("question", manifest["tasks"][0])
        self.assertNotIn("query", manifest["tasks"][0])
        self.assertNotIn("instructions", manifest["tasks"][0])

    def test_missing_category_fails_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary)
            build_fixture(root)
            path = root / "data/instruct_advanced_postgres.csv"
            with path.open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            rows = [
                row
                for row in rows
                if not (
                    row["db_name"] == "broker"
                    and row["query_category"] == "keywords_ratio"
                )
            ]
            write_csv(path, rows[0].keys(), rows)
            with self.assertRaises(cohort.CohortError):
                cohort.build_manifest(root)


if __name__ == "__main__":
    unittest.main()
