
import logging
import threading

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query
from psycopg.types.json import Jsonb

from app.core.auth import authenticate_user
from app.core.config import DATABASE_URL


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/observability",
    tags=["Observability"],
)

_schema_lock = threading.Lock()
_schema_ready = False

_OBSERVABILITY_LOCK_KEY = 728194604


def ensure_observability_table() -> None:
    """Initialize the observability table without resetting existing data."""
    global _schema_ready

    if _schema_ready:
        return

    with _schema_lock:
        if _schema_ready:
            return

        with psycopg.connect(
            DATABASE_URL,
            connect_timeout=20,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT pg_advisory_xact_lock(%s)",
                    (_OBSERVABILITY_LOCK_KEY,),
                )

                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS observability_events (
                        id BIGSERIAL PRIMARY KEY,
                        principal_id TEXT,
                        event_type TEXT NOT NULL,
                        severity TEXT NOT NULL DEFAULT 'INFO',
                        duration_ms DOUBLE PRECISION,
                        status_code INTEGER,
                        details JSONB NOT NULL DEFAULT '{}'::jsonb,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )

                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS
                        idx_observability_events_created
                    ON observability_events (created_at DESC)
                    """
                )

                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS
                        idx_observability_events_principal_created
                    ON observability_events (
                        principal_id,
                        created_at DESC
                    )
                    """
                )

        _schema_ready = True


def record_observability_event(
    event_type: str,
    severity: str = "INFO",
    principal_id: str | None = None,
    duration_ms: float | None = None,
    status_code: int | None = None,
    details: dict | None = None,
) -> None:
    """Record an operational event without disrupting the application."""
    if severity not in {"INFO", "WARNING", "ERROR"}:
        raise ValueError("Invalid observability severity.")

    try:
        ensure_observability_table()

        with psycopg.connect(
            DATABASE_URL,
            connect_timeout=5,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO observability_events (
                        principal_id,
                        event_type,
                        severity,
                        duration_ms,
                        status_code,
                        details
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        principal_id,
                        event_type[:100],
                        severity,
                        duration_ms,
                        status_code,
                        Jsonb(details or {}),
                    ),
                )

    except Exception:
        # Monitoring failures must not break the main application.
        logger.exception("Unable to persist observability event.")


@router.get("/summary")
def get_observability_summary(
    principal_id: str = Depends(authenticate_user),
):
    """Return operational metrics for the authenticated employee."""
    ensure_observability_table()

    try:
        with psycopg.connect(
            DATABASE_URL,
            connect_timeout=10,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        COUNT(*) AS total_events,
                        COUNT(*) FILTER (
                            WHERE severity = 'ERROR'
                        ) AS error_count,
                        COUNT(*) FILTER (
                            WHERE severity = 'WARNING'
                        ) AS warning_count,
                        COUNT(*) FILTER (
                            WHERE status_code >= 500
                        ) AS server_error_count,
                        ROUND(
                            AVG(duration_ms)::numeric,
                            2
                        ) AS average_latency_ms,
                        ROUND(
                            percentile_cont(0.95)
                            WITHIN GROUP (ORDER BY duration_ms)::numeric,
                            2
                        ) AS p95_latency_ms
                    FROM observability_events
                    WHERE principal_id = %s
                      AND created_at >= NOW() - INTERVAL '24 hours'
                    """,
                    (principal_id,),
                )

                row = cur.fetchone()

                cur.execute(
                    """
                    SELECT
                        event_type,
                        COUNT(*) AS event_count
                    FROM observability_events
                    WHERE principal_id = %s
                      AND created_at >= NOW() - INTERVAL '24 hours'
                    GROUP BY event_type
                    ORDER BY event_count DESC, event_type
                    LIMIT 10
                    """,
                    (principal_id,),
                )

                event_counts = [
                    {
                        "event_type": item[0],
                        "count": item[1],
                    }
                    for item in cur.fetchall()
                ]

        return {
            "window": "24 hours",
            "total_events": row[0],
            "error_count": row[1],
            "warning_count": row[2],
            "server_error_count": row[3],
            "average_latency_ms": (
                float(row[4]) if row[4] is not None else None
            ),
            "p95_latency_ms": (
                float(row[5]) if row[5] is not None else None
            ),
            "event_counts": event_counts,
        }

    except psycopg.Error as exc:
        logger.exception("Observability summary query failed.")
        raise HTTPException(
            status_code=503,
            detail="Observability metrics are temporarily unavailable.",
        ) from exc


@router.get("/events")
def list_observability_events(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    severity: str | None = Query(default=None),
    principal_id: str = Depends(authenticate_user),
):
    """List only the authenticated employee's operational events."""
    ensure_observability_table()

    if severity is not None:
        severity = severity.strip().upper()

        if severity not in {"INFO", "WARNING", "ERROR"}:
            raise HTTPException(
                status_code=422,
                detail="Severity must be INFO, WARNING, or ERROR.",
            )

    # Build the WHERE clause only from fixed SQL fragments.
    # This avoids PostgreSQL's inability to infer the type of a NULL
    # parameter in expressions such as (%s IS NULL OR severity = %s).
    conditions = ["principal_id = %s"]
    params: list = [principal_id]

    if severity is not None:
        conditions.append("severity = %s")
        params.append(severity)

    where_clause = " AND ".join(conditions)

    try:
        with psycopg.connect(
            DATABASE_URL,
            connect_timeout=10,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT
                        id,
                        event_type,
                        severity,
                        duration_ms,
                        status_code,
                        details,
                        created_at
                    FROM observability_events
                    WHERE {where_clause}
                    ORDER BY created_at DESC, id DESC
                    LIMIT %s OFFSET %s
                    """,
                    (*params, limit, offset),
                )

                rows = cur.fetchall()

                cur.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM observability_events
                    WHERE {where_clause}
                    """,
                    tuple(params),
                )

                total = cur.fetchone()[0]

        return {
            "events": [
                {
                    "id": row[0],
                    "event_type": row[1],
                    "severity": row[2],
                    "duration_ms": row[3],
                    "status_code": row[4],
                    "details": row[5] or {},
                    "created_at": row[6],
                }
                for row in rows
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    except psycopg.Error as exc:
        logger.exception("Observability event query failed.")
        raise HTTPException(
            status_code=503,
            detail="Observability events are temporarily unavailable.",
        ) from exc
