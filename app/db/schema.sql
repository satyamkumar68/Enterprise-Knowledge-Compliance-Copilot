
-- Enable pgvector for embedding storage.
CREATE EXTENSION IF NOT EXISTS vector;


-- =========================================================
-- Documents
-- =========================================================

CREATE TABLE IF NOT EXISTS documents (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    filename TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    owner_principal_id TEXT,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (
            status IN (
                'pending',
                'processing',
                'indexed',
                'failed'
            )
        ),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT documents_owner_content_hash_key UNIQUE (owner_principal_id, content_hash)
);


-- =========================================================
-- Document chunks and embeddings
-- =========================================================

CREATE TABLE IF NOT EXISTS document_chunks (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id BIGINT NOT NULL
        REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(768) NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    tsv TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', content)) STORED,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunks_document_id
    ON document_chunks(document_id);

CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw
    ON document_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

CREATE INDEX IF NOT EXISTS idx_chunks_tsv
    ON document_chunks USING gin (tsv);


-- =========================================================
-- Document-level read permissions
-- =========================================================

CREATE TABLE IF NOT EXISTS document_permissions (
    document_id BIGINT NOT NULL
        REFERENCES documents(id) ON DELETE CASCADE,
    principal_id TEXT NOT NULL,
    permission TEXT NOT NULL DEFAULT 'read'
        CHECK (permission IN ('read')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (document_id, principal_id)
);

CREATE INDEX IF NOT EXISTS idx_document_permissions_principal
    ON document_permissions(principal_id, document_id);


-- =========================================================
-- API users and hashed tokens
-- =========================================================

CREATE TABLE IF NOT EXISTS app_users (
    principal_id TEXT PRIMARY KEY,
    token_hash TEXT NOT NULL UNIQUE,
    password_hash TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- =========================================================
-- User sessions and CSRF
-- =========================================================

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


-- =========================================================
-- Security audit events
-- =========================================================

CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_type TEXT NOT NULL,
    principal_id TEXT,
    outcome TEXT NOT NULL
        CHECK (
            outcome IN (
                'success',
                'failure',
                'denied',
                'error'
            )
        ),
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at
    ON audit_logs(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_audit_logs_principal
    ON audit_logs(principal_id, created_at DESC);


-- =========================================================
-- Evaluation cases and benchmark runs
-- =========================================================

CREATE TABLE IF NOT EXISTS evaluation_cases (
    id BIGSERIAL PRIMARY KEY,
    principal_id TEXT NOT NULL,
    question TEXT NOT NULL,
    expected_answer TEXT NOT NULL DEFAULT '',
    expected_document_ids INTEGER[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_evaluation_cases_principal_created
    ON evaluation_cases (principal_id, created_at DESC);

CREATE TABLE IF NOT EXISTS evaluation_runs (
    id BIGSERIAL PRIMARY KEY,
    principal_id TEXT NOT NULL,
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    results JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_evaluation_runs_principal_created
    ON evaluation_runs (principal_id, created_at DESC);


-- =========================================================
-- Observability and operational telemetry
-- =========================================================

CREATE TABLE IF NOT EXISTS observability_events (
    id BIGSERIAL PRIMARY KEY,
    principal_id TEXT,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'INFO',
    duration_ms DOUBLE PRECISION,
    status_code INTEGER,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_observability_events_created_at
    ON observability_events (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_observability_events_principal
    ON observability_events (principal_id, created_at DESC);

