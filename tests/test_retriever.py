
import unittest
from unittest.mock import patch

from app.retrieval.retriever import retrieve_chunks


class TestRetriever(unittest.TestCase):

    def setUp(self):
        # Mock database access, embeddings, query rewriting, and audit logging.
        self.connect_patcher = patch(
            "app.retrieval.retriever.get_connection"
        )
        self.mock_connect = self.connect_patcher.start()

        self.embedding_patcher = patch(
            "app.retrieval.retriever.create_embedding",
            return_value=[0.1, 0.2, 0.3],
        )
        self.embedding_patcher.start()

        self.rewriter_patcher = patch(
            "app.retrieval.retriever.rewrite_query",
            side_effect=lambda q, **kwargs: q,
        )
        self.mock_rewriter = self.rewriter_patcher.start()

        self.audit_patcher = patch(
            "app.retrieval.retriever.log_audit_event"
        )
        self.mock_audit = self.audit_patcher.start()

        connection = self.mock_connect.return_value.__enter__.return_value
        self.cursor = (
            connection.cursor.return_value.__enter__.return_value
        )

        self.cursor.fetchall.return_value = []
        self.cursor.fetchone.return_value = None

    def tearDown(self):
        self.audit_patcher.stop()
        self.rewriter_patcher.stop()
        self.embedding_patcher.stop()
        self.connect_patcher.stop()

    def test_authorized_user_receives_permitted_chunks(self):
        self.cursor.fetchall.return_value = [
            (4, 0, "Production database access policy", {}, 0.12)
        ]

        chunks = retrieve_chunks(
            question="How do I access the production database?",
            principal_id="employee-001",
        )

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["document_id"], 4)
        self.assertEqual(
            chunks[0]["content"],
            "Production database access policy",
        )
        self.mock_audit.assert_not_called()

    def test_relevance_threshold_filters_distant_chunks(self):
        self.cursor.fetchall.return_value = [
            (4, 0, "Close relevant policy chunk", {}, 0.20),
            (4, 1, "Distant irrelevant chunk", {}, 0.85),
        ]

        chunks = retrieve_chunks(
            question="How do I access the production database?",
            principal_id="employee-001",
            max_distance=0.65,
        )

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["content"], "Close relevant policy chunk")
        self.assertEqual(chunks[0]["distance"], 0.20)

    def test_unauthorized_user_receives_no_protected_chunks(self):
        # No permitted chunks are available to this user.
        self.cursor.fetchall.return_value = []

        # A restricted document is semantically similar.
        self.cursor.fetchone.return_value = (4, 0.19)

        chunks = retrieve_chunks(
            question="How do I access the production database?",
            principal_id="employee-unauthorized",
        )

        self.assertEqual(chunks, [])

    def test_close_restricted_match_creates_monitoring_event(self):
        self.cursor.fetchone.return_value = (4, 0.19)

        retrieve_chunks(
            question="How do I access the production database?",
            principal_id="employee-unauthorized",
        )

        self.mock_audit.assert_called_once_with(
            event_type="restricted_document_similarity",
            outcome="success",
            principal_id="employee-unauthorized",
            details={
                "reason": "question_similar_to_unreadable_document",
                "document_id": 4,
                "distance": 0.19,
            },
        )

    def test_distant_restricted_match_creates_no_event(self):
        self.cursor.fetchone.return_value = (4, 0.80)

        chunks = retrieve_chunks(
            question="What is today's cafeteria menu?",
            principal_id="employee-unauthorized",
        )

        self.assertEqual(chunks, [])
        self.mock_audit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
