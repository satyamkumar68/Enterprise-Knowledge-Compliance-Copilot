
import hashlib
import logging
import secrets
import time

import psycopg
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.audit import log_audit_event
from app.core.config import DATABASE_URL


logger = logging.getLogger(__name__)

bearer_scheme = HTTPBearer(auto_error=False)

SESSION_COOKIE = "kc_session"
CSRF_COOKIE = "kc_csrf"
CSRF_HEADER = "X-CSRF-Token"

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}

# Cache of recently audited session tokens to prevent flooding the audit log on every request.
# Maps token hash -> timestamp of last audit log event.
_session_audit_cache: dict[str, float] = {}
_SESSION_AUDIT_TTL_SECONDS = 3600.0  # Log session auth at most once per hour per session



def hash_token(token: str) -> str:
    """Return the SHA-256 hex digest of a token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_api_token() -> str:
    """Generate a cryptographically secure API token."""
    return secrets.token_urlsafe(32)


def _unauthorized(
    detail: str = "Authentication required.",
) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _authenticate_session(request: Request) -> str:
    """Validate the session cookie and enforce CSRF on unsafe methods."""

    session_token = request.cookies.get(SESSION_COOKIE)

    if not session_token:
        raise _unauthorized("Session cookie is missing.")

    csrf_cookie = request.cookies.get(CSRF_COOKIE)
    csrf_header = request.headers.get(CSRF_HEADER)

    if request.method.upper() not in SAFE_METHODS:
        if (
            not csrf_cookie
            or not csrf_header
            or not secrets.compare_digest(csrf_cookie, csrf_header)
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token missing or invalid.",
            )

    with psycopg.connect(DATABASE_URL, connect_timeout=20) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT s.principal_id, s.csrf_token_hash
                FROM user_sessions AS s
                JOIN app_users AS u
                  ON u.principal_id = s.principal_id
                WHERE s.session_token_hash = %s
                  AND s.expires_at > NOW()
                  AND u.is_active = TRUE
                """,
                (hash_token(session_token),),
            )
            row = cur.fetchone()

    if row is None:
        raise _unauthorized("Session is invalid or expired.")

    principal_id, stored_csrf_hash = row

    if request.method.upper() not in SAFE_METHODS:
        if not secrets.compare_digest(
            hash_token(csrf_header),
            stored_csrf_hash,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF token is invalid.",
            )

    return principal_id


def _authenticate_bearer(
    credentials: HTTPAuthorizationCredentials,
) -> str:
    """Validate a legacy development Bearer token."""

    token_digest = hash_token(credentials.credentials)

    with psycopg.connect(DATABASE_URL, connect_timeout=20) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT principal_id
                FROM app_users
                WHERE token_hash = %s
                  AND is_active = TRUE
                """,
                (token_digest,),
            )
            row = cur.fetchone()

    if row is None:
        log_audit_event(
            event_type="authentication",
            outcome="failure",
            details={
                "reason": "invalid_or_inactive_token",
                "method": "bearer_token",
            },
        )
        raise _unauthorized("Invalid authentication credentials.")

    principal_id = row[0]

    log_audit_event(
        event_type="authentication",
        outcome="success",
        principal_id=principal_id,
        details={"method": "bearer_token"},
    )

    return principal_id


def authenticate_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
) -> str:
    """
    Authenticate using a session cookie or legacy Bearer token.

    Session authentication takes precedence when a session cookie exists.
    Diagnostic logging never prints actual credentials or cookie values.
    """

    session_token = request.cookies.get(SESSION_COOKIE)
    csrf_cookie = request.cookies.get(CSRF_COOKIE)

    logger.debug(
        "Auth check: path=%s method=%s host=%s session=%s csrf=%s bearer=%s",
        request.url.path,
        request.method,
        request.headers.get("host"),
        bool(session_token),
        bool(csrf_cookie),
        credentials is not None,
    )

    if session_token:
        principal_id = _authenticate_session(request)

        # Log session authentication only for new sessions or periodically
        # to prevent flooding the database with an audit insert on every API call.
        now = time.time()
        token_digest = hash_token(session_token)
        last_audited = _session_audit_cache.get(token_digest, 0.0)

        if now - last_audited > _SESSION_AUDIT_TTL_SECONDS:
            _session_audit_cache[token_digest] = now
            if len(_session_audit_cache) > 2000:
                expired_keys = [
                    k
                    for k, v in _session_audit_cache.items()
                    if now - v > _SESSION_AUDIT_TTL_SECONDS
                ]
                for k in expired_keys:
                    _session_audit_cache.pop(k, None)

            log_audit_event(
                event_type="authentication",
                outcome="success",
                principal_id=principal_id,
                details={
                    "method": "password_session",
                    "path": request.url.path,
                },
            )

        return principal_id

    if credentials is not None:
        return _authenticate_bearer(credentials)

    log_audit_event(
        event_type="authentication",
        outcome="failure",
        details={
            "reason": "missing_session_and_bearer_token",
            "path": request.url.path,
        },
    )

    raise _unauthorized()
