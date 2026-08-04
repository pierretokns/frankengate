import unittest

import finance_mteb_ollama_embedding_benchmark as study


class FinanceMTEBOllamaBenchmarkTests(unittest.TestCase):
    def test_loopback_endpoint_is_required(self):
        with self.assertRaises(ValueError):
            study.embed(
                endpoint="https://example.invalid",
                model="nomic-embed-text:latest",
                texts=["x"],
                prefix="search_query: ",
            )

    def test_defaults_use_local_harness(self):
        self.assertEqual(study.DEFAULT_ENDPOINT, "http://127.0.0.1:11434")
        self.assertEqual(study.DEFAULT_MODEL, "nomic-embed-text:latest")


if __name__ == "__main__":
    unittest.main()
