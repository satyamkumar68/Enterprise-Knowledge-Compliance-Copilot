
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.main import app
from app.core.auth import authenticate_user


client = TestClient(app)


class TestAPIAuthentication(unittest.TestCase):

    def setUp(self):
        self.question = {
            "question": (
                "What permission do I need to access "
                "the production database?"
            ),
            "top_k": 5,
        }

    def test_missing_token_returns_401(self):
        response = client.post(
            "/api/v1/ask",
            json=self.question,
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json()["detail"],
            "Authentication required.",
        )

    @patch("app.api.main.generate_answer")
    def test_invalid_token_returns_401(self, mock_generate):
        # Test the actual authentication function with a token
        # that the database does not recognize.
        with patch("app.core.auth.psycopg.connect") as mock_connect:
            mock_connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value.fetchone.return_value = None

            response = client.post(
                "/api/v1/ask",
                headers={"Authorization": "Bearer invalid-test-token"},
                json=self.question,
            )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json()["detail"],
            "Invalid authentication credentials.",
        )
        mock_generate.assert_not_called()

    @patch("app.api.main.generate_answer")
    def test_authorized_employee_can_ask(self, mock_generate):
        app.dependency_overrides[authenticate_user] = (
            lambda: "employee-001"
        )
        self.addCleanup(app.dependency_overrides.clear)

        mock_generate.return_value = {
            "answer": "Manager approval is required. [Source 1]",
            "abstained": False,
            "sources": [
                {
                    "source_id": 1,
                    "document_id": 4,
                    "chunk_index": 0,
                    "filename": "security_policy.md",
                    "content": (
                        "Employees must obtain approval from "
                        "their engineering manager."
                    ),
                    "distance": 0.19,
                }
            ],
        }

        response = client.post(
            "/api/v1/ask",
            headers={"Authorization": "Bearer test-token"},
            json=self.question,
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["abstained"])
        self.assertEqual(
            response.json()["sources"][0]["document_id"],
            4,
        )
        mock_generate.assert_called_once()

        self.assertEqual(
            mock_generate.call_args.kwargs["principal_id"],
            "employee-001",
        )

    @patch("app.api.main.generate_answer")
    def test_unauthorized_employee_gets_no_sources(
        self,
        mock_generate,
    ):
        app.dependency_overrides[authenticate_user] = (
            lambda: "employee-unauthorized"
        )
        self.addCleanup(app.dependency_overrides.clear)

        mock_generate.return_value = {
            "answer": (
                "The available documents do not contain enough "
                "information to answer this question."
            ),
            "abstained": True,
            "sources": [],
        }

        response = client.post(
            "/api/v1/ask",
            headers={"Authorization": "Bearer test-token"},
            json=self.question,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["abstained"])
        self.assertEqual(response.json()["sources"], [])

        self.assertEqual(
            mock_generate.call_args.kwargs["principal_id"],
            "employee-unauthorized",
        )


if __name__ == "__main__":
    unittest.main()

