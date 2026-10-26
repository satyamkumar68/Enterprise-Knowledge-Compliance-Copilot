# Current State of the Repository

**Date:** 2026-10-26  
**Repository:** Enterprise Knowledge & Compliance Copilot  
**Stack:** FastAPI 0.143.0, React 19, PostgreSQL 16 + pgvector, Ollama 0.34.4  

---

## 1. Architecture As-Is

The repository implements a local-first enterprise question-answering system (RAG) with the following components:

- **Backend (`app/`)**:
  - `app/api/main.py`: FastAPI entrypoint with endpoints for document upload, deletion, listing, synchronous question answering (`/api/v1/ask`), and Server-Sent Events streaming (`/api/v1/ask/stream`).
  - `app/core/auth.py`: Token generation, SHA-256 and Argon2 password hashing, session tokens, and CSRF token verification.
  - `app/core/audit.py`: PostgreSQL-backed audit trail logging for authentication, document lifecycle, and query events.
  - `app/retrieval/retriever.py`: Hybrid search executing:
    1. Vector similarity search via pgvector cosine distance (`<=>`) using HNSW index.
    2. Full-text search via PostgreSQL `tsvector` with GIN indexing using `plainto_tsquery('english', query)`.
    3. Merged via Reciprocal Rank Fusion (RRF) with constant `k=60`.
    4. **Retrieval-time RBAC**: Enforced directly in SQL via `JOIN document_permissions dp ON dp.document_id = d.id WHERE dp.principal_id = %s AND dp.permission = 'read'`.
  - `app/generation/answer.py`: Strict system prompt instructing the LLM to answer using only supplied citations, output bracketed citations (`[Source X]`), or abstain with a standardized phrase (`"The available documents do not contain enough information to answer this question."`).
  - `app/observability/routes.py`: Endpoints and schema for storing operational events, latencies, and error telemetry.
  - `app/evaluation/routes.py`: Database-backed evaluation endpoints for storing manual evaluation cases and runs via the React UI.

- **Frontend (`frontend/`)**:
  - Built with React 19 and Vite 8.3.4.
  - Features real-time SSE typewriter streaming, Knowledge Base document manager with drag-and-drop file upload, permissions manager, evaluation dashboard with SVG gauges, and audit logs view.

- **Data Storage**:
  - PostgreSQL 16 on port 5432 with `pgvector` extension enabled.
  - Tables: `documents`, `document_chunks` (vector 768, HNSW index), `document_permissions`, `app_users`, `user_sessions`, `audit_events`, `observability_events`, `evaluation_cases`, `evaluation_runs`.

- **Inference Engine**:
  - Ollama running locally at `http://localhost:11434`.
  - Installed models: `qwen3:4b` (standard generation), `nomic-embed-text:latest` (embeddings), `qwen2.5-coder:1.5b` (fast profile).

---

## 2. Test Suite & Health Status

- **Test Framework**: `pytest` 9.1.1.
- **Current Test Count**: **46 tests, 0 failures, 100% passing**.
- **Passing Test Suites**:
  - `tests/test_answer.py` (7 tests): Citation parsing, abstention fallback, confidence calculation.
  - `tests/test_api_auth.py` (4 tests): Unauthorized rejection, missing token 401, authorized principal pass-through.
  - `tests/test_api_documents.py` (4 tests): Permission-scoped document listing and deletion.
  - `tests/test_audit.py` (4 tests): Audit event logging and schema assertions.
  - `tests/test_bugfixes.py` (5 tests): Edge-case sanitization and regression prevention.
  - `tests/test_chunking_quality.py` (5 tests): Sliding-window chunking and token boundaries.
  - `tests/test_ingestion.py` (7 tests): Document parsing (Markdown, TXT, PDF, DOCX) and embedding storage.
  - `tests/test_query_rewriter.py` (5 tests): Query expansion logic.
  - `tests/test_retriever.py` (5 tests): RRF rank fusion and distance calculation.

---

## 3. How to Run (Current)

```bash
# 1. Database
# PostgreSQL 16 + pgvector running on port 5432 (database: knowledge_copilot)

# 2. Run Backend
$env:PYTHONPATH="."
.venv\Scripts\python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000

# 3. Run Frontend
cd frontend
npm run dev

# 4. Run Test Suite
$env:PYTHONPATH="."
.venv\Scripts\pytest -v
```

---

## 4. Known Gaps & Target Improvements

1. **No Standalone Reproducible Eval Dataset**:
   - `eval/golden.jsonl` does not exist. No golden set of unanswerable and RBAC-restricted questions exists to independently prove claims.
2. **Missing Automated CLI Evaluation Script**:
   - No `eval/run_eval.py` that computes Recall@k, MRR, Faithfulness, Abstention precision, and RBAC leakage rate in a single command.
3. **Unverified Latency Claims**:
   - README claims "17.7s → ~2.0s TTFT", but there is no hardware-grounded benchmark script (`eval/bench_ttft.py`) measuring this with logged system specifications.
4. **No Automated Prompt-Injection Tests**:
   - Lack of dedicated adversarial document test fixtures verifying defense against prompt injection.
5. **No Turnkey Docker Setup**:
   - No `docker-compose.yml` or `Dockerfile`; users currently have to run standalone docker and manually copy schemas.
6. **No Continuous Integration (CI)**:
   - No `.github/workflows/ci.yml` to automatically run tests and eval smoke tests on push.
7. **Documentation Depth**:
   - Missing `docs/ARCHITECTURE.md` and `docs/DECISIONS.md` detailing architectural trade-offs (e.g. why pgvector, why RRF, why local Ollama).
