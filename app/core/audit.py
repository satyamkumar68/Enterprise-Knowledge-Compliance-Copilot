
import json
import logging

import psycopg

from app.core.config import DATABASE_URL


logger = logging.getLogger(__name__)


def log_audit_event(
    event_type: str,
    outcome: str,
    principal_id: str | None = None,
    details: dict | None = None,
) -> None:
    """Store a security audit event in PostgreSQL."""

    if outcome not in {"success", "failure", "denied", "error"}:
        raise ValueError("Invalid audit event outcome.")

    try:
        with psycopg.connect(
            DATABASE_URL,
            connect_timeout=20,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO audit_logs
                        (event_type, principal_id, outcome, details)
                    VALUES (%s, %s, %s, %s::jsonb)
                    """,
                    (
                        event_type,
                        principal_id,
                        outcome,
                        json.dumps(details or {}),
                    ),
                )
    except psycopg.Error as exc:
        logger.error("Audit logging failed: %s (%s)", type(exc).__name__, exc)

