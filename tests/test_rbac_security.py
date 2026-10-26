import os
import unittest
from unittest.mock import MagicMock, patch

from app.retrieval.retriever import retrieve_chunks, _check_restricted_documents


class TestRBACSecurity(unittest.TestCase):
    """Rigorous security test suite proving retrieval-time RBAC enforcement,
    zero-leakage at maximum top_k, SQL parameterization against injection,
    and restricted document similarity probe auditing."""

    def setUp(self):
        self.connect_patcher = patch("app.retrieval.retriever.get_connection")
        self.mock_connect = self.connect_patcher.start()

        self.embedding_patcher = patch(
            "app.retrieval.retriever.create_embedding",
            return_value=[0.05] * 768,
        )
        self.embedding_patcher.start()

        self.rewriter_patcher = patch(
            "app.retrieval.retriever.rewrite_query",
            side_effect=lambda q, **kwargs: q,
        )
        self.rewriter_patcher.start()

        self.audit_patcher = patch("app.retrieval.retriever.log_audit_event")
        self.mock_audit = self.audit_patcher.start()

        self.restricted_check_patcher = patch("app.retrieval.retriever._check_restricted_documents")
        self.mock_restricted_check = self.restricted_check_patcher.start()

        self.connection = self.mock_connect.return_value.__enter__.return_value
        self.cursor = self.connection.cursor.return_value.__enter__.return_value
        self.cursor.fetchall.return_value = []
        self.cursor.fetchone.return_value = None

    def tearDown(self):
        self.restricted_check_patcher.stop()
        self.audit_patcher.stop()
        self.rewriter_patcher.stop()
        self.embedding_patcher.stop()
        self.connect_patcher.stop()

    def test_sql_query_enforces_rbac_filter_at_database_layer(self):
        """Verify that SQL query contains the mandatory RBAC filter in the WHERE clause,
        preventing post-processing data leakage."""
        retrieve_chunks(
            question="What are the executive salaries?",
            principal_id="unauthorized-employee",
            top_k=20,
            search_mode="hybrid",
        )

        executed_sql, params = self.cursor.execute.call_args[0]
        # Verify SQL joins document_permissions and checks principal_id at the database level
        self.assertIn("JOIN document_permissions AS dp ON dp.document_id = d.id", executed_sql)
        self.assertIn("dp.principal_id = %s", executed_sql)
        self.assertIn("dp.permission = 'read'", executed_sql)
        self.assertIn("unauthorized-employee", params)

    def test_zero_leakage_at_max_top_k_vector_mode(self):
        """Even with top_k=20, an unauthorized user retrieves 0 restricted chunks."""
        self.cursor.fetchall.return_value = []

        chunks = retrieve_chunks(
            question="What is executive compensation?",
            principal_id="standard-user",
            top_k=20,
            search_mode="vector_only",
        )

        executed_sql, params = self.cursor.execute.call_args[0]
        self.assertIn("dp.principal_id = %s", executed_sql)
        self.assertIn("standard-user", params)
        self.assertEqual(len(chunks), 0)

    def test_zero_leakage_at_max_top_k_keyword_mode(self):
        """Full-text keyword search also enforces document_permissions at the database level."""
        self.cursor.fetchall.return_value = []

        chunks = retrieve_chunks(
            question="CEO bonus multiplier tier",
            principal_id="intern-user",
            top_k=20,
            search_mode="keyword_only",
        )

        executed_sql, params = self.cursor.execute.call_args[0]
        self.assertIn("JOIN document_permissions AS dp ON dp.document_id = d.id", executed_sql)
        self.assertIn("dp.principal_id = %s", executed_sql)
        self.assertIn("intern-user", params)
        self.assertEqual(len(chunks), 0)

    def test_sql_injection_attempt_in_principal_id_is_parameterized(self):
        """Malicious SQL injection in principal_id cannot escape parameterization."""
        injection_payloads = [
            "' OR '1'='1",
            "admin'; DROP TABLE documents; --",
            "' UNION SELECT * FROM documents WHERE '1'='1",
            " executive-001' --",
        ]

        for payload in injection_payloads:
            with self.subTest(payload=payload):
                self.cursor.fetchall.return_value = []
                retrieve_chunks(
                    question="Show me all confidential documents",
                    principal_id=payload,
                    top_k=5,
                    search_mode="hybrid",
                )
                executed_sql, params = self.cursor.execute.call_args[0]
                # The payload must be in params tuple, NEVER string-interpolated into SQL
                self.assertNotIn(payload, executed_sql)
                self.assertIn(payload, params)

    def test_restricted_document_similarity_triggers_security_audit(self):
        """When an unauthorized user asks a question close to a restricted document,
        an audit event is logged with event_type 'restricted_document_similarity'."""
        self.cursor.fetchone.return_value = (99, 0.22)  # Distance 0.22 <= threshold 0.35

        _check_restricted_documents(
            vector_literal="[0.05, 0.05]",
            principal_id="curious-employee-42",
        )

        self.mock_audit.assert_called_once_with(
            event_type="restricted_document_similarity",
            outcome="success",
            principal_id="curious-employee-42",
            details={
                "reason": "question_similar_to_unreadable_document",
                "document_id": 99,
                "distance": 0.22,
            },
        )

    def test_authorized_user_retrieval_success(self):
        """When a user HAS read permission, chunks are returned properly."""
        self.cursor.fetchall.return_value = [
            (99, 0, "Confidential Executive Compensation Tier 1", {"source": "compensation.md"}, 0.15)
        ]

        chunks = retrieve_chunks(
            question="What is executive compensation?",
            principal_id="executive-001",
            top_k=5,
            search_mode="hybrid",
        )

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["document_id"], 99)
        self.assertIn("Confidential Executive", chunks[0]["content"])

    def test_invalid_principal_id_rejected(self):
        """Empty or whitespace-only principal_id must raise ValueError."""
        with self.assertRaises(ValueError):
            retrieve_chunks("test question", principal_id="")

        with self.assertRaises(ValueError):
            retrieve_chunks("test question", principal_id="   ")

    def test_top_k_boundary_enforcement(self):
        """top_k outside [1, 20] must be rejected."""
        with self.assertRaises(ValueError):
            retrieve_chunks("test question", principal_id="user1", top_k=0)

        with self.assertRaises(ValueError):
            retrieve_chunks("test question", principal_id="user1", top_k=21)


class TestLiveDBRBACIsolation(unittest.TestCase):
    """Live database integration test (runs when PostgreSQL is available)
    verifying 0.0% leakage between unauthorized and authorized roles."""

    def test_live_db_zero_leakage_and_authorized_access(self):
        db_url = os.environ.get(
            "DATABASE_URL",
            "postgresql://raguser:local_dev_password_change_me@127.0.0.1:5432/knowledge_copilot",
        )
        try:
            import psycopg
            conn = psycopg.connect(db_url, connect_timeout=3)
            conn.close()
        except Exception:
            self.skipTest("Live PostgreSQL database is not reachable.")

        # Test with real retriever against the eval corpus seeded in PostgreSQL
        unauth_chunks = retrieve_chunks(
            question="What is the CEO bonus multiplier for exceeding 120% target?",
            principal_id="unauthorized-employee-test",
            top_k=10,
            search_mode="hybrid",
        )
        # Verify 0.0% leakage of confidential executive compensation
        for chunk in unauth_chunks:
            meta = chunk.get("metadata") or {}
            source = meta.get("source", "")
            self.assertNotIn("executive", source.lower())
            self.assertNotIn("compensation", chunk.get("content", "").lower())

        # Test authorized access
        auth_chunks = retrieve_chunks(
            question="What is the CEO bonus multiplier for exceeding 120% target?",
            principal_id="executive-001",
            top_k=5,
            search_mode="hybrid",
        )
        self.assertGreater(len(auth_chunks), 0)
        self.assertTrue(any("executive" in str(c.get("metadata", "")).lower() or "compensation" in c.get("content", "").lower() for c in auth_chunks))
