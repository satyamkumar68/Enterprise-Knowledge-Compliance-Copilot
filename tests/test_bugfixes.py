import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.generation.answer import generate_answer
from app.ingestion.loaders import load_document


class TestBugFixesAndEdgeCases(unittest.TestCase):

    def test_script_modules_resolve_project_root(self):
        """Ensure all CLI scripts import cleanly and set up sys.path for direct execution."""
        scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
        script_files = [
            "create_dev_user.py",
            "set_user_password.py",
            "run_answer_demo.py",
            "run_retriever_demo.py",
        ]
        for script_name in script_files:
            file_path = scripts_dir / script_name
            self.assertTrue(file_path.is_file(), f"{script_name} must exist")
            content = file_path.read_text(encoding="utf-8")
            self.assertIn("sys.path.insert(0", content, f"{script_name} must configure sys.path")

    @patch("app.generation.answer.retrieve_chunks")
    @patch("app.generation.answer.httpx.post")
    def test_answer_parsing_handles_markdown_code_fences(self, mock_post, mock_retrieve):
        """Model wrapping JSON in markdown fences ```json ... ``` must parse without error."""
        mock_retrieve.return_value = [
            {
                "document_id": 1,
                "chunk_index": 0,
                "content": "Employees must rotate passwords quarterly.",
                "metadata": {"source": "policy.md"},
                "distance": 0.15,
            }
        ]

        markdown_json = (
            "```json\n"
            "{\n"
            '  "answer": "Passwords must be rotated quarterly. [Source 1]",\n'
            '  "abstained": false,\n'
            '  "source_ids": [1]\n'
            "}\n"
            "```"
        )
        mock_post.return_value.json.return_value = {
            "message": {"content": markdown_json}
        }
        mock_post.return_value.raise_for_status.return_value = None

        result = generate_answer("How often to rotate?", "employee-001")
        self.assertFalse(result["abstained"])
        self.assertEqual(result["clean_answer"], "Passwords must be rotated quarterly.")
        self.assertIn("[Source 1]", result["answer"])

    @patch("app.generation.answer.retrieve_chunks")
    @patch("app.generation.answer.httpx.post")
    def test_answer_parsing_strips_thinking_tags(self, mock_post, mock_retrieve):
        """Reasoning models that prepend <think>...</think> must be stripped cleanly."""
        mock_retrieve.return_value = [
            {
                "document_id": 1,
                "chunk_index": 0,
                "content": "Approval is required.",
                "metadata": {"source": "policy.md"},
                "distance": 0.10,
            }
        ]

        content_with_think = (
            "<think>The question asks about approvals. Looking at chunk 1, it says approval is required.</think>\n"
            '{"answer": "Approval is required. [Source 1]", "abstained": false, "source_ids": [1]}'
        )
        mock_post.return_value.json.return_value = {
            "message": {"content": content_with_think}
        }
        mock_post.return_value.raise_for_status.return_value = None

        result = generate_answer("What is needed?", "employee-001")
        self.assertFalse(result["abstained"])
        self.assertEqual(result["clean_answer"], "Approval is required.")

    @patch("app.generation.answer.retrieve_chunks")
    @patch("app.generation.answer.httpx.post")
    def test_clean_answer_normalizes_multiple_citation_styles_and_orphan_periods(self, mock_post, mock_retrieve):
        """Clean answer should strip [Source 1, 2] and avoid orphan punctuation like 'word .'."""
        mock_retrieve.return_value = [
            {
                "document_id": 1,
                "chunk_index": 0,
                "content": "Access requires manager approval.",
                "metadata": {"source": "policy.md"},
                "distance": 0.10,
            }
        ]

        # LLM placed citation before period: "approval [Source 1]."
        mock_post.return_value.json.return_value = {
            "message": {
                "content": json.dumps({
                    "answer": "Access requires manager approval [Source 1].",
                    "abstained": False,
                    "source_ids": [1],
                })
            }
        }
        mock_post.return_value.raise_for_status.return_value = None

        result = generate_answer("What is needed?", "employee-001")
        self.assertEqual(result["clean_answer"], "Access requires manager approval.")

    def test_loader_utf8_fallback_on_corrupted_encoding(self):
        """Non-UTF8 bytes in text files should be replaced without raising UnicodeDecodeError."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_file = Path(temp_dir) / "corrupted_charset.txt"
            # Write invalid UTF-8 byte sequence (e.g., latin-1 character 0xE9 without utf-8 encoding)
            temp_file.write_bytes(b"Valid ASCII with high byte \xe9 here.")

            pages = load_document(str(temp_file))
            self.assertEqual(len(pages), 1)
            self.assertIn("Valid ASCII", pages[0]["text"])


if __name__ == "__main__":
    unittest.main()
