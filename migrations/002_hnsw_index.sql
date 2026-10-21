-- Add an HNSW index for fast approximate nearest-neighbour search.
-- Uses CONCURRENTLY so the table remains available during the build.
-- Run outside a transaction block:
--   psql -f migrations/002_hnsw_index.sql

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_chunks_embedding_hnsw
    ON document_chunks USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);
