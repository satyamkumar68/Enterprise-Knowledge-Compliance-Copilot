
import asyncio
import logging
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path

import httpx
import psycopg
from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.api.auth_routes import router as auth_router
from app.evaluation.routes import router as evaluation_router
from app.observability.routes import (
    record_observability_event,
    router as observability_router,
)
from app.core.auth import authenticate_user
from app.core.audit import log_audit_event
from app.core.config import (
    DATABASE_URL,
    OLLAMA_BASE_URL,
    EMBEDDING_MODEL,
    GENERATION_MODEL,
    FAST_GENERATION_MODEL,
    OLLAMA_KEEP_ALIVE,
    OLLAMA_MAX_LOADED_MODELS,
    DEFAULT_TOP_K,
)
from app.core.ollama_client import post_ollama
from app.generation.answer import generate_answer, stream_answer
from app.ingestion.loaders import SUPPORTED_EXTENSIONS
from app.ingestion.pipeline import ingest_document


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("copilot.api")

REQUEST_TIMEOUT_SECONDS = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "120.0"))
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB


from contextlib import asynccontextmanager


def check_ollama_health() -> dict:
    """Verify connectivity to Ollama and check availability and residency of configured models."""
    info = {
        "connected": False,
        "base_url": OLLAMA_BASE_URL,
        "embedding_model": EMBEDDING_MODEL,
        "generation_model": GENERATION_MODEL,
        "fast_generation_model": FAST_GENERATION_MODEL,
        "embedding_model_available": False,
        "generation_model_available": False,
        "fast_generation_model_available": False,
        "available_models": [],
        "loaded_models": [],
        "multi_model_ready": False,
        "keep_alive": OLLAMA_KEEP_ALIVE,
        "error": None,
    }
    try:
        with httpx.Client(timeout=2.0) as client:
            resp = client.get(f"{OLLAMA_BASE_URL.rstrip('/')}/api/tags")
            if resp.status_code == 200:
                info["connected"] = True
                models = resp.json().get("models", [])
                names = [m.get("name", "") for m in models]
                info["available_models"] = names

                def has_model(target: str, list_names: list[str]) -> bool:
                    target_base = target.split(":")[0]
                    return any(
                        n == target or n.split(":")[0] == target_base
                        for n in list_names
                    )

                info["embedding_model_available"] = has_model(
                    EMBEDDING_MODEL, names
                )
                info["generation_model_available"] = has_model(
                    GENERATION_MODEL, names
                )
                info["fast_generation_model_available"] = has_model(
                    FAST_GENERATION_MODEL, names
                )

            # Query loaded models currently residing in VRAM/RAM
            try:
                resp_ps = client.get(f"{OLLAMA_BASE_URL.rstrip('/')}/api/ps")
                if resp_ps.status_code == 200:
                    ps_models = resp_ps.json().get("models", [])
                    loaded_names = [m.get("name", "") for m in ps_models]
                    info["loaded_models"] = loaded_names
                    info["multi_model_ready"] = len(loaded_names) >= 2
            except Exception:
                pass
    except Exception as exc:
        info["error"] = str(exc)

    return info


def warmup_ollama_models():
    """Background warm-up to pre-load embedding and generation models into memory with keep_alive."""
    try:
        post_ollama(
            "/api/embed",
            {"model": EMBEDDING_MODEL, "input": "copilot warm up", "keep_alive": OLLAMA_KEEP_ALIVE},
            timeout=10.0,
        )
        post_ollama(
            "/api/chat",
            {
                "model": GENERATION_MODEL,
                "messages": [{"role": "user", "content": "ping"}],
                "stream": False,
                "keep_alive": OLLAMA_KEEP_ALIVE,
                "options": {"num_predict": 1},
            },
            timeout=15.0,
        )
        logger.info(
            "Ollama models pre-warmed and resident in memory (%s keep-alive).",
            OLLAMA_KEEP_ALIVE,
        )
    except Exception as exc:
        logger.debug("Ollama background warm-up skipped or failed: %s", exc)


def startup_dependency_checks():
    logger.info("Starting Enterprise Knowledge Copilot API v0.9.2...")
    ollama_info = check_ollama_health()
    if ollama_info["connected"]:
        logger.info(
            "Ollama service reachable at %s. Models: embedding='%s' (available=%s), generation='%s' (available=%s), fast='%s' (available=%s)",
            OLLAMA_BASE_URL,
            EMBEDDING_MODEL,
            ollama_info["embedding_model_available"],
            GENERATION_MODEL,
            ollama_info["generation_model_available"],
            FAST_GENERATION_MODEL,
            ollama_info["fast_generation_model_available"],
        )
        if ollama_info.get("loaded_models"):
            logger.info("Active Ollama models resident in memory: %s", ollama_info["loaded_models"])
        else:
            logger.info("Triggering non-blocking background model warm-up into RAM/VRAM...")
            import threading
            threading.Thread(target=warmup_ollama_models, daemon=True).start()

        if not ollama_info["embedding_model_available"]:
            logger.warning(
                "Configured EMBEDDING_MODEL '%s' not found in Ollama tags. Install with: ollama pull %s",
                EMBEDDING_MODEL,
                EMBEDDING_MODEL,
            )
        if not ollama_info["generation_model_available"]:
            logger.warning(
                "Configured GENERATION_MODEL '%s' not found in Ollama tags. Install with: ollama pull %s",
                GENERATION_MODEL,
                GENERATION_MODEL,
            )
    else:
        logger.warning(
            "Ollama service at %s is not reachable (%s). RAG operations requiring Ollama will use fallback/mock modes.",
            OLLAMA_BASE_URL,
            ollama_info["error"],
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    startup_dependency_checks()
    yield


app = FastAPI(
    title="Enterprise Knowledge & Compliance Copilot",
    description="Evidence-based answers from authorized documents.",
    version="0.9.2",
    lifespan=lifespan,
)

# Authentication and session endpoints.
app.include_router(auth_router)

# Evaluation dataset, execution, metrics, and run history.
app.include_router(evaluation_router)

# Operational events, latency metrics, and observability.
app.include_router(observability_router)

# Request timeout middleware: prevents hung LLM or DB requests from blocking connections.
@app.middleware("http")
async def request_timeout_middleware(request: Request, call_next):
    try:
        return await asyncio.wait_for(
            call_next(request),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.error(
            "Request timed out after %.1fs: %s %s",
            REQUEST_TIMEOUT_SECONDS,
            request.method,
            request.url.path,
        )
        return JSONResponse(
            status_code=504,
            content={"detail": "Request timed out. Please try again."},
        )

# Allow credentialed requests only from local frontend origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "X-CSRF-Token",
    ],
)


# =========================================================
# Request and response models
# =========================================================

class QuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=DEFAULT_TOP_K, ge=1, le=10)
    model_profile: str | None = Field(default=None, description="Optional profile: 'standard' or 'fast'")
    model: str | None = Field(default=None, description="Optional model name override")


class SourceResponse(BaseModel):
    source_id: int
    document_id: int
    chunk_index: int
    filename: str
    content: str
    distance: float
    citation_tag: str | None = None
    metadata: dict = Field(default_factory=dict)


class AnswerResponse(BaseModel):
    answer: str
    abstained: bool
    sources: list[SourceResponse]
    clean_answer: str | None = None
    confidence_score: float | None = None
    average_distance: float | None = None
    model: str | None = None


class DocumentResponse(BaseModel):
    document_id: int
    filename: str
    status: str
    created_at: datetime
    chunk_count: int


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int


class DocumentUploadResponse(BaseModel):
    document_id: int
    filename: str
    status: str
    message: str


class DocumentDeleteResponse(BaseModel):
    document_id: int
    filename: str
    access_removed: bool
    document_deleted: bool
    message: str


class AuditEventResponse(BaseModel):
    id: int
    event_type: str
    principal_id: str | None
    outcome: str
    details: dict
    created_at: datetime


class AuditEventListResponse(BaseModel):
    events: list[AuditEventResponse]
    total: int


# =========================================================
# Health check
# =========================================================

@app.get("/health")
def health():
    ollama_info = check_ollama_health()
    return {
        "status": "ok",
        "ollama": ollama_info,
    }


# =========================================================
# Ask the knowledge copilot
# =========================================================

@app.post("/api/v1/ask", response_model=AnswerResponse)
def ask_question(
    request: QuestionRequest,
    principal_id: str = Depends(authenticate_user),
):
    started_at = time.perf_counter()

    try:
        result = generate_answer(
            question=request.question,
            principal_id=principal_id,
            top_k=request.top_k,
            model_profile=request.model_profile,
            model=request.model,
        )

        duration_ms = round(
            (time.perf_counter() - started_at) * 1000,
            2,
        )

        record_observability_event(
            event_type="rag_answer",
            severity="INFO",
            principal_id=principal_id,
            duration_ms=duration_ms,
            status_code=200,
            details={
                "abstained": bool(result.get("abstained", False)),
                "source_count": len(result.get("sources", [])),
                "top_k": request.top_k,
                "confidence_score": result.get("confidence_score"),
                "model": result.get("model"),
                "model_profile": request.model_profile,
            },
        )

        return {
            "answer": result["answer"],
            "clean_answer": result.get("clean_answer", result["answer"]),
            "abstained": result["abstained"],
            "sources": result["sources"],
            "confidence_score": result.get("confidence_score"),
            "average_distance": result.get("average_distance"),
            "model": result.get("model"),
        }

    except ValueError as exc:
        record_observability_event(
            event_type="rag_validation_error",
            severity="WARNING",
            principal_id=principal_id,
            duration_ms=round(
                (time.perf_counter() - started_at) * 1000,
                2,
            ),
            status_code=422,
            details={"error_type": type(exc).__name__},
        )

        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    except httpx.HTTPError as exc:
        logger.error(
            "Question service dependency failed: %s (%s)",
            type(exc).__name__,
            exc,
        )

        record_observability_event(
            event_type="rag_dependency_error",
            severity="ERROR",
            principal_id=principal_id,
            duration_ms=round(
                (time.perf_counter() - started_at) * 1000,
                2,
            ),
            status_code=503,
            details={"error_type": type(exc).__name__},
        )

        raise HTTPException(
            status_code=503,
            detail="The question service is temporarily unavailable.",
        ) from exc

    except Exception as exc:
        logger.exception(
            "Unexpected question request failure: %s",
            exc,
        )

        record_observability_event(
            event_type="rag_unexpected_error",
            severity="ERROR",
            principal_id=principal_id,
            duration_ms=round(
                (time.perf_counter() - started_at) * 1000,
                2,
            ),
            status_code=500,
            details={"error_type": type(exc).__name__},
        )

        raise HTTPException(
            status_code=500,
            detail="Unable to process the question.",
        ) from exc


@app.post("/api/v1/ask/stream")
def ask_question_stream(
    request: QuestionRequest,
    principal_id: str = Depends(authenticate_user),
):
    """Stream evidence-based answer chunks and final metadata via Server-Sent Events (SSE)."""
    import json
    started_at = time.perf_counter()

    def event_stream():
        final_meta = None
        has_error = False
        try:
            for event in stream_answer(
                question=request.question,
                principal_id=principal_id,
                top_k=request.top_k,
                model_profile=request.model_profile,
                model=request.model,
            ):
                event_name = event.get("event", "message")
                if event_name == "done":
                    final_meta = event
                elif event_name == "error":
                    has_error = True

                payload = json.dumps(event)
                yield f"event: {event_name}\ndata: {payload}\n\n"

        except Exception as exc:
            logger.exception("Unexpected error in SSE ask stream: %s", exc)
            has_error = True
            err_data = json.dumps({"event": "error", "error": "Unable to complete answer stream."})
            yield f"event: error\ndata: {err_data}\n\n"

        finally:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            if final_meta is not None:
                record_observability_event(
                    event_type="rag_answer_stream",
                    severity="INFO",
                    principal_id=principal_id,
                    duration_ms=duration_ms,
                    status_code=200,
                    details={
                        "abstained": bool(final_meta.get("abstained", False)),
                        "source_count": len(final_meta.get("sources", [])),
                        "top_k": request.top_k,
                        "confidence_score": final_meta.get("confidence_score"),
                        "model": final_meta.get("model"),
                        "model_profile": request.model_profile,
                    },
                )
            elif has_error:
                record_observability_event(
                    event_type="rag_stream_error",
                    severity="ERROR",
                    principal_id=principal_id,
                    duration_ms=duration_ms,
                    status_code=500,
                    details={"error": "stream_terminated_with_error"},
                )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# =========================================================
# Upload and ingest documents
# =========================================================

@app.post(
    "/api/v1/documents/upload",
    response_model=DocumentUploadResponse,
    status_code=201,
)
def upload_document(
    file: UploadFile = File(...),
    principal_id: str = Depends(authenticate_user),
):
    """
    Upload and index a document for the authenticated employee.

    Duplicate detection is scoped to the document owner.
    The employee ID is never accepted from the request body.
    """
    original_name = (file.filename or "").replace("\\", "/")
    filename = Path(original_name).name

    if not filename or filename in {".", ".."}:
        raise HTTPException(
            status_code=400,
            detail="A valid filename is required.",
        )

    extension = Path(filename).suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Upload PDF, DOCX, TXT, or MD.",
        )

    try:
        content = file.file.read(MAX_UPLOAD_SIZE + 1)

        if not content:
            raise HTTPException(
                status_code=400,
                detail="The uploaded file is empty.",
            )

        if len(content) > MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=413,
                detail="File exceeds the 10 MB upload limit.",
            )

        with tempfile.TemporaryDirectory(
            prefix="knowledge-upload-"
        ) as temp_dir:
            temp_path = Path(temp_dir) / filename
            temp_path.write_bytes(content)

            try:
                document_id = ingest_document(
                    str(temp_path),
                    principal_id=principal_id,
                )

            except ValueError as exc:
                raise HTTPException(
                    status_code=422,
                    detail=str(exc),
                ) from exc

            except (httpx.HTTPError, psycopg.Error) as exc:
                logger.error(
                    "Document ingestion dependency failed: %s (%s)",
                    type(exc).__name__,
                    exc,
                )

                raise HTTPException(
                    status_code=503,
                    detail="Document ingestion is temporarily unavailable.",
                ) from exc

            # Verify ownership before confirming read access.
            try:
                with psycopg.connect(DATABASE_URL) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            SELECT filename, status
                            FROM documents
                            WHERE id = %s
                              AND owner_principal_id = %s
                            FOR UPDATE;
                            """,
                            (document_id, principal_id),
                        )

                        row = cur.fetchone()

                        if row is None:
                            raise HTTPException(
                                status_code=500,
                                detail=(
                                    "The ingested document could not be "
                                    "verified for the authenticated employee."
                                ),
                            )

                        cur.execute(
                            """
                            INSERT INTO document_permissions
                                (document_id, principal_id, permission)
                            VALUES (%s, %s, 'read')
                            ON CONFLICT (document_id, principal_id)
                            DO NOTHING;
                            """,
                            (document_id, principal_id),
                        )

            except HTTPException:
                raise

            except psycopg.Error as exc:
                logger.error(
                    "Document permission assignment failed: %s (%s)",
                    type(exc).__name__,
                    exc,
                )

                raise HTTPException(
                    status_code=503,
                    detail=(
                        "The document was processed, but access could not "
                        "be configured. Contact the administrator."
                    ),
                ) from exc

        return {
            "document_id": document_id,
            "filename": row[0],
            "status": row[1],
            "message": "Document uploaded and processed.",
        }

    finally:
        file.file.close()


# =========================================================
# List authorized documents
# =========================================================

@app.get(
    "/api/v1/documents",
    response_model=DocumentListResponse,
)
def list_documents(
    principal_id: str = Depends(authenticate_user),
):
    """Return only documents the authenticated principal can read."""

    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        d.id,
                        d.filename,
                        d.status,
                        d.created_at,
                        COUNT(dc.id) AS chunk_count
                    FROM documents AS d
                    JOIN document_permissions AS dp
                        ON dp.document_id = d.id
                    LEFT JOIN document_chunks AS dc
                        ON dc.document_id = d.id
                    WHERE dp.principal_id = %s
                      AND dp.permission = 'read'
                    GROUP BY
                        d.id,
                        d.filename,
                        d.status,
                        d.created_at
                    ORDER BY d.created_at DESC, d.id DESC;
                    """,
                    (principal_id,),
                )

                rows = cur.fetchall()

        documents = [
            {
                "document_id": row[0],
                "filename": row[1],
                "status": row[2],
                "created_at": row[3],
                "chunk_count": row[4],
            }
            for row in rows
        ]

        return {
            "documents": documents,
            "total": len(documents),
        }

    except psycopg.Error as exc:
        logger.error(
            "Document listing database failure: %s (%s)",
            type(exc).__name__,
            exc,
        )

        raise HTTPException(
            status_code=503,
            detail="The document service is temporarily unavailable.",
        ) from exc


# =========================================================
# Delete a document or remove the user's access
# =========================================================

@app.delete(
    "/api/v1/documents/{document_id}",
    response_model=DocumentDeleteResponse,
)
def delete_document(
    document_id: int,
    principal_id: str = Depends(authenticate_user),
):
    """
    Remove the current user's permission for a document.

    Delete the document and its chunks only if no permissions remain.
    """
    if document_id <= 0:
        raise HTTPException(
            status_code=422,
            detail="Document ID must be a positive integer.",
        )

    filename = None
    document_deleted = False

    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT d.filename
                    FROM documents AS d
                    JOIN document_permissions AS dp
                        ON dp.document_id = d.id
                    WHERE d.id = %s
                      AND dp.principal_id = %s
                      AND dp.permission = 'read'
                    FOR UPDATE OF d;
                    """,
                    (document_id, principal_id),
                )

                row = cur.fetchone()

                if row is None:
                    raise HTTPException(
                        status_code=404,
                        detail=(
                            "Document not found or you do not have "
                            "permission to remove it."
                        ),
                    )

                filename = row[0]

                cur.execute(
                    """
                    DELETE FROM document_permissions
                    WHERE document_id = %s
                      AND principal_id = %s;
                    """,
                    (document_id, principal_id),
                )

                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM document_permissions
                    WHERE document_id = %s;
                    """,
                    (document_id,),
                )

                remaining_permissions = cur.fetchone()[0]

                if remaining_permissions == 0:
                    cur.execute(
                        """
                        DELETE FROM document_chunks
                        WHERE document_id = %s;
                        """,
                        (document_id,),
                    )

                    cur.execute(
                        """
                        DELETE FROM documents
                        WHERE id = %s;
                        """,
                        (document_id,),
                    )

                    document_deleted = True

        try:
            log_audit_event(
                event_type="document_deleted",
                outcome="success",
                principal_id=principal_id,
                details={
                    "document_id": document_id,
                    "filename": filename,
                    "document_record_deleted": document_deleted,
                    "access_removed": True,
                },
            )

        except Exception as audit_error:
            logger.warning(
                "Document change succeeded, but its audit event failed: %s (%s)",
                type(audit_error).__name__,
                audit_error,
            )

        if document_deleted:
            message = (
                "Document and indexed chunks deleted because no other "
                "users had access."
            )
        else:
            message = (
                "Your access was removed. The document remains available "
                "to other authorized users."
            )

        return {
            "document_id": document_id,
            "filename": filename,
            "access_removed": True,
            "document_deleted": document_deleted,
            "message": message,
        }

    except HTTPException:
        raise

    except psycopg.Error as exc:
        logger.error(
            "Document deletion database failure: %s (%s)",
            type(exc).__name__,
            exc,
        )

        raise HTTPException(
            status_code=503,
            detail="The document service is temporarily unavailable.",
        ) from exc


# =========================================================
# Security and activity: audit events
# =========================================================

@app.get(
    "/api/v1/audit-events",
    response_model=AuditEventListResponse,
)
def list_audit_events(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    principal_id: str = Depends(authenticate_user),
):
    """Return audit events for the authenticated principal only."""

    try:
        with psycopg.connect(DATABASE_URL) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        id,
                        event_type,
                        principal_id,
                        outcome,
                        details,
                        created_at
                    FROM audit_logs
                    WHERE principal_id = %s
                    ORDER BY created_at DESC, id DESC
                    LIMIT %s OFFSET %s;
                    """,
                    (principal_id, limit, offset),
                )

                rows = cur.fetchall()

                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM audit_logs
                    WHERE principal_id = %s;
                    """,
                    (principal_id,),
                )

                total = cur.fetchone()[0]

        events = [
            {
                "id": row[0],
                "event_type": row[1],
                "principal_id": row[2],
                "outcome": row[3],
                "details": row[4] or {},
                "created_at": row[5],
            }
            for row in rows
        ]

        return {
            "events": events,
            "total": total,
        }

    except psycopg.Error as exc:
        logger.error(
            "Audit listing database failure: %s (%s)",
            type(exc).__name__,
            exc,
        )

        raise HTTPException(
            status_code=503,
            detail="The audit service is temporarily unavailable.",
        ) from exc
