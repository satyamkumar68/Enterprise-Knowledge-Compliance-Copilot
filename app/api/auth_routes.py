
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone

import psycopg
from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from app.core.auth import hash_token
from app.core.audit import log_audit_event
from app.core.config import DATABASE_URL
from app.core.passwords import hash_password, verify_password


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

SESSION_COOKIE = "kc_session"
CSRF_COOKIE = "kc_csrf"
SESSION_DURATION_HOURS = 8

COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"


class LoginRequest(BaseModel):
    principal_id: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=1024)


class RegisterRequest(BaseModel):
    principal_id: str = Field(min_length=3, max_length=128)
    password: str = Field(min_length=12, max_length=1024)


def _clear_cookies(response: Response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE,
        path="/",
        secure=COOKIE_SECURE,
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(
        key=CSRF_COOKIE,
        path="/",
        secure=COOKIE_SECURE,
        httponly=False,
        samesite="lax",
    )


def _create_session(principal_id: str, response: Response) -> dict:
    """Create a session and set browser cookies."""

    session_token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(
        hours=SESSION_DURATION_HOURS
    )

    with psycopg.connect(DATABASE_URL, connect_timeout=20) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM user_sessions WHERE expires_at <= NOW()"
            )

            cur.execute(
                """
                INSERT INTO user_sessions (
                    session_token_hash,
                    principal_id,
                    csrf_token_hash,
                    expires_at
                )
                VALUES (%s, %s, %s, %s)
                """,
                (
                    hash_token(session_token),
                    principal_id,
                    hash_token(csrf_token),
                    expires_at,
                ),
            )

    max_age = SESSION_DURATION_HOURS * 60 * 60

    response.set_cookie(
        key=SESSION_COOKIE,
        value=session_token,
        max_age=max_age,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
    )

    response.set_cookie(
        key=CSRF_COOKIE,
        value=csrf_token,
        max_age=max_age,
        httponly=False,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
    )

    return {
        "authenticated": True,
        "principal_id": principal_id,
        "expires_at": expires_at.isoformat(),
    }


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest):
    """Create a standard employee account."""

    principal_id = payload.principal_id.strip()

    if len(principal_id) < 3:
        raise HTTPException(
            status_code=422,
            detail="Employee ID must contain at least 3 characters.",
        )

    if any(character.isspace() for character in principal_id):
        raise HTTPException(
            status_code=422,
            detail="Employee ID cannot contain spaces.",
        )

    try:
        password_hash = hash_password(payload.password)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    # This is a random legacy compatibility value, not a login credential.
    # Only its hash is stored. Verify the intended meaning of token_hash
    # before using public self-registration in production.
    registration_token_hash = hash_token(secrets.token_urlsafe(32))

    try:
        with psycopg.connect(
            DATABASE_URL,
            connect_timeout=20,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO app_users (
                        principal_id,
                        password_hash,
                        token_hash,
                        is_active
                    )
                    VALUES (%s, %s, %s, TRUE)
                    ON CONFLICT (principal_id) DO NOTHING
                    RETURNING principal_id
                    """,
                    (
                        principal_id,
                        password_hash,
                        registration_token_hash,
                    ),
                )

                row = cur.fetchone()

        if row is None:
            raise HTTPException(
                status_code=409,
                detail="An account with this employee ID already exists.",
            )

    except HTTPException:
        raise
    except psycopg.Error as exc:
        logger.exception("Account registration failed.")
        raise HTTPException(
            status_code=503,
            detail="Account registration is temporarily unavailable.",
        ) from exc

    try:
        log_audit_event(
            event_type="account_registration",
            outcome="success",
            principal_id=principal_id,
            details={"method": "self_registration"},
        )
    except Exception:
        logger.exception("Account created, but registration audit failed.")

    return {
        "created": True,
        "principal_id": principal_id,
        "message": "Account created. You can now sign in.",
    }


@router.post("/login")
def login(payload: LoginRequest, response: Response):
    """Verify credentials and create a cookie-backed session."""

    principal_id = payload.principal_id.strip()

    try:
        with psycopg.connect(
            DATABASE_URL,
            connect_timeout=20,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT password_hash
                    FROM app_users
                    WHERE principal_id = %s
                      AND is_active = TRUE
                    """,
                    (principal_id,),
                )
                row = cur.fetchone()

    except psycopg.Error as exc:
        logger.exception("Login database query failed.")
        raise HTTPException(
            status_code=503,
            detail="Authentication is temporarily unavailable.",
        ) from exc

    if (
        row is None
        or not row[0]
        or not verify_password(payload.password, row[0])
    ):
        try:
            log_audit_event(
                event_type="authentication",
                outcome="failure",
                principal_id=None,
                details={
                    "method": "password",
                    "reason": "invalid_credentials",
                },
            )
        except Exception:
            logger.exception("Failed to record login failure.")

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid employee ID or password.",
        )

    try:
        result = _create_session(principal_id, response)
    except psycopg.Error as exc:
        logger.exception("Unable to create login session.")
        raise HTTPException(
            status_code=503,
            detail="Unable to create a session. Please try again.",
        ) from exc

    try:
        log_audit_event(
            event_type="authentication",
            outcome="success",
            principal_id=principal_id,
            details={"method": "password_session"},
        )
    except Exception:
        logger.exception("Login succeeded, but audit logging failed.")

    return result


@router.get("/me")
def current_session(request: Request):
    """Return the employee associated with the current valid session."""

    token = request.cookies.get(SESSION_COOKIE)

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated.",
        )

    try:
        with psycopg.connect(
            DATABASE_URL,
            connect_timeout=20,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT s.principal_id, s.expires_at
                    FROM user_sessions AS s
                    JOIN app_users AS u
                      ON u.principal_id = s.principal_id
                    WHERE s.session_token_hash = %s
                      AND s.expires_at > NOW()
                      AND u.is_active = TRUE
                    """,
                    (hash_token(token),),
                )
                row = cur.fetchone()

    except psycopg.Error as exc:
        logger.exception("Session verification query failed.")
        raise HTTPException(
            status_code=503,
            detail="Session verification is temporarily unavailable.",
        ) from exc

    if row is None:
        raise HTTPException(
            status_code=401,
            detail="Session is invalid or expired.",
        )

    return {
        "authenticated": True,
        "principal_id": row[0],
        "expires_at": row[1].isoformat(),
    }


@router.post("/logout")
def logout(request: Request, response: Response):
    """Revoke the current session and clear its browser cookies."""

    token = request.cookies.get(SESSION_COOKIE)
    csrf_cookie = request.cookies.get(CSRF_COOKIE)
    csrf_header = request.headers.get("X-CSRF-Token")

    if not token:
        _clear_cookies(response)
        return {"authenticated": False, "message": "Logged out."}

    if (
        not csrf_cookie
        or not csrf_header
        or not secrets.compare_digest(csrf_cookie, csrf_header)
    ):
        raise HTTPException(
            status_code=403,
            detail="CSRF token missing or invalid.",
        )

    try:
        with psycopg.connect(
            DATABASE_URL,
            connect_timeout=20,
        ) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT principal_id
                    FROM user_sessions
                    WHERE session_token_hash = %s
                      AND csrf_token_hash = %s
                      AND expires_at > NOW()
                    """,
                    (hash_token(token), hash_token(csrf_header)),
                )
                row = cur.fetchone()

                cur.execute(
                    """
                    DELETE FROM user_sessions
                    WHERE session_token_hash = %s
                    """,
                    (hash_token(token),),
                )

    except psycopg.Error as exc:
        logger.exception("Logout session revocation failed.")
        raise HTTPException(
            status_code=503,
            detail="Unable to complete logout. Please try again.",
        ) from exc

    if row:
        try:
            log_audit_event(
                event_type="logout",
                outcome="success",
                principal_id=row[0],
                details={"method": "password_session"},
            )
        except Exception:
            logger.exception("Session revoked, but logout audit failed.")

    _clear_cookies(response)
    return {"authenticated": False, "message": "Logged out."}
