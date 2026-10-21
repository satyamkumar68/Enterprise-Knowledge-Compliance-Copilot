import unittest

from app.ingestion.chunking import chunk_text


class TestChunkingQuality(unittest.TestCase):

    def test_invalid_parameters_raise_value_error(self):
        with self.assertRaises(ValueError):
            chunk_text("Some text", chunk_size=0)

        with self.assertRaises(ValueError):
            chunk_text("Some text", chunk_size=100, overlap=100)

        with self.assertRaises(ValueError):
            chunk_text("Some text", chunk_size=100, overlap=-1)

    def test_empty_text_returns_empty_list(self):
        self.assertEqual(chunk_text(""), [])
        self.assertEqual(chunk_text("   "), [])

    def test_contextual_headers_prepended(self):
        text = (
            "# Access Rules\n\n"
            "Employees must request access from manager before touching production."
        )
        chunks = chunk_text(
            text,
            chunk_size=300,
            overlap=50,
            document_title="security_policy.md",
        )
        self.assertEqual(len(chunks), 1)
        self.assertIn("[Document: security_policy.md | Section: Access Rules]", chunks[0])
        self.assertIn("Employees must request access", chunks[0])

    def test_sliding_window_overlap_preserves_context(self):
        # Create text that exceeds chunk_size
        text = (
            "First sentence about database access rules. "
            "Second sentence about password requirements and length. "
            "Third sentence about rotating credentials quarterly. "
            "Fourth sentence about revoking contractor privileges."
        )
        chunks = chunk_text(text, chunk_size=120, overlap=40)
        self.assertGreater(len(chunks), 1)
        # Check that consecutive chunks have overlapping text
        overlap_found = False
        for i in range(len(chunks) - 1):
            chunk1_words = set(chunks[i].split())
            chunk2_words = set(chunks[i + 1].split())
            shared = chunk1_words.intersection(chunk2_words)
            if shared:
                overlap_found = True
                break
        self.assertTrue(overlap_found, "Consecutive chunks must share overlapping context")

    def test_section_headings_start_new_chunks(self):
        text = (
            "# Section A\n"
            "Rule one of section A.\n\n"
            "# Section B\n"
            "Rule one of section B."
        )
        chunks = chunk_text(text, chunk_size=300, overlap=50)
        self.assertEqual(len(chunks), 2)
        self.assertTrue(chunks[0].startswith("# Section A"))
        self.assertTrue(chunks[1].startswith("# Section B"))


if __name__ == "__main__":
    unittest.main()
