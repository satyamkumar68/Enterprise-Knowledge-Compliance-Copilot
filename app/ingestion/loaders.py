
from pathlib import Path

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from pypdf import PdfReader


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".md", ".txt"}


def _extract_docx_text(path: Path) -> str:
    """Extract paragraphs and tables from a DOCX in document order."""
    document = Document(str(path))
    sections = []

    for element in document.element.body.iterchildren():
        if element.tag.endswith("}p"):
            paragraph = Paragraph(element, document)
            text = paragraph.text.strip()

            if text:
                sections.append(text)

        elif element.tag.endswith("}tbl"):
            table = Table(element, document)

            for row in table.rows:
                cells = [
                    cell.text.strip().replace("\n", " ")
                    for cell in row.cells
                ]

                if any(cells):
                    sections.append(" | ".join(cells))

    return "\n".join(sections)


def load_document(file_path: str) -> list[dict]:
    path = Path(file_path)

    if not path.is_file():
        raise FileNotFoundError(f"File not found: {path}")

    extension = path.suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {extension}")

    pages = []

    if extension == ".pdf":
        reader = PdfReader(str(path))

        if reader.is_encrypted:
            raise ValueError("Encrypted PDFs are not supported yet.")

        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""

            if text.strip():
                pages.append({
                    "text": text,
                    "metadata": {
                        "source": path.name,
                        "file_type": extension,
                        "page": page_number,
                    },
                })

    elif extension == ".docx":
        text = _extract_docx_text(path)

        if text.strip():
            pages.append({
                "text": text,
                "metadata": {
                    "source": path.name,
                    "file_type": extension,
                },
            })

    else:
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            text = path.read_text(encoding="utf-8", errors="replace")

        if text.strip():
            pages.append({
                "text": text,
                "metadata": {
                    "source": path.name,
                    "file_type": extension,
                },
            })

    return pages
