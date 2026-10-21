
import unittest
from unittest.mock import patch

import psycopg

from app.core.audit import log_audit_event


class TestAuditLogging(unittest.TestCase):

    @patch("app.core.audit.psycopg.connect")
    def test_successful_event_is_inserted(self, mock_connect):
        log_audit_event(
            event_type="authentication",
            outcome="success",
            principal_id="employee-001",
            details={"method": "bearer_token"},
        )

        connection = mock_connect.return_value.__enter__.return_value
        cursor = connection.cursor.return_value.__enter__.return_value

        cursor.execute.assert_called_once()

        sql, params = cursor.execute.call_args.args

        self.assertIn("INSERT INTO audit_logs", sql)
        self.assertEqual(params[0], "authentication")
        self.assertEqual(params[1], "employee-001")
        self.assertEqual(params[2], "success")
        self.assertEqual(params[3], '{"method": "bearer_token"}')

    @patch("app.core.audit.psycopg.connect")
    def test_database_error_does_not_escape(self, mock_connect):
        mock_connect.side_effect = psycopg.OperationalError(
            "Database unavailable"
        )

        # Audit logging failure must not interrupt the main request.
        log_audit_event(
            event_type="authentication",
            outcome="failure",
            details={"reason": "missing_bearer_token"},
        )

    @patch("app.core.audit.psycopg.connect")
    def test_invalid_outcome_is_rejected(self, mock_connect):
        with self.assertRaisesRegex(
            ValueError,
            "Invalid audit event outcome.",
        ):
            log_audit_event(
                event_type="authentication",
                outcome="unexpected",
            )

        mock_connect.assert_not_called()

    @patch("app.core.audit.psycopg.connect")
    def test_missing_details_use_empty_object(self, mock_connect):
        log_audit_event(
            event_type="authentication",
            outcome="failure",
        )

        connection = mock_connect.return_value.__enter__.return_value
        cursor = connection.cursor.return_value.__enter__.return_value
        params = cursor.execute.call_args.args[1]

        self.assertEqual(params[3], "{}")


if __name__ == "__main__":
    unittest.main()
