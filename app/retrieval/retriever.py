
import logging
import threading
import time

from app.core.audit import log_audit_event
from app.core.config import RELEVANCE_THRESHOLD, RERANKER_ENABLED
from app.core.db_pool import get_connection
from app.ingestion.embeddings import create_embedding
from app.retrieval.query_rewriter import rewrite_query
from app.retrieval.reranker import rerank_chunks


logger = logging.getLogger(__name__)


RESTRICTED_SIMILARITY_THRESHOLD = 0.35


def _check_restricted_documents(
    vector_literal: str,
    principal_id: str,
) -> None:
    """Log an audit event if the query matches a restricted document.

    Runs in a background thread so it never delays the response.
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        dc.document_id,
                        dc.embedding <=> %s::vector AS distance
                    FROM document_chunks AS dc
                    JOIN documents AS d
                        ON d.id = dc.document_id
                    LEFT JOIN document_permissions AS dp
                        ON dp.document_id = d.id
                       AND dp.principal_id = %s
                    WHERE d.status = 'indexed'
                       AND (
                           dp.document_id IS NULL
                           OR dp.permission IS DISTINCT FROM 'read'
                       )
                    ORDER BY distance
                    LIMIT 1;
                    """,
                    (
                        vector_literal,
                        principal_id,
                    ),
                )

                restricted_match = cur.fetchone()

        if (
            restricted_match is not None
            and float(restricted_match[1])
            <= RESTRICTED_SIMILARITY_THRESHOLD
        ):
            log_audit_event(
                event_type="restricted_document_similarity",
                outcome="success",
                principal_id=principal_id,
                details={
                    "reason": "question_similar_to_unreadable_document",
                    "document_id": restricted_match[0],
                    "distance": float(restricted_match[1]),
                },
            )

    except Exception:
        # Non-critical monitoring — never disrupt retrieval.
        pass


def retrieve_chunks(
    question: str,
    principal_id: str,
    top_k: int = 5,
    max_distance: float | None = None,
    rewrite: bool | None = None,
    search_mode: str = "hybrid",
    rerank: bool | None = None,
) -> list[dict]:
    """Retrieve chunks using hybrid vector similarity and full-text RRF search, or single mode."""

    total_start = time.perf_counter()

    if not question or not question.strip():
        raise ValueError("Question cannot be empty.")

    if not principal_id or not principal_id.strip():
        raise ValueError("principal_id is required.")

    if not 1 <= top_k <= 20:
        raise ValueError("top_k must be between 1 and 20.")

    clean_question = question.strip()
    should_rerank = RERANKER_ENABLED if rerank is None else rerank
    fetch_limit = min(20, top_k * 3) if should_rerank else top_k

    # Stage 0: Query rewriting / expansion
    search_query = rewrite_query(clean_question, enabled=rewrite)

    # Stage 1: Embed the search query.
    stage_start = time.perf_counter()
    query_vector = create_embedding(search_query)

    logger.debug(
        "Retriever embedding: %.3fs",
        time.perf_counter() - stage_start,
    )

    vector_literal = "[" + ",".join(
        str(value) for value in query_vector
    ) + "]"

    # Stage 2: Retrieve authorized chunks using hybrid RRF search or single mode.
    connection_start = time.perf_counter()

    with get_connection() as conn:
        logger.debug(
            "Retrieval DB connection: %.3fs",
            time.perf_counter() - connection_start,
        )

        with conn.cursor() as cur:
            stage_start = time.perf_counter()

            if search_mode == "vector_only":
                vector_sql = """
                    SELECT
                        dc.document_id,
                        dc.chunk_index,
                        dc.content,
                        dc.metadata,
                        dc.embedding <=> %s::vector AS distance,
                        (1.0 - (dc.embedding <=> %s::vector)) AS score
                    FROM document_chunks AS dc
                    JOIN documents AS d ON d.id = dc.document_id
                    JOIN document_permissions AS dp ON dp.document_id = d.id
                    WHERE dp.principal_id = %s
                      AND dp.permission = 'read'
                      AND d.status = 'indexed'
                    ORDER BY distance ASC
                    LIMIT %s;
                """
                cur.execute(
                    vector_sql,
                    (vector_literal, vector_literal, principal_id, fetch_limit),
                )
                rows = cur.fetchall()

            elif search_mode == "keyword_only":
                keyword_sql = """
                    SELECT
                        dc.document_id,
                        dc.chunk_index,
                        dc.content,
                        dc.metadata,
                        dc.embedding <=> %s::vector AS distance,
                        ts_rank_cd(dc.tsv, plainto_tsquery('english', %s)) AS score
                    FROM document_chunks AS dc
                    JOIN documents AS d ON d.id = dc.document_id
                    JOIN document_permissions AS dp ON dp.document_id = d.id
                    WHERE dp.principal_id = %s
                      AND dp.permission = 'read'
                      AND d.status = 'indexed'
                      AND dc.tsv @@ plainto_tsquery('english', %s)
                    ORDER BY score DESC
                    LIMIT %s;
                """
                cur.execute(
                    keyword_sql,
                    (
                        vector_literal,
                        search_query,
                        principal_id,
                        search_query,
                        fetch_limit,
                    ),
                )
                rows = cur.fetchall()

            else:
                hybrid_sql = """
                    WITH vector_matches AS (
                        SELECT
                            dc.id AS chunk_id,
                            dc.document_id,
                            dc.chunk_index,
                            dc.content,
                            dc.metadata,
                            dc.embedding <=> %s::vector AS distance,
                            ROW_NUMBER() OVER (
                                ORDER BY dc.embedding <=> %s::vector
                            ) AS rank_vec
                        FROM document_chunks AS dc
                        JOIN documents AS d ON d.id = dc.document_id
                        JOIN document_permissions AS dp ON dp.document_id = d.id
                        WHERE dp.principal_id = %s
                          AND dp.permission = 'read'
                          AND d.status = 'indexed'
                        LIMIT %s * 3
                    ),
                    text_matches AS (
                        SELECT
                            dc.id AS chunk_id,
                            dc.document_id,
                            dc.chunk_index,
                            dc.content,
                            dc.metadata,
                            dc.embedding <=> %s::vector AS distance,
                            ROW_NUMBER() OVER (
                                ORDER BY ts_rank_cd(
                                    dc.tsv,
                                    plainto_tsquery('english', %s)
                                ) DESC
                            ) AS rank_text
                        FROM document_chunks AS dc
                        JOIN documents AS d ON d.id = dc.document_id
                        JOIN document_permissions AS dp ON dp.document_id = d.id
                        WHERE dp.principal_id = %s
                          AND dp.permission = 'read'
                          AND d.status = 'indexed'
                          AND dc.tsv @@ plainto_tsquery('english', %s)
                        LIMIT %s * 3
                    ),
                    combined AS (
                        SELECT
                            COALESCE(vm.chunk_id, tm.chunk_id) AS chunk_id,
                            COALESCE(vm.document_id, tm.document_id) AS document_id,
                            COALESCE(vm.chunk_index, tm.chunk_index) AS chunk_index,
                            COALESCE(vm.content, tm.content) AS content,
                            COALESCE(vm.metadata, tm.metadata) AS metadata,
                            COALESCE(vm.distance, tm.distance) AS distance,
                            (
                                COALESCE(1.0 / (60.0 + vm.rank_vec), 0.0) +
                                COALESCE(1.0 / (60.0 + tm.rank_text), 0.0)
                            ) AS rrf_score
                        FROM vector_matches vm
                        FULL OUTER JOIN text_matches tm ON tm.chunk_id = vm.chunk_id
                    )
                    SELECT
                        document_id,
                        chunk_index,
                        content,
                        metadata,
                        distance,
                        rrf_score
                    FROM combined
                    ORDER BY rrf_score DESC, distance ASC
                    LIMIT %s;
                """

                cur.execute(
                    hybrid_sql,
                    (
                        vector_literal,
                        vector_literal,
                        principal_id,
                        fetch_limit,
                        vector_literal,
                        search_query,
                        principal_id,
                        search_query,
                        fetch_limit,
                        fetch_limit,
                    ),
                )

                rows = cur.fetchall()

            logger.debug(
                "Authorized Retrieval (%s) SQL query + fetch: %.3fs (chunks=%d)",
                search_mode,
                time.perf_counter() - stage_start,
                len(rows),
            )

    # Check restricted documents in a background thread.
    threading.Thread(
        target=_check_restricted_documents,
        args=(vector_literal, principal_id),
        daemon=True,
    ).start()

    effective_max_distance = (
        max_distance if max_distance is not None else RELEVANCE_THRESHOLD
    )

    results = []
    for row in rows:
        dist = float(row[4])
        if effective_max_distance is not None and dist > effective_max_distance:
            continue
        item = {
            "document_id": row[0],
            "chunk_index": row[1],
            "content": row[2],
            "metadata": row[3],
            "distance": dist,
        }
        if len(row) > 5:
            item["score"] = float(row[5])
        results.append(item)

    # Stage 3: Second-stage reranker (if enabled, re-scores and trims to top_k)
    if should_rerank:
        results = rerank_chunks(clean_question, results, top_k=top_k, enabled=True)
    else:
        results = results[:top_k]

    logger.info(
        "Total retrieval: %.3fs (returned=%d)",
        time.perf_counter() - total_start,
        len(results),
    )

    return results
