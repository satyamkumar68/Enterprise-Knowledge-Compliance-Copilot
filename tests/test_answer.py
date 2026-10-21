
import unittest
from unittest.mock import patch

from app.generation.answer import (
    ABSTENTION_MESSAGE,
    generate_answer,
)


class TestAnswerGeneration(unittest.TestCase):

    def setUp(self):
        self.chunks = [
            {
                "document_id": 4,
                "chunk_index": 0,
                "content": (
                    "Employees must obtain approval from their "
                    "engineering manager before accessing "
                    "production databases."
                ),
                "metadata": {"source": "security_policy.md"},
                "distance": 0.19,
            },
            {
                "document_id": 4,
                "chunk_index": 1,
                "content": (
                    "Production database credentials must never "
                    "be shared through public channels."
                ),
                "metadata": {"source": "security_policy.md"},
                "distance": 0.25,
            },
        ]

    @patch("app.generation.answer.retrieve_chunks")
    @patch("app.generation.answer.httpx.post")
    def test_answerable_question(self, mock_post, mock_retrieve):
        mock_retrieve.return_value = [self.chunks[0]]

        mock_post.return_value.json.return_value = {
            "message": {
                "content": (
                    '{"answer":"Manager approval is required.",'
                    '"abstained":false,"source_ids":[1]}'
                )
            }
        }
        mock_post.return_value.raise_for_status.return_value = None

        result = generate_answer(
            question="What approval is required?",
            principal_id="employee-001",
        )

        self.assertFalse(result["abstained"])
        self.assertIn("Manager approval", result["answer"])
        self.assertIn("[Source 1]", result["answer"])
        self.assertEqual(len(result["sources"]), 1)
        self.assertEqual(result["sources"][0]["document_id"], 4)
        self.assertEqual(result["sources"][0]["chunk_index"], 0)

        mock_retrieve.assert_called_once_with(
            question="What approval is required?",
            principal_id="employee-001",
            top_k=5,
        )

    @patch("app.generation.answer.retrieve_chunks")
    def test_no_retrieved_chunks(self, mock_retrieve):
        mock_retrieve.return_value = []

        result = generate_answer(
            question="What is the policy?",
            principal_id="employee-001",
        )

        self.assertTrue(result["abstained"])
        self.assertEqual(result["sources"], [])
        self.assertEqual(result["answer"], ABSTENTION_MESSAGE)

    @patch("app.generation.answer.retrieve_chunks")
    @patch("app.generation.answer.httpx.post")
    def test_unanswerable_question(self, mock_post, mock_retrieve):
        mock_retrieve.return_value = [self.chunks[1]]

        mock_post.return_value.json.return_value = {
            "message": {
                "content": (
                    '{"answer":"No rotation policy found.",'
                    '"abstained":true,"source_ids":[]}'
                )
            }
        }
        mock_post.return_value.raise_for_status.return_value = None

        result = generate_answer(
            question="How often must passwords be rotated?",
            principal_id="employee-001",
        )

        self.assertTrue(result["abstained"])
        self.assertEqual(result["sources"], [])
        self.assertEqual(result["answer"], ABSTENTION_MESSAGE)

    def test_missing_principal_is_rejected(self):
        with self.assertRaises(ValueError):
            generate_answer(
                question="What is the policy?",
                principal_id="",
            )

    @patch("app.generation.answer.retrieve_chunks")
    @patch("app.generation.answer.httpx.post")
    def test_unknown_source_ids_are_not_returned(
        self, mock_post, mock_retrieve
    ):
        mock_retrieve.return_value = [self.chunks[0]]

        mock_post.return_value.json.return_value = {
            "message": {
                "content": (
                    '{"answer":"Manager approval is required.",'
                    '"abstained":false,"source_ids":[999]}'
                )
            }
        }
        mock_post.return_value.raise_for_status.return_value = None

        result = generate_answer(
            question="What approval is required?",
            principal_id="employee-001",
        )

        self.assertTrue(result["abstained"])
        self.assertEqual(result["sources"], [])
        self.assertEqual(result["answer"], ABSTENTION_MESSAGE)

    @patch("app.generation.answer.retrieve_chunks")
    @patch("app.generation.answer.httpx.post")
    def test_only_validated_citation_markers_are_returned(
        self, mock_post, mock_retrieve
    ):
        mock_retrieve.return_value = [self.chunks[0]]

        mock_post.return_value.json.return_value = {
            "message": {
                "content": (
                    '{"answer":"Manager approval is required. '
                    '[Source 999]",'
                    '"abstained":false,"source_ids":[1]}'
                )
            }
        }
        mock_post.return_value.raise_for_status.return_value = None

        result = generate_answer(
            question="What approval is required?",
            principal_id="employee-001",
        )

        self.assertFalse(result["abstained"])
        self.assertIn("[Source 1]", result["answer"])
        self.assertNotIn("[Source 999]", result["answer"])
        self.assertEqual(
            [source["source_id"] for source in result["sources"]],
            [1],
        )

    @patch("app.generation.answer.retrieve_chunks")
    @patch("app.generation.answer.httpx.post")
    def test_multiple_valid_sources_keep_correct_mapping(
        self, mock_post, mock_retrieve
    ):
        mock_retrieve.return_value = self.chunks

        mock_post.return_value.json.return_value = {
            "message": {
                "content": (
                    '{"answer":"Approval is required and credentials '
                    'must not be shared.",'
                    '"abstained":false,"source_ids":[2,1,2]}'
                )
            }
        }
        mock_post.return_value.raise_for_status.return_value = None

        result = generate_answer(
            question="Explain database access requirements.",
            principal_id="employee-001",
        )

        self.assertFalse(result["abstained"])
        self.assertEqual(
            [source["source_id"] for source in result["sources"]],
            [1, 2],
        )
        self.assertEqual(
            [source["chunk_index"] for source in result["sources"]],
            [0, 1],
        )
        self.assertIn("[Source 1]", result["answer"])
        self.assertIn("[Source 2]", result["answer"])
        self.assertNotIn("[Source 999]", result["answer"])


if __name__ == "__main__":
    unittest.main()
