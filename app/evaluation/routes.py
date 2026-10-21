
import time
from datetime import datetime
from threading import Lock

import psycopg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from psycopg.types.json import Jsonb

from app.core.auth import authenticate_user
from app.core.config import DATABASE_URL
from app.generation.answer import generate_answer


router = APIRouter(
    prefix="/api/v1/evaluation",
    tags=["RAG Evaluation"],
)

# Prevent repeated initialization within the same process.
_evaluation_schema_lock = Lock()
_evaluation_schema_ready = False

# Fixed PostgreSQL advisory-lock key for evaluation schema initialization.
# All backend workers using this code share the same database lock.
_EVALUATION_SCHEMA_LOCK_KEY = 728194603


# =========================================================
# Request models
# =========================================================

class EvaluationCaseCreate(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    expected_answer: str = Field(default="", max_length=5000)
    expected_document_ids: list[int] = Field(
        default_factory=list,
        max_length=50,
    )


class EvaluationCaseResponse(BaseModel):
    id: int
    question: str
    expected_answer: str
    expected_document_ids: list[int]
    created_at: datetime


# =========================================================
# Evaluation database initialization
# =========================================================

def ensure_evaluation_tables() -> None:
    """
    Initialize only the evaluation tables.

    A PostgreSQL transaction-level advisory lock serializes schema
    initialization across concurrent requests and backend workers.
    Existing application tables and document data are untouched.
    """
    global _evaluation_schema_ready

    if _evaluation_schema_ready:
        return

    with _evaluation_schema_lock:
        if _evaluation_schema_ready:
            return

        with psycopg.connect(
            DATABASE_URL,
            connect_timeout=20,
        ) as conn:
            with conn.cursor() as cur:
                # Automatically released when this transaction ends.
                cur.execute(
                    "SELECT pg_advisory_xact_lock(%s)",
                    (_EVALUATION_SCHEMA_LOCK_KEY,),
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS evaluation_cases (
                        id BIGSERIAL PRIMARY KEY,
                        principal_id TEXT NOT NULL,
                        question TEXT NOT NULL,
                        expected_answer TEXT NOT NULL DEFAULT '',
                        expected_document_ids INTEGER[]
                            NOT NULL DEFAULT '{}',
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )

                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS
                        idx_evaluation_cases_principal_created
                    ON evaluation_cases (
                        principal_id,
                        created_at DESC
                    )
                    """
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS evaluation_runs (
                        id BIGSERIAL PRIMARY KEY,
                        principal_id TEXT NOT NULL,
                        metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
                        results JSONB NOT NULL DEFAULT '[]'::jsonb,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )

                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS
                        idx_evaluation_runs_principal_created
                    ON evaluation_runs (
                        principal_id,
                        created_at DESC
                    )
                    """
                )

        # Mark ready only after the transaction commits successfully.
        _evaluation_schema_ready = True


# =========================================================
# Evaluation dataset endpoints
# =========================================================

@router.post(
    "/cases",
    status_code=status.HTTP_201_CREATED,
)
def create_evaluation_case(
    payload: EvaluationCaseCreate,
    principal_id: str = Depends(authenticate_user),
):
    ensure_evaluation_tables()

    question = payload.question.strip()

    if not question:
        raise HTTPException(
            status_code=422,
            detail="The evaluation question cannot be blank.",
        )

    if any(
        document_id <= 0
        for document_id in payload.expected_document_ids
    ):
        raise HTTPException(
            status_code=422,
            detail="Expected document IDs must be positive integers.",
        )

    expected_ids = sorted(set(payload.expected_document_ids))

    with psycopg.connect(
        DATABASE_URL,
        connect_timeout=20,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO evaluation_cases (
                    principal_id,
                    question,
                    expected_answer,
                    expected_document_ids
                )
                VALUES (%s, %s, %s, %s)
                RETURNING
                    id,
                    question,
                    expected_answer,
                    expected_document_ids,
                    created_at
                """,
                (
                    principal_id,
                    question,
                    payload.expected_answer.strip(),
                    expected_ids,
                ),
            )

            row = cur.fetchone()

    return {
        "id": row[0],
        "question": row[1],
        "expected_answer": row[2],
        "expected_document_ids": row[3],
        "created_at": row[4],
    }


@router.get("/cases")
def list_evaluation_cases(
    principal_id: str = Depends(authenticate_user),
):
    ensure_evaluation_tables()

    with psycopg.connect(
        DATABASE_URL,
        connect_timeout=20,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    question,
                    expected_answer,
                    expected_document_ids,
                    created_at
                FROM evaluation_cases
                WHERE principal_id = %s
                ORDER BY created_at DESC, id DESC
                """,
                (principal_id,),
            )

            rows = cur.fetchall()

    return {
        "cases": [
            {
                "id": row[0],
                "question": row[1],
                "expected_answer": row[2],
                "expected_document_ids": row[3],
                "created_at": row[4],
            }
            for row in rows
        ],
        "total": len(rows),
    }


@router.delete("/cases/{case_id}")
def delete_evaluation_case(
    case_id: int,
    principal_id: str = Depends(authenticate_user),
):
    ensure_evaluation_tables()

    with psycopg.connect(
        DATABASE_URL,
        connect_timeout=20,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                DELETE FROM evaluation_cases
                WHERE id = %s
                  AND principal_id = %s
                RETURNING id
                """,
                (case_id, principal_id),
            )

            deleted = cur.fetchone()

    if deleted is None:
        raise HTTPException(
            status_code=404,
            detail="Evaluation case not found.",
        )

    return {
        "deleted": True,
        "case_id": deleted[0],
    }


# =========================================================
# Execute an evaluation
# =========================================================

@router.post(
    "/runs",
    status_code=status.HTTP_201_CREATED,
)
def run_evaluation(
    principal_id: str = Depends(authenticate_user),
):
    """
    Evaluate the signed-in employee's saved questions.

    Metrics:
    - answer_rate: completed cases that did not abstain
    - abstention_rate: completed cases that abstained
    - retrieval_hit_rate: evaluable cases retrieving at least one
      expected document
    - average_latency_ms: average processing time per case

    These metrics measure system behavior, not semantic answer accuracy.
    """
    ensure_evaluation_tables()

    with psycopg.connect(
        DATABASE_URL,
        connect_timeout=20,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    question,
                    expected_answer,
                    expected_document_ids
                FROM evaluation_cases
                WHERE principal_id = %s
                ORDER BY id ASC
                """,
                (principal_id,),
            )

            cases = cur.fetchall()

    if not cases:
        raise HTTPException(
            status_code=400,
            detail=(
                "Your evaluation dataset is empty. "
                "Create at least one evaluation case first."
            ),
        )

    results = []
    answered_count = 0
    abstained_count = 0
    retrieval_hit_count = 0
    retrieval_evaluable_count = 0
    total_latency_ms = 0.0

    for case_id, question, expected_answer, expected_ids in cases:
        started_at = time.perf_counter()

        try:
            answer_result = generate_answer(
                question=question,
                principal_id=principal_id,
                top_k=5,
            )

            latency_ms = round(
                (time.perf_counter() - started_at) * 1000,
                2,
            )
            total_latency_ms += latency_ms

            answer = str(answer_result.get("answer", ""))
            abstained = bool(
                answer_result.get("abstained", False)
            )

            sources = answer_result.get("sources", [])

            if not isinstance(sources, list):
                sources = []

            retrieved_ids = set()

            for source in sources:
                if not isinstance(source, dict):
                    continue

                document_id = source.get("document_id")

                if document_id is None:
                    continue

                try:
                    retrieved_ids.add(int(document_id))
                except (TypeError, ValueError):
                    continue

            retrieved_ids = sorted(retrieved_ids)

            if abstained:
                abstained_count += 1
            else:
                answered_count += 1

            expected_ids = list(expected_ids or [])
            retrieval_hit = None

            if expected_ids:
                retrieval_evaluable_count += 1

                retrieval_hit = bool(
                    set(expected_ids).intersection(retrieved_ids)
                )

                if retrieval_hit:
                    retrieval_hit_count += 1

            results.append(
                {
                    "case_id": case_id,
                    "question": question,
                    "expected_answer": expected_answer,
                    "answer": answer,
                    "clean_answer": str(answer_result.get("clean_answer", answer)),
                    "confidence_score": answer_result.get("confidence_score"),
                    "abstained": abstained,
                    "expected_document_ids": expected_ids,
                    "retrieved_document_ids": retrieved_ids,
                    "retrieval_hit": retrieval_hit,
                    "source_count": len(sources),
                    "latency_ms": latency_ms,
                    "status": "completed",
                }
            )

        except Exception as exc:
            latency_ms = round(
                (time.perf_counter() - started_at) * 1000,
                2,
            )
            total_latency_ms += latency_ms

            # Do not expose internal exception details to API clients.
            results.append(
                {
                    "case_id": case_id,
                    "question": question,
                    "expected_answer": expected_answer,
                    "status": "error",
                    "error_type": type(exc).__name__,
                    "expected_document_ids": list(expected_ids or []),
                    "retrieved_document_ids": [],
                    "latency_ms": latency_ms,
                }
            )

    total = len(cases)
    completed = answered_count + abstained_count
    error_count = total - completed

    metrics = {
        "total_cases": total,
        "completed_cases": completed,
        "error_count": error_count,
        "answer_rate": (
            round(answered_count / completed, 4)
            if completed
            else None
        ),
        "abstention_rate": (
            round(abstained_count / completed, 4)
            if completed
            else None
        ),
        "retrieval_hit_rate": (
            round(
                retrieval_hit_count / retrieval_evaluable_count,
                4,
            )
            if retrieval_evaluable_count
            else None
        ),
        "retrieval_evaluable_cases": retrieval_evaluable_count,
        "average_latency_ms": round(
            total_latency_ms / total,
            2,
        ),
    }

    with psycopg.connect(
        DATABASE_URL,
        connect_timeout=20,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO evaluation_runs (
                    principal_id,
                    metrics,
                    results
                )
                VALUES (%s, %s, %s)
                RETURNING id, created_at
                """,
                (
                    principal_id,
                    Jsonb(metrics),
                    Jsonb(results),
                ),
            )

            run_id, created_at = cur.fetchone()

    return {
        "run_id": run_id,
        "created_at": created_at,
        "metrics": metrics,
        "results": results,
    }


# =========================================================
# Evaluation run history
# =========================================================

@router.get("/runs")
def list_evaluation_runs(
    limit: int = 20,
    principal_id: str = Depends(authenticate_user),
):
    ensure_evaluation_tables()

    if not 1 <= limit <= 100:
        raise HTTPException(
            status_code=422,
            detail="Limit must be between 1 and 100.",
        )

    with psycopg.connect(
        DATABASE_URL,
        connect_timeout=20,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, metrics, created_at
                FROM evaluation_runs
                WHERE principal_id = %s
                ORDER BY created_at DESC, id DESC
                LIMIT %s
                """,
                (principal_id, limit),
            )

            rows = cur.fetchall()

    return {
        "runs": [
            {
                "run_id": row[0],
                "metrics": row[1],
                "created_at": row[2],
            }
            for row in rows
        ],
        "total": len(rows),
    }


@router.get("/runs/{run_id}")
def get_evaluation_run(
    run_id: int,
    principal_id: str = Depends(authenticate_user),
):
    ensure_evaluation_tables()

    with psycopg.connect(
        DATABASE_URL,
        connect_timeout=20,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, metrics, results, created_at
                FROM evaluation_runs
                WHERE id = %s
                  AND principal_id = %s
                """,
                (run_id, principal_id),
            )

            row = cur.fetchone()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="Evaluation run not found.",
        )

    return {
        "run_id": row[0],
        "metrics": row[1],
        "results": row[2],
        "created_at": row[3],
    }
