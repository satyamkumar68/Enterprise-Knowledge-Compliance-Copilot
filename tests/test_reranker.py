import unittest
from unittest.mock import patch, MagicMock

from app.retrieval.reranker import rerank_chunks, _score_with_heuristic, _score_with_ollama
from app.retrieval.retriever import retrieve_chunks


class TestReranker(unittest.TestCase):
    def setUp(self):
        self.chunks = [
            {
                "document_id": 1,
                "chunk_index": 0,
                "content": "General corporate overview and cafeteria hours.",
                "distance": 0.40,
            },
            {
                "document_id": 2,
                "chunk_index": 0,
                "content": "Production database access policy requires manager approval.",
                "distance": 0.20,
            },
            {
                "document_id": 3,
                "chunk_index": 0,
                "content": "Employee benefits, health insurance, and PTO guidelines.",
                "distance": 0.45,
            },
        ]

    def test_reranker_disabled_by_default_returns_original_slice(self):
        result = rerank_chunks(
            query="production database access",
            chunks=self.chunks,
            top_k=2,
            enabled=False,
        )
        self.assertEqual(len(result), 2)
        # Without reranking, first two items in original order
        self.assertEqual(result[0]["document_id"], 1)
        self.assertEqual(result[1]["document_id"], 2)

    def test_reranker_heuristic_promotes_relevant_chunk(self):
        result = rerank_chunks(
            query="production database access",
            chunks=self.chunks,
            top_k=2,
            enabled=True,
        )
        self.assertEqual(len(result), 2)
        # Production database chunk matches exact query tokens, should rank first
        self.assertEqual(result[0]["document_id"], 2)
        self.assertIn("rerank_score", result[0])
        self.assertGreater(result[0]["rerank_score"], result[1]["rerank_score"])

    @patch("app.retrieval.reranker.post_ollama")
    def test_reranker_ollama_scoring_success(self, mock_post):
        mock_post.return_value.json.return_value = {
            "response": '{"scores": [2, 9, 1]}'
        }

        with patch("app.retrieval.reranker.RERANKER_TYPE", "ollama"):
            result = rerank_chunks(
                query="How to access database?",
                chunks=self.chunks,
                top_k=2,
                enabled=True,
            )

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["document_id"], 2)
        self.assertEqual(result[0]["rerank_score"], 9.0)
        self.assertEqual(result[1]["document_id"], 1)
        self.assertEqual(result[1]["rerank_score"], 2.0)

    @patch("app.retrieval.reranker.post_ollama")
    def test_reranker_ollama_fallback_on_exception(self, mock_post):
        mock_post.side_effect = RuntimeError("Ollama connection timeout")

        with patch("app.retrieval.reranker.RERANKER_TYPE", "ollama"):
            result = rerank_chunks(
                query="How to access database?",
                chunks=self.chunks,
                top_k=3,
                enabled=True,
            )

        # Fallback preserves chunks and gracefully returns without throwing
        self.assertEqual(len(result), 3)

    def test_reranker_empty_chunks_returns_empty_list(self):
        result = rerank_chunks(query="test", chunks=[], top_k=5, enabled=True)
        self.assertEqual(result, [])
