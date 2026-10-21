import unittest
from unittest.mock import MagicMock, patch

from app.retrieval.query_rewriter import rewrite_query


class TestQueryRewriter(unittest.TestCase):

    def test_empty_or_whitespace_query_returns_empty(self):
        self.assertEqual(rewrite_query(""), "")
        self.assertEqual(rewrite_query("   "), "")

    def test_disabled_rewriting_returns_original(self):
        result = rewrite_query(
            "What is the policy for databases?",
            enabled=False,
        )
        self.assertEqual(result, "What is the policy for databases?")

    def test_successful_ollama_rewriting(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {
                "content": "production database access approval process and policy"
            }
        }

        with patch("app.retrieval.query_rewriter.httpx.post", return_value=mock_response):
            result = rewrite_query(
                "How do I get prod db access?",
                enabled=True,
            )
            self.assertEqual(
                result,
                "production database access approval process and policy",
            )

    def test_ollama_failure_falls_back_to_original_query(self):
        with patch(
            "app.retrieval.query_rewriter.httpx.post",
            side_effect=Exception("Network error or timeout"),
        ):
            result = rewrite_query(
                "What is the database policy?",
                enabled=True,
            )
            self.assertEqual(result, "What is the database policy?")

    def test_conversational_prefix_cleanup(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "message": {
                "content": '"production database credentials policy"'
            }
        }

        with patch("app.retrieval.query_rewriter.httpx.post", return_value=mock_response):
            result = rewrite_query("How to access db?", enabled=True)
            self.assertEqual(result, "production database credentials policy")


if __name__ == "__main__":
    unittest.main()
