
-- migrations/001_auth_sessions.sql
-- Add password authentication and server-managed sessions.
-- Existing users, tokens, documents, and permissions are preserved.

BEGIN;

ALTER TABLE app_users
    ADD COLUMN IF NOT EXISTS password_hash TEXT;

CREATE TABLE IF NOT EXISTS user_sessions (
    session_token_hash TEXT PRIMARY KEY,
    principal_id TEXT NOT NULL
        REFERENCES app_users(principal_id) ON DELETE CASCADE,
    csrf_token_hash TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_sessions_principal
    ON user_sessions(principal_id);

CREATE INDEX IF NOT EXISTS idx_user_sessions_expiry
    ON user_sessions(expires_at);

COMMIT;
