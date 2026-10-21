
import unittest
from unittest.mock import patch

from app.ingestion.pipeline import ingest_document


class TestDocumentIngestion(unittest.TestCase):

    def setUp(self):
        self.principal_id = "employee-001"

        # Mock the PostgreSQL connection.
        self.db_patcher = patch(
            "app.ingestion.pipeline.psycopg.connect"
        )
        self.mock_connect = self.db_patcher.start()

        # Mock document loading.
        self.loader_patcher = patch(
            "app.ingestion.pipeline.load_document",
            return_value=[
                {
                    "text": "Production database access policy.",
                    "metadata": {"page": 1},
                }
            ],
        )
        self.loader_patcher.start()

        # Mock text chunking.
        self.chunker_patcher = patch(
            "app.ingestion.pipeline.chunk_text",
            return_value=[
                "Production database access policy."
            ],
        )
        self.chunker_patcher.start()

        # Mock embedding generation.
        self.embedding_patcher = patch(
            "app.ingestion.pipeline.create_embedding",
            return_value=[0.1, 0.2, 0.3],
        )
        self.embedding_patcher.start()

        # Access the mocked cursor.
        connection = (
            self.mock_connect.return_value
            .__enter__.return_value
        )
        self.cursor = (
            connection.cursor.return_value
            .__enter__.return_value
        )

        # Simulate INSERT ... RETURNING id.
        self.cursor.fetchone.return_value = (42,)

    def tearDown(self):
        self.embedding_patcher.stop()
        self.chunker_patcher.stop()
        self.loader_patcher.stop()
        self.db_patcher.stop()

    def get_executed_sql(self):
        return [
            " ".join(call.args[0].split())
            for call in self.cursor.execute.call_args_list
        ]

    @patch(
        "app.ingestion.pipeline.Path.read_bytes",
        return_value=b"test",
    )
    def test_new_document_is_inserted_and_indexed(
        self, mock_read_bytes
    ):
        document_id = ingest_document(
            "policy.txt",
            principal_id=self.principal_id,
        )

        self.assertEqual(document_id, 42)

        sql_statements = self.get_executed_sql()

        insert_call = next(
            call
            for call in self.cursor.execute.call_args_list
            if "INSERT INTO documents" in call.args[0]
        )

        insert_sql = " ".join(insert_call.args[0].split())

        # Verify employee-specific document ownership.
        self.assertIn("owner_principal_id", insert_sql)
        self.assertIn(
            "ON CONFLICT (owner_principal_id, content_hash)",
            insert_sql,
        )

        insert_params = insert_call.args[1]

        self.assertEqual(insert_params[0], "policy.txt")
        self.assertEqual(
            insert_params[1],
            "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
        )
        self.assertEqual(
            insert_params[2],
            self.principal_id,
        )

        # Verify old chunks are replaced only for this document.
        self.assertTrue(
            any(
                "DELETE FROM document_chunks" in sql
                for sql in sql_statements
            )
        )

        # Verify chunks are inserted.
        self.assertTrue(
            any(
                "INSERT INTO document_chunks" in sql
                for sql in sql_statements
            )
        )

        # Verify document indexing completes.
        self.assertTrue(
            any(
                "UPDATE documents SET status = 'indexed'"
                in sql
                for sql in sql_statements
            )
        )

    @patch(
        "app.ingestion.pipeline.Path.read_bytes",
        return_value=b"identical file contents",
    )
    def test_duplicate_detection_is_scoped_to_owner(
        self, mock_read_bytes
    ):
        ingest_document(
            "policy.txt",
            principal_id=self.principal_id,
        )

        insert_call = next(
            call
            for call in self.cursor.execute.call_args_list
            if "INSERT INTO documents" in call.args[0]
        )

        insert_sql = " ".join(insert_call.args[0].split())

        self.assertIn(
            "ON CONFLICT (owner_principal_id, content_hash)",
            insert_sql,
        )

        self.assertNotIn(
            "ON CONFLICT (content_hash)",
            insert_sql,
        )

        self.assertEqual(
            insert_call.args[1][2],
            self.principal_id,
        )

    @patch(
        "app.ingestion.pipeline.Path.read_bytes",
        return_value=b"identical file contents",
    )
    def test_identical_content_is_scoped_to_each_employee(
        self, mock_read_bytes
    ):
        # Simulate two different document IDs returned by PostgreSQL.
        self.cursor.fetchone.side_effect = [
            (42,),
            (84,),
        ]

        first_document_id = ingest_document(
            "policy.txt",
            principal_id="employee-001",
        )

        second_document_id = ingest_document(
            "policy.txt",
            principal_id="employee-002",
        )

        self.assertEqual(first_document_id, 42)
        self.assertEqual(second_document_id, 84)
        self.assertNotEqual(
            first_document_id,
            second_document_id,
        )

        insert_calls = [
            call
            for call in self.cursor.execute.call_args_list
            if "INSERT INTO documents" in call.args[0]
        ]

        self.assertEqual(len(insert_calls), 2)

        first_sql = " ".join(insert_calls[0].args[0].split())
        second_sql = " ".join(insert_calls[1].args[0].split())

        for sql in (first_sql, second_sql):
            self.assertIn(
                "ON CONFLICT (owner_principal_id, content_hash)",
                sql,
            )

        # Each upload must use its authenticated employee ID.
        self.assertEqual(
            insert_calls[0].args[1][2],
            "employee-001",
        )
        self.assertEqual(
            insert_calls[1].args[1][2],
            "employee-002",
        )

        # Both uploads must have the same content hash.
        self.assertEqual(
            insert_calls[0].args[1][1],
            insert_calls[1].args[1][1],
        )

    @patch(
        "app.ingestion.pipeline.Path.read_bytes",
        return_value=b"test",
    )
    def test_database_work_uses_transaction_context(
        self, mock_read_bytes
    ):
        ingest_document(
            "policy.txt",
            principal_id=self.principal_id,
        )

        self.mock_connect.assert_called_once()
        self.mock_connect.return_value.__enter__.assert_called_once()

    @patch(
        "app.ingestion.pipeline.load_document",
        return_value=[],
    )
    def test_empty_document_is_rejected_before_database_write(
        self, mock_load
    ):
        with self.assertRaisesRegex(
            ValueError,
            "Document contains no extractable text.",
        ):
            ingest_document(
                "empty.txt",
                principal_id=self.principal_id,
            )

        self.mock_connect.assert_not_called()

    def test_missing_principal_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "authenticated employee ID is required",
        ):
            ingest_document(
                "policy.txt",
                principal_id="",
            )

        self.mock_connect.assert_not_called()

    @patch(
        "app.ingestion.pipeline.Path.read_bytes",
        return_value=b"test",
    )
    def test_chunk_insert_failure_propagates_error(
        self, mock_read_bytes
    ):
        def fail_on_chunk_insert(sql, params=None):
            if "INSERT INTO document_chunks" in sql:
                raise RuntimeError(
                    "Simulated chunk insertion failure"
                )

        self.cursor.execute.side_effect = fail_on_chunk_insert

        with self.assertRaisesRegex(
            RuntimeError,
            "Simulated chunk insertion failure",
        ):
            ingest_document(
                "policy.txt",
                principal_id=self.principal_id,
            )

        self.mock_connect.assert_called_once()
        self.mock_connect.return_value.__enter__.assert_called_once()


if __name__ == "__main__":
    unittest.main()
