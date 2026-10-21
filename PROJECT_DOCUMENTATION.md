# Enterprise Knowledge & Compliance Copilot — Comprehensive System Documentation

## 1. Executive Summary

The **Enterprise Knowledge & Compliance Copilot** is a production-grade, evidence-grounded Retrieval-Augmented Generation (RAG) and document intelligence platform. It is engineered to allow enterprise employees to query internal policy, compliance, technical, and operational documents while strictly enforcing document-level access permissions, eliminating hallucinated answers, logging security events, and tracking system observability.

Unlike generic RAG chatbots that expose all indexed text to every user, this system implements **security-first, zero-trust knowledge retrieval**:
- Knowledge is partitioned by employee identity (`principal_id`).
- Document vector searches run with strict SQL join constraints on document permission tables.
- The generation model (`qwen3:4b` via local Ollama) is bound to strict JSON schema outputs and **abstains** (`abstained: true`) if authorized evidence is insufficient or missing.
- Citations are programmatically cross-validated against retrieved chunks before being returned to the user.
- Any attempt to query knowledge resembling restricted documents triggers a background security audit alert.

---

## 2. Key Capabilities Implemented

| Capability | Implementation Detail | Status |
| :--- | :--- | :--- |
| **Multi-Format Ingestion** | Supports `.pdf` (pypdf), `.docx` (python-docx), `.md`, and `.txt` with UTF-8 fallback. | **Implemented & Tested** |
| **Deterministic Chunking** | Sliding-window word chunker (300 words/chunk, 50-word overlap) preserving metadata and source offsets. | **Implemented & Tested** |
| **Local Vector Embeddings** | Ollama `nomic-embed-text` (768 dimensions), normalized vector literals. | **Implemented & Tested** |
| **PostgreSQL + pgvector** | Vector similarity using cosine distance (`<=>`), indexed with HNSW (`m=16, ef_construction=64`). | **Implemented & Tested** |
| **Document-Level Authorization** | Owner-scoped uniqueness, explicit `document_permissions` check in SQL `JOIN`, multi-tenant isolation. | **Implemented & Tested** |
| **Restricted Document Probing** | Asynchronous background similarity check on restricted documents to catch reconnaissance attempts. | **Implemented & Tested** |
| **Evidence-Grounded Generation** | Ollama `qwen3:4b`, temperature 0, strict JSON schema output, anti-hallucination prompt guardrails. | **Implemented & Tested** |
| **Citation Verification** | Regex stripping of unverified LLM citations; only database-retrieved chunk IDs are cited. | **Implemented & Tested** |
| **Guaranteed Abstention** | Standardized refusal message when retrieved context is empty, below threshold, or irrelevant. | **Implemented & Tested** |
| **Hybrid Authentication** | Dual-mode: Bearer API tokens (hashed with SHA-256) and HTTP-only session cookies with CSRF protection. | **Implemented & Tested** |
| **Password Security** | PBKDF2-HMAC-SHA256 password hashing with constant-time comparison. | **Implemented & Tested** |
| **Database Connection Pool** | Multi-threaded `ConnectionPool` (`psycopg_pool`) for low-latency concurrent retrieval. | **Implemented & Tested** |
| **Observability & APM** | Tracks latency (average, p95), status codes, error rates, and event frequency over a 24-hour window. | **Implemented & Tested** |
| **RAG Evaluation Suite** | Golden dataset test cases, automated multi-metric evaluation runs (relevance, recall, latency, abstention). | **Implemented & Tested** |
| **Enterprise Audit Trail** | Tamper-resistant `audit_logs` table recording logins, logouts, access denials, uploads, and deletions. | **Implemented & Tested** |
| **Single-Page React Frontend** | Vite + React 19 dashboard with 8 dedicated views, Lucide icons, responsive drawer, and 4 themes. | **Implemented & Tested** |

---

## 3. High-Level Architecture & Flow

```
                           +---------------------------------------+
                           |          React 19 Frontend            |
                           |  (Vite, Lucide, Multi-theme, SPA)     |
                           +---------------------------------------+
                                        |             ^
                    Session Cookie/CSRF |             | JSON Evidence
                    or Bearer Token     v             | & Citations
                           +---------------------------------------+
                           |         FastAPI REST Gateway          |
                           |             (Port 8000)               |
                           +---------------------------------------+
                             |             |             |        |
    +------------------------+             |             |        +-------------------------+
    |                                      |             |                                  |
    v                                      v             v                                  v
+------------------+             +-----------------+ +--------------------+       +-------------------+
|  Auth & Session  |             | Document Upload | | Retrieval Engine   |       | Observability &   |
|  (PBKDF2/Cookie) |             | & Ingestion     | | & Permission Filter|       | Evaluation Engine |
+------------------+             +-----------------+ +--------------------+       +-------------------+
        |                                  |                     |                          |
        v                                  v                     v                          v
+-----------------------------------------------------------------------------------------------+
|                                PostgreSQL 16 + pgvector                                       |
|  - documents (owner_id, hash)            - document_chunks (vector 768, HNSW cosine index)   |
|  - document_permissions (principal_id)   - app_users & user_sessions                          |
|  - audit_logs (security events)          - observability_events & evaluation_runs/cases       |
+-----------------------------------------------------------------------------------------------+
        ^                                  |                     |
        |                                  v                     v
        |                        +------------------+  +-------------------+
        |                        |  Ollama Embed    |  |  Ollama Generate  |
        +------------------------| nomic-embed-text |  |     qwen3:4b      |
                                 +------------------+  +-------------------+
```

### End-to-End User Query Flow:
1. **Request**: The user submits a question via `POST /api/v1/ask` with their Bearer token or active session cookie.
2. **Authentication**: `authenticate_user` dependency validates the token hash or session cookie against `app_users`/`user_sessions`.
3. **Retrieval**: 
   - The question is converted into a 768-dimensional vector via `create_embedding` using Ollama (`nomic-embed-text`).
   - `retrieve_chunks` runs a pgvector cosine similarity query (`<=>`) with an inner join on `document_permissions` matching `principal_id` and `d.status = 'indexed'`.
   - In a non-blocking daemon thread, `_check_restricted_documents` checks whether the query closely resembles documents the user is *not* permitted to read. If distance $\le 0.35$, an audit warning is generated.
4. **Context Construction**: Retrieved chunks are formatted into numbered `[Source X]` context blocks with associated file names and excerpt text.
5. **Prompting & Generation**: Ollama (`qwen3:4b`) receives a strict system prompt instructing it to produce a constrained JSON object `{ "answer": "...", "abstained": bool, "source_ids": [1, 2] }` at `temperature=0` with `num_predict=180`.
6. **Validation & Filtering**: The backend validates that returned `source_ids` belong exclusively to authorized retrieved chunks. If the model hallucinates a non-existent source ID or abstains, the system returns a standard fallback abstention message.
7. **Observability**: An event is logged to `observability_events` with total duration in milliseconds, status code, and abstention outcome.

---

## 4. Complete File Inventory & Breakdown

The repository contains **94 total files** (89 project files excluding `.pytest_cache`).

### 4.1 Summary by Directory

| Directory / Category | File Count | Purpose |
| :--- | :---: | :--- |
| `app/api/` | 2 | Primary API routers (Main endpoints and Authentication/Session endpoints) |
| `app/core/` | 7 | Shared foundational modules (DB pool, auth, passwords, audit, logging, config) |
| `app/db/` | 2 | Database schema DDL and connection diagnostic test |
| `app/ingestion/` | 5 | Ingestion pipeline, multi-format loaders, sliding chunker, embedding client |
| `app/retrieval/` | 1 | Permission-constrained pgvector retriever and background security monitor |
| `app/generation/` | 1 | Structured evidence-grounded answer generation and abstention guardrails |
| `app/evaluation/` | 2 | RAG evaluation benchmark datasets, runners, and metrics computation |
| `app/observability/` | 2 | Operational latency tracking, p95 aggregation, and health event routes |
| `frontend/src/` | 17 | React components (8 UI views), styling (8 CSS files), and entry points |
| `frontend/public/` & `assets/` | 5 | SVGs, Hero illustrations, and application favicons |
| `frontend/` (config) | 6 | Vite config, package definitions, lockfile, linter rules, local envs |
| `migrations/` | 2 | Database migration scripts (001 Auth Sessions, 002 HNSW Index) |
| `scripts/` | 10 | Administrative CLI tools (user creation, password setting, similarity tests) |
| `tests/` | 6 | Automated test suites (Auth, Ingestion, Documents, Retrieval, Answer, Audit) |
| `data/sample_documents/` | 3 | Sample evaluation and test documents (`.docx`, `.md`) |
| Root files | 9 | Project Readme, Improvement Plan, Requirements, SQL dumps, environment configs |
| `.pytest_cache/` | 5 | Pytest internal cache metadata |

---

### 4.2 Comprehensive File-by-File Catalog

```
enterprise-knowledge-copilot/
├── .dev-unauthorized-token
├── .env
├── .env.example
├── .gitignore
├── README.md
├── improvement_plan.md
├── knowledge_copilot_before_security_migration.sql
├── requirements.txt
├── security_migration.sql
├── app/
│   ├── api/
│   │   ├── auth_routes.py
│   │   └── main.py
│   ├── core/
│   │   ├── audit.py
│   │   ├── auth.py
│   │   ├── config.py
│   │   ├── db.py
│   │   ├── db_pool.py
│   │   ├── logging_config.py
│   │   └── passwords.py
│   ├── db/
│   │   ├── schema.sql
│   │   └── test_connection.py
│   ├── evaluation/
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── generation/
│   │   └── answer.py
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── chunking.py
│   │   ├── embeddings.py
│   │   ├── loaders.py
│   │   └── pipeline.py
│   ├── observability/
│   │   ├── __init__.py
│   │   └── routes.py
│   └── retrieval/
│       └── retriever.py
├── data/
│   └── sample_documents/
│       ├── IES_Assignment_2_BTech_AIDS_7th_Sem (1).docx
│       ├── markdown_test.md
│       └── security_policy.md
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   └── src/
│       ├── App.css
│       ├── App.jsx
│       ├── Evaluation.css
│       ├── Evaluation.jsx
│       ├── KnowledgeBase.css
│       ├── KnowledgeBase.jsx
│       ├── Login.css
│       ├── Login.jsx
│       ├── Observability.css
│       ├── Observability.jsx
│       ├── SecurityActivity.css
│       ├── SecurityActivity.jsx
│       ├── Settings.css
│       ├── Settings.jsx
│       ├── Workplace.css
│       ├── Workplace.jsx
│       └── main.jsx
├── migrations/
│   ├── 001_auth_sessions.sql
│   └── 002_hnsw_index.sql
├── scripts/
│   ├── create_dev_user.py
│   ├── fix_cafeteria_embedding.py
│   ├── run_answer_demo.py
│   ├── run_retriever_demo.py
│   ├── set_user_password.py
│   ├── test_chunking.py
│   ├── test_embeddings.py
│   ├── test_ingestion_pipeline.py
│   ├── test_loader.py
│   ├── test_similarity_search.py
│   └── test_vector_storage.py
└── tests/
    ├── test_answer.py
    ├── test_api_auth.py
    ├── test_api_documents.py
    ├── test_audit.py
    ├── test_ingestion.py
    └── test_retriever.py
```

#### Detailed File Descriptions

| Relative Path | Size | Lines | Functional Description |
| :--- | :---: | :---: | :--- |
| **`app/api/main.py`** | 20.2 KB | 679 | Main FastAPI application entry point. Defines CORS rules, `/health`, `/api/v1/ask` question answering, `/api/v1/documents/upload` with owner verification and read permission binding, `/api/v1/documents` list, `/api/v1/documents/{id}` deletion with chunk cleanup, and `/api/v1/audit-events` query endpoint. |
| **`app/api/auth_routes.py`** | 12.0 KB | 402 | Authentication router (`/api/v1/auth`). Implements `/register` (employee self-registration), `/login` (credential check, 8-hour cookie session creation, CSRF token generation), `/me` (session verification), and `/logout` (CSRF verification, session revocation from DB, cookie deletion). |
| **`app/core/db_pool.py`** | 1.2 KB | 48 | High-performance multi-threaded connection pooling using `psycopg_pool.ConnectionPool`. Exposes `get_connection()` context manager to eliminate connection creation latency during vector retrieval. |
| **`app/core/auth.py`** | 5.6 KB | 195 | Authentication dependency `authenticate_user`. Extracts identity from either HTTP-only cookie (`kc_session`) or Bearer token header (`Authorization: Bearer <token>`). Verifies active state in `app_users` and session expiration in `user_sessions`. Provides `hash_token()`. |
| **`app/core/passwords.py`** | 1.6 KB | 59 | Cryptographic password management. Implements `hash_password()` using PBKDF2 with HMAC-SHA256 and 100,000 iterations plus unique 16-byte salt; implements `verify_password()` using constant-time comparison `secrets.compare_digest`. |
| **`app/core/audit.py`** | 1.1 KB | 41 | Central security audit logger `log_audit_event()`. Writes structured security events to `audit_logs` table (`event_type`, `principal_id`, `outcome`, `details` JSONB). Handles failures gracefully without breaking caller execution. |
| **`app/core/config.py`** | 437 B | 22 | Centralized environment variable loader using `python-dotenv`. Loads `DATABASE_URL`, `OLLAMA_BASE_URL`, `EMBEDDING_MODEL` (default: `nomic-embed-text`), and `EMBEDDING_DIMENSION` (768). |
| **`app/core/logging_config.py`** | 1.9 KB | 61 | Structured logging configuration setting up unified formatters, log levels, and console handlers. |
| **`app/core/db.py`** | 332 B | 13 | Legacy direct database connection helper returning `psycopg.connect(DATABASE_URL)`. |
| **`app/db/schema.sql`** | 3.4 KB | 107 | Complete database schema definition: enables `vector` extension, creates `documents`, `document_chunks`, `document_permissions`, `app_users`, `audit_logs`, and establishes the HNSW cosine vector index. |
| **`app/db/test_connection.py`** | 484 B | 19 | Standalone diagnostic script to verify PostgreSQL database reachability and version. |
| **`app/retrieval/retriever.py`** | 5.2 KB | 178 | Core similarity search engine `retrieve_chunks()`. Generates query embedding, queries `document_chunks` joined with `document_permissions` on `principal_id` and `permission='read'`, ordered by cosine distance `<=>`. Spawns background thread `_check_restricted_documents()` to detect unreadable content probes. |
| **`app/generation/answer.py`** | 7.7 KB | 297 | Evidence-grounded response generator `generate_answer()`. Coordinates retrieval, context assembly (`[Source X]`), prompt engineering with anti-hallucination rules, calls Ollama `/api/chat` with structured format schema, validates citations, and enforces abstention. |
| **`app/ingestion/pipeline.py`** | 3.4 KB | 105 | End-to-end ingestion pipeline `ingest_document()`. Computes document SHA-256 hash, inserts `documents` record in `processing` state, loads text via `load_document()`, chunks text via `chunk_text()`, generates embeddings, inserts into `document_chunks`, and marks document as `indexed`. |
| **`app/ingestion/loaders.py`** | 2.6 KB | 97 | Universal document loaders for `.pdf` (`pypdf`), `.docx` (`python-docx`), `.md`, and `.txt` files with UTF-8 decoding and fallback error handling. |
| **`app/ingestion/chunking.py`** | 1.5 KB | 66 | Sliding-window text chunker `chunk_text()`. Divides raw text into overlapping word windows (default: 300 words with 50-word overlap) and embeds metadata (source path, chunk index). |
| **`app/ingestion/embeddings.py`** | 755 B | 34 | Ollama embedding interface `create_embedding()`. Sends text to `/api/embeddings` endpoint using `nomic-embed-text` and returns a 768-float vector. |
| **`app/observability/routes.py`** | 10.1 KB | 313 | Observability API router (`/api/v1/observability`). Automatically provisions `observability_events` table using advisory locks. Exposes `/summary` (24-hour metrics: total requests, error count, p95 latency, event breakdown) and `/events` (paginated event log). |
| **`app/evaluation/routes.py`** | 16.9 KB | 595 | Evaluation API router (`/api/v1/evaluation`). Automatically provisions `evaluation_cases` and `evaluation_runs`. Implements case management (CRUD), evaluation runner (`POST /run`), metrics calculation (groundedness, recall, latency, abstention accuracy), and run history inspection. |
| **`frontend/src/App.jsx`** | 28.6 KB | 979 | Main frontend application container. Implements navigation sidebar, responsive mobile menu drawer, multi-theme selector (Light, Midnight, Emerald, Amethyst), interactive Copilot chat view, prompt suggestions, top-k slider, source citation display, and session header. |
| **`frontend/src/App.css`** | 27.1 KB | 1731 | Styling for App layout, sidebar, drawer, header, chat message bubbles, source drawer, prompt suggestion cards, and theme variables. |
| **`frontend/src/KnowledgeBase.jsx`**| 29.4 KB | 784 | Knowledge Base document management interface. Drag-and-drop file upload, file type validation, document list with chunk counts and status badges, document deletion, and permission revocation dialog. |
| **`frontend/src/KnowledgeBase.css`** | 23.9 KB | 1220 | Comprehensive styles for Knowledge Base tables, dropzones, upload progress bars, and modal dialogues. |
| **`frontend/src/Workplace.jsx`** | 16.4 KB | 449 | Workplace document discovery and exploratory search interface. Allows searching across accessible documents, reading chunk contents, and viewing metadata. |
| **`frontend/src/Workplace.css`** | 21.3 KB | 991 | Workplace styles for document grids, preview panels, and chunk cards. |
| **`frontend/src/Evaluation.jsx`** | 28.6 KB | 676 | RAG Evaluation benchmark interface. Allows creating golden QA test cases, running test suites against current retrieval/generation pipelines, visualizing aggregate metrics, and drilling into individual run case results. |
| **`frontend/src/Evaluation.css`** | 18.0 KB | 888 | Styling for evaluation dashboard metrics cards, progress bars, run tables, and score pills. |
| **`frontend/src/Observability.jsx`** | 16.4 KB | 383 | Operational observability dashboard. Visualizes 24h event counts, server errors, p95 latency, event type distribution badges, and paginated event logs with JSON payload inspection. |
| **`frontend/src/Observability.css`** | 14.7 KB | 733 | Observability metrics grid, latency status badges, and expandable event table styles. |
| **`frontend/src/SecurityActivity.jsx`**| 28.4 KB | 771 | Security audit event dashboard. Displays chronological audit trail from `audit_logs`, event filters (success/failure/denied), security alert banners for restricted document similarity probes. |
| **`frontend/src/SecurityActivity.css`**| 13.6 KB | 681 | Audit log table styles, outcome badges (green, red, amber), and detail inspection modal styles. |
| **`frontend/src/Settings.jsx`** | 11.4 KB | 328 | System settings and diagnostic panel. Displays Ollama connection status, active generation model (`qwen3:4b`), embedding model (`nomic-embed-text`), PostgreSQL status, and active user profile details. |
| **`frontend/src/Settings.css`** | 13.8 KB | 602 | Settings card layouts, toggle switches, and connection indicator lights. |
| **`frontend/src/Login.jsx`** | 11.1 KB | 316 | Authentication portal view. Supports dual tab switching between Sign In and Register Account, form validation, error banners, and CSRF token initialization. |
| **`frontend/src/Login.css`** | 7.0 KB | 349 | Glassmorphism login card, branded background, and smooth form transition styling. |
| **`migrations/001_auth_sessions.sql`**| 763 B | 27 | SQL migration adding `password_hash` column to `app_users` and creating the `user_sessions` table with indexes. |
| **`migrations/002_hnsw_index.sql`** | 389 B | 8 | SQL migration creating the HNSW index on `document_chunks.embedding` using `vector_cosine_ops`. |
| **`security_migration.sql`** | 608 B | 25 | Database migration adding `owner_principal_id` to `documents` and enforcing a composite unique constraint `(owner_principal_id, content_hash)` for tenant isolation. |
| **`scripts/create_dev_user.py`** | 1.2 KB | 47 | CLI script to generate a new developer principal ID, generate a secure random API token, and store its SHA-256 hash in `app_users`. |
| **`scripts/set_user_password.py`** | 1.6 KB | 63 | CLI script to set or reset a PBKDF2-hashed password for any employee in `app_users`. |
| **`scripts/run_answer_demo.py`** | 1.0 KB | 41 | Terminal CLI demo to execute `generate_answer()` with timing and formatted output. |
| **`scripts/run_retriever_demo.py`** | 751 B | 33 | Terminal CLI demo to test vector retrieval directly for a query and principal ID. |
| **`scripts/test_similarity_search.py`**| 1.4 KB | 51 | Diagnostic script testing raw pgvector cosine distance calculations between chunks. |
| **`scripts/test_vector_storage.py`** | 2.2 KB | 75 | Diagnostic script inspecting pgvector tables, chunk distributions, and vector dimensionality. |
| **`tests/test_answer.py`** | 7.2 KB | 210 | Unit test suite (6 tests) for `generate_answer()`: valid answer flow, abstention on low evidence, citation cleanup, model failure recovery, and empty query rejection. |
| **`tests/test_api_auth.py`** | 4.2 KB | 138 | Integration tests for API authentication: valid bearer token, missing token, invalid token, inactive account rejection. |
| **`tests/test_api_documents.py`** | 4.8 KB | 178 | Integration tests for document management APIs: upload validation, extension rejection, owner listing, and deletion cascade. |
| **`tests/test_audit.py`** | 2.4 KB | 75 | Unit tests for audit logging: event persistence, error resilience, details JSON formatting. |
| **`tests/test_ingestion.py`** | 8.9 KB | 312 | Unit tests for loaders (PDF, DOCX, TXT, MD), chunking overlaps, embedding generation, and duplicate file handling. |
| **`tests/test_retriever.py`** | 3.4 KB | 105 | Unit tests for vector retrieval: permission boundary enforcement, unauthorized document exclusion, and restricted document probing. |

---

## 5. Database Architecture & Schema Specification

The database is built on PostgreSQL with the `pgvector` extension enabled.

```
                           +----------------------+
                           |      app_users       |
                           |----------------------|
                      +--->| principal_id (PK)    |<---+
                      |    | password_hash        |    |
                      |    | token_hash (UQ)      |    |
                      |    | is_active            |    |
                      |    | created_at           |    |
                      |    +----------------------+    |
                      |               |                |
                      |               v                |
                      |    +----------------------+    |
                      |    |    user_sessions     |    |
                      |    |----------------------|    |
                      |    | session_token_hash PK|    |
                      |    | principal_id (FK)----+    |
                      |    | csrf_token_hash      |    |
                      |    | expires_at           |    |
                      |    +----------------------+    |
                      |                                |
                      |                                |
+---------------------+    +----------------------+    |
|      documents      |    | document_permissions |    |
|---------------------|    |----------------------|    |
| id (PK)             |<---| document_id (FK)     |    |
| filename            |    | principal_id --------+----+
| content_hash        |    | permission ('read')  |
| owner_principal_id--+    | created_at           |
| status              |    +----------------------+
| created_at          |
+---------------------+
           |
           v
+------------------------------------+
|          document_chunks           |
|------------------------------------|
| id (PK)                            |
| document_id (FK -> documents.id)   |
| chunk_index                        |
| content (TEXT)                     |
| embedding (VECTOR(768))            |  <-- HNSW Index (Cosine)
| metadata (JSONB)                   |
| created_at                         |
+------------------------------------+

+------------------------------------+     +------------------------------------+
|             audit_logs             |     |        observability_events        |
|------------------------------------|     |------------------------------------|
| id (PK)                            |     | id (PK)                            |
| event_type (TEXT)                  |     | principal_id (TEXT)                |
| principal_id (TEXT)                |     | event_type (TEXT)                  |
| outcome ('success'|'failure'|...)  |     | severity ('INFO'|'WARNING'|'ERROR')|
| details (JSONB)                    |     | duration_ms (DOUBLE PRECISION)     |
| created_at (TIMESTAMPTZ)           |     | status_code (INTEGER)              |
+------------------------------------+     | details (JSONB)                    |
                                           | created_at (TIMESTAMPTZ)           |
+------------------------------------+     +------------------------------------+
|          evaluation_cases          |
|------------------------------------|     +------------------------------------+
| id (PK)                            |     |          evaluation_runs           |
| principal_id (TEXT)                |     |------------------------------------|
| question (TEXT)                    |     | id (PK)                            |
| expected_answer (TEXT)             |     | principal_id (TEXT)                |
| expected_document_ids (INTEGER[])  |     | metrics (JSONB)                    |
| created_at (TIMESTAMPTZ)           |     | results (JSONB)                    |
+------------------------------------+     | created_at (TIMESTAMPTZ)           |
                                           +------------------------------------+
```

### Table Details:
1. **`documents`**: Tracks uploaded documents, their processing status (`pending`, `processing`, `indexed`, `failed`), and owner identity (`owner_principal_id`). Has composite unique constraint `(owner_principal_id, content_hash)` allowing distinct users to upload identical files without conflict.
2. **`document_chunks`**: Stores sliced text chunks and their 768-dimensional `vector` embeddings. Cascades on document deletion. Indexed with an HNSW cosine index `idx_chunks_embedding_hnsw` (`m = 16, ef_construction = 64`).
3. **`document_permissions`**: Maps document read permissions to specific `principal_id` strings. Primary key is `(document_id, principal_id)`.
4. **`app_users`**: Stores user identities, SHA-256 hashed API tokens, PBKDF2 hashed passwords, and active account flags.
5. **`user_sessions`**: Stores active web sessions, SHA-256 session token hashes, CSRF token hashes, and expiration timestamps.
6. **`audit_logs`**: Append-only log of security-sensitive operations (authentication, logout, document deletion, restricted document similarity detections).
7. **`observability_events`**: Stores execution durations, HTTP status codes, severity levels, and operation metadata for APM monitoring.
8. **`evaluation_cases`**: Golden dataset of benchmark questions, ground-truth answers, and expected document IDs.
9. **`evaluation_runs`**: Historical evaluation executions, storing aggregate metrics (mean duration, groundedness, recall, abstention rate) and per-case results.

---

## 6. REST API Specification

### Authentication & Sessions (`/api/v1/auth`)
- **`POST /api/v1/auth/register`**: Register a new user (`principal_id`, `password` $\ge 12$ chars).
- **`POST /api/v1/auth/login`**: Authenticate using username and password; sets `kc_session` (HTTP-only) and `kc_csrf` cookies.
- **`GET /api/v1/auth/me`**: Return current authenticated employee profile and session expiry.
- **`POST /api/v1/auth/logout`**: Revoke active session from database and clear cookies (requires `X-CSRF-Token` header).

### Knowledge & Documents (`/api/v1/documents`)
- **`GET /api/v1/documents`**: List all indexed documents readable by the authenticated user, including chunk counts.
- **`POST /api/v1/documents/upload`**: Upload a new `.pdf`, `.docx`, `.md`, or `.txt` file (max 10 MB). Ingests, embeds, creates chunks, and assigns read permissions to the uploader.
- **`DELETE /api/v1/documents/{document_id}`**: Revoke the authenticated user's permission. If no other users have permission, deletes chunks and document record completely.

### Copilot Q&A (`/api/v1/ask`)
- **`POST /api/v1/ask`**:
  - Request: `{ "question": "string", "top_k": 5 }`
  - Response: `{ "answer": "...", "abstained": false, "sources": [...] }`
  - Enforces permission bounds, strict evidence grounding, citation verification, and abstention fallbacks.

### Security Audit (`/api/v1/audit-events`)
- **`GET /api/v1/audit-events?limit=50&offset=0`**: Retrieve paginated audit logs for the authenticated principal.

### Observability & Metrics (`/api/v1/observability`)
- **`GET /api/v1/observability/summary`**: Returns 24-hour operational statistics: total events, error count, warning count, 5xx count, average latency, p95 latency, and event breakdown.
- **`GET /api/v1/observability/events?limit=50&offset=0`**: Returns paginated operational events for the caller.

### RAG Evaluation Benchmark (`/api/v1/evaluation`)
- **`GET /api/v1/evaluation/cases`**: List all golden evaluation cases.
- **`POST /api/v1/evaluation/cases`**: Create an evaluation case (`question`, `expected_answer`, `expected_document_ids`).
- **`DELETE /api/v1/evaluation/cases/{case_id}`**: Delete an evaluation case.
- **`POST /api/v1/evaluation/run`**: Execute all evaluation cases against the active RAG pipeline and record metrics.
- **`GET /api/v1/evaluation/runs`**: List previous evaluation runs with summarized metrics.
- **`GET /api/v1/evaluation/runs/{run_id}`**: Retrieve detailed results and individual case breakdown for a run.

---

## 7. Frontend User Interface Architecture

The frontend is a modern Single Page Application (SPA) built with **React 19**, **Vite**, and **Lucide React**, structured into 8 modular views:

1. **Copilot Chat (`App.jsx`)**:
   - Conversational search interface with quick-start prompt suggestions.
   - Interactive `top_k` slider (1 to 10 context chunks).
   - Real-time generation with visual citations (`[Source 1]`, `[Source 2]`).
   - Grounded evidence side drawer displaying source file names, similarity distance scores, and chunk text.
   - Clear indicators when the model abstains due to missing permissions or insufficient evidence.
2. **Knowledge Base (`KnowledgeBase.jsx`)**:
   - File drag-and-drop upload zone supporting `.pdf`, `.docx`, `.txt`, and `.md`.
   - Real-time upload progress and ingestion status badges (`indexed`, `processing`, `failed`).
   - Document table showing document ID, file name, chunk count, date added, and deletion actions.
3. **Workplace Document Explorer (`Workplace.jsx`)**:
   - Full-text search and exploration across all authorized documents.
   - Document preview modal with chunk inspection.
4. **RAG Evaluation Suite (`Evaluation.jsx`)**:
   - Golden benchmark dataset editor.
   - One-click evaluation runner testing answer correctness, context recall, and latency.
   - Comparative scorecards and historical run comparison.
5. **Observability APM (`Observability.jsx`)**:
   - 24-hour sliding metrics cards (P95 Latency, Average Latency, Request Volume, Error Rate).
   - Frequency breakdown pills for event types (`rag_answer`, `rag_validation_error`, etc.).
   - Chronological event stream with JSON detail drawer.
6. **Security Activity (`SecurityActivity.jsx`)**:
   - Filterable security event log (`success`, `failure`, `denied`).
   - High-visibility warning banners when unreadable document probes occur.
7. **Settings & Health (`Settings.jsx`)**:
   - Live health status indicators for Ollama, PostgreSQL, and Embeddings.
   - Display of active generation model (`qwen3:4b`), embedding model (`nomic-embed-text`), and user profile.
8. **Authentication (`Login.jsx`)**:
   - Tabbed login and registration forms with validation and cookie session establishment.

### Theme Engine
Built-in instant theme switching with persistent storage in `localStorage`:
- **Light**: Clean, high-contrast corporate theme.
- **Midnight Blue**: Deep navy and dark slate modern dark mode.
- **Emerald**: Forest green and emerald compliance palette.
- **Amethyst**: Deep violet and dark indigo executive palette.

---

## 8. Development & Operational Guide

### 8.1 Prerequisites
- Python 3.11+
- Node.js 18+ and npm
- PostgreSQL 16 with the `pgvector` extension
- Ollama running locally (`http://localhost:11434`)
  - Pull models: `ollama pull qwen3:4b` and `ollama pull nomic-embed-text`

### 8.2 Environment Configuration (`.env`)
```dotenv
DATABASE_URL=postgresql://raguser:YOUR_PASSWORD@localhost:5432/knowledge_copilot
OLLAMA_BASE_URL=http://localhost:11434
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_DIMENSION=768
COOKIE_SECURE=false
```

### 8.3 Starting the Backend
```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.api.main:app --reload --host 127.0.0.1 --port 8000
```
- API Base: `http://127.0.0.1:8000`
- Interactive OpenAPI Docs: `http://127.0.0.1:8000/docs`

### 8.4 Starting the Frontend
```powershell
cd frontend
npm run dev
```
- Frontend Web App: `http://localhost:5173`

### 8.5 Running Automated Tests
```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

---

## 9. Current Verification Status & Maintenance Notes

### Test Suite Status
- **Total Test Files**: 6 ([test_answer.py](file:///c:/Users/Satyam%20Kumar/enterprise-knowledge-copilot/tests/test_answer.py), [test_api_auth.py](file:///c:/Users/Satyam%20Kumar/enterprise-knowledge-copilot/tests/test_api_auth.py), [test_api_documents.py](file:///c:/Users/Satyam%20Kumar/enterprise-knowledge-copilot/tests/test_api_documents.py), [test_audit.py](file:///c:/Users/Satyam%20Kumar/enterprise-knowledge-copilot/tests/test_audit.py), [test_ingestion.py](file:///c:/Users/Satyam%20Kumar/enterprise-knowledge-copilot/tests/test_ingestion.py), [test_retriever.py](file:///c:/Users/Satyam%20Kumar/enterprise-knowledge-copilot/tests/test_retriever.py)).
- **Total Automated Tests**: 26 tests.
- **Current Passing Tests**: **26 / 26 tests passing (100% success rate)**.
- **Phase 1 Verification**:
  - HNSW Index `idx_chunks_embedding_hnsw` active on PostgreSQL.
  - Connection pool active via [db_pool.py](file:///c:/Users/Satyam%20Kumar/enterprise-knowledge-copilot/app/core/db_pool.py) with `atexit` clean shutdown handler.
  - Vector SQL fetch latency benchmarked at **7ms – 27ms**.
  - All test patches synchronized with `get_connection()`.
