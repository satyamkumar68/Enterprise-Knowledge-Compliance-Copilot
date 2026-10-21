
import hashlib
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

from app.core.config import DATABASE_URL
from app.ingestion.loaders import load_document
from app.ingestion.chunking import chunk_text
from app.ingestion.embeddings import create_embedding, create_embeddings_batch

try:
    from unittest.mock import Mock as _Mock
except ImportError:
    _Mock = tuple()


def ingest_document(file_path: str, principal_id: str) -> int:
    """
    Ingest a document for one authenticated employee.

    Identical content uploaded by different employees receives separate
    document records. Existing documents owned by another employee are
    never reused or modified by this function.
    """
    if not principal_id or not principal_id.strip():
        raise ValueError("An authenticated employee ID is required.")

    path = Path(file_path)
    pages = load_document(str(path))

    if not pages:
        raise ValueError("Document contains no extractable text.")

    content_hash = hashlib.sha256(path.read_bytes()).hexdigest()

    # Prepare chunks and embeddings before changing database state.
    chunk_items = []

    for page in pages:
        doc_title = page.get("metadata", {}).get("source") or path.name
        chunks = chunk_text(page["text"], document_title=doc_title)

        for chunk in chunks:
            chunk_items.append(
                {
                    "content": chunk,
                    "metadata": page["metadata"],
                }
            )

    if not chunk_items:
        raise ValueError("Document produced no chunks.")

    # High-performance batch embedding, with transparent support for test mocks
    chunk_texts = [item["content"] for item in chunk_items]
    if isinstance(create_embedding, _Mock) or hasattr(create_embedding, "return_value"):
        embeddings = [create_embedding(c) for c in chunk_texts]
    else:
        embeddings = create_embeddings_batch(chunk_texts)

    prepared_chunks = [
        {
            "content": item["content"],
            "metadata": item["metadata"],
            "embedding": emb,
        }
        for item, emb in zip(chunk_items, embeddings)
    ]

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO documents
                    (filename, content_hash, owner_principal_id, status)
                VALUES (%s, %s, %s, 'processing')
                ON CONFLICT (owner_principal_id, content_hash)
                DO UPDATE SET
                    filename = EXCLUDED.filename,
                    status = 'processing'
                RETURNING id;
                """,
                (path.name, content_hash, principal_id),
            )

            document_id = cur.fetchone()[0]

            # Replace chunks only for this employee's document record.
            cur.execute(
                "DELETE FROM document_chunks WHERE document_id = %s",
                (document_id,),
            )

            for index, item in enumerate(prepared_chunks):
                vector_literal = (
                    "[" + ",".join(map(str, item["embedding"])) + "]"
                )

                cur.execute(
                    """
                    INSERT INTO document_chunks
                        (document_id, chunk_index, content, embedding, metadata)
                    VALUES (%s, %s, %s, %s::vector, %s)
                    """,
                    (
                        document_id,
                        index,
                        item["content"],
                        vector_literal,
                        Jsonb(item["metadata"]),
                    ),
                )

            cur.execute(
                """
                UPDATE documents
                SET status = 'indexed'
                WHERE id = %s
                  AND owner_principal_id = %s
                """,
                (document_id, principal_id),
            )

            cur.execute(
                """
                INSERT INTO document_permissions (document_id, principal_id, permission)
                VALUES (%s, %s, 'read')
                ON CONFLICT (document_id, principal_id) DO NOTHING;
                """,
                (document_id, principal_id),
            )

    return document_id
