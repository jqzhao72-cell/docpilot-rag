"""Dataset-validator unit tests: synthetic fixtures, no model or index access."""

import unittest

from evaluation.datasets.validate_paper_dataset import validate


class DatasetValidationTests(unittest.TestCase):
    def setUp(self):
        self.corpus = {"chunks": [{"global_chunk_index": 0, "source": "fixture.pdf", "page_start": 1, "page_end": 2, "text": "Synthetic unit-test evidence"}]}
        self.dataset = {
            "status": "candidate_pending_review",
            "corpus": {"chunk_count": 1, "sources": [{"source": "fixture.pdf", "chunk_count": 1}]},
            "queries": [{"id": f"q{i}", "query": f"Synthetic question {i}", "source": "fixture.pdf", "question_type": "fixture", "relevant_chunk_ids": ["paper-0"], "relevant_pages": [1, 2], "expected_answer_points": ["Evidence"], "review_status": "pending", "review_notes": "Test only"} for i in range(30)],
        }

    def test_valid(self):
        result = validate(self.dataset, self.corpus)
        self.assertEqual(result["query_count"], 30)
        self.assertFalse(result["formal_metrics_executed"])

    def test_unknown_chunk(self):
        self.dataset["queries"][0]["relevant_chunk_ids"] = ["paper-missing"]
        with self.assertRaisesRegex(ValueError, "unknown chunk"):
            validate(self.dataset, self.corpus)

    def test_wrong_source(self):
        self.dataset["queries"][0]["source"] = "other.pdf"
        with self.assertRaisesRegex(ValueError, "source mismatch"):
            validate(self.dataset, self.corpus)

    def test_missing_page(self):
        self.dataset["queries"][0]["relevant_pages"] = [1]
        with self.assertRaisesRegex(ValueError, "page mismatch"):
            validate(self.dataset, self.corpus)

    def test_duplicate_query_id(self):
        self.dataset["queries"][1]["id"] = "q0"
        with self.assertRaisesRegex(ValueError, "Duplicate query IDs"):
            validate(self.dataset, self.corpus)

    def test_duplicate_chunk(self):
        self.dataset["queries"][0]["relevant_chunk_ids"] *= 2
        with self.assertRaisesRegex(ValueError, "invalid chunk IDs"):
            validate(self.dataset, self.corpus)

    def test_empty_answer_points(self):
        self.dataset["queries"][0]["expected_answer_points"] = []
        with self.assertRaisesRegex(ValueError, "missing answer points"):
            validate(self.dataset, self.corpus)


if __name__ == "__main__":
    unittest.main()
