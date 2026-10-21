# Enterprise Knowledge & Compliance Copilot

[![Python](https://img.shields.io/badge/Python-3.11%20%7C%203.14-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.143.0-009688.svg)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19.0-61DAFB.svg)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-8.3.4-646CFF.svg)](https://vitejs.dev/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16%20%2B%20pgvector-336791.svg)](https://github.com/pgvector/pgvector)
[![Ollama](https://img.shields.io/badge/Ollama-Local%20Inference-black.svg)](https://ollama.com/)
[![Tests](https://img.shields.io/badge/Unit%20Tests-46%2F46%20Passing-brightgreen.svg)]()
[![Latency](https://img.shields.io/badge/TTFT-~2.0s%20(86%25%20Faster)-success.svg)]()

An enterprise-grade, evidence-based question-answering system (RAG) that enforces strict document-level read permissions, prevents hallucinations via mathematical evidence grounding, streams real-time responses through Server-Sent Events (SSE), and runs 100% locally with zero cloud dependencies or external API fees.

---

## Table of Contents

1. [Key Features & Capabilities](#key-features--capabilities)
2. [System Architecture](#system-architecture)
3. [Project Directory Structure](#project-directory-structure)
4. [Prerequisites](#prerequisites)
5. [Quick Start Guide](#quick-start-guide)
   - [1. Database Setup (Docker + pgvector)](#1-database-setup-docker--pgvector)
   - [2. Local LLM Setup (Ollama)](#2-local-llm-setup-ollama)
   - [3. Backend Setup](#3-backend-setup)
   - [4. Create Development Users](#4-create-development-users)
   - [5. Frontend Setup](#5-frontend-setup)
6. [Configuration Reference (`.env`)](#configuration-reference-env)
7. [API Reference](#api-reference)
8. [Performance & Latency Optimization](#performance--latency-optimization)
9. [Automated Testing & Quality Verification](#automated-testing--quality-verification)
10. [Security & Compliance Architecture](#security--compliance-architecture)
11. [Troubleshooting & FAQs](#troubleshooting--faqs)

---

## Key Features & Capabilities

- 🛡️ **Role-Based Document Access Control (RBAC)**: Enforces permission boundaries at the PostgreSQL vector query layer. Unauthorized documents are mathematically excluded from distance calculations and LLM prompts.
- 🎯 **Evidence-Grounded Answers & Anti-Hallucination**:
  - The model only answers when authorized evidence directly supports the claim.
  - Automatically abstains with a standardized message when evidence is insufficient or missing.
  - Generates transparent, verifiable inline citations (`[Source X]`) linked directly to document chunks.
- ⚡ **Real-Time Streaming Architecture (Server-Sent Events)**:
  - Cuts perceived latency (Time-to-First-Token) from 17.7s to **~2.0s – 2.5s** (an **86% reduction**).
  - Progressive typewriter rendering with instantaneous candidate source preview pills within 2.58s.
- 🎛️ **Dual-Model Profiles (Phase 8)**:
  - **🎯 Standard Profile (`qwen3:4b`)**: Comprehensive analytical precision for complex compliance policies.
  - **⚡ Fast Profile (`qwen2.5-coder:1.5b`)**: ~2× faster generation for quick factual lookups and developer queries.
  - Switchable on-the-fly via interactive toggle pill buttons in the web UI.
- 🚀 **High-Performance Hybrid Search**:
  - Dense semantic retrieval via **pgvector HNSW** indexing (`m=16, ef_construction=64`).
  - Sparse lexical search via PostgreSQL `tsvector` with **GIN indexing**.
  - Merged via **Reciprocal Rank Fusion (RRF)** for optimal recall and ranking.
- 🧠 **Smart Memory Management & Caching**:
  - Thread-safe **in-memory LRU Embedding Cache** (`maxsize=1024`) serving repeat queries in `< 1ms` (>99% speedup).
  - **Ollama Memory Keep-Alive (`30m`)** and non-blocking background model pre-warming during server startup.
  - Multi-model concurrency configuration preventing VRAM model thrashing.
  - Database connection pooling (`psycopg-pool`) eliminating TCP handshake churn.
- 🖥️ **Full-Featured React 19 Frontend**:
  - Conversational AI Assistant with real-time typewriter streaming.
  - **Knowledge Base**: Drag-and-drop document upload (PDF, DOCX, Markdown, TXT) and document permission management.
  - **Evaluation Dashboard**: Visual SVG gauges, per-case latency distributions, side-by-side run comparisons, answer diff highlighting, and one-click JSON/CSV export.
  - **Observability Hub**: Real-time operational event tracking, error telemetry, and performance percentiles.
  - **Security & Activity**: Audit trail logs for all logins, document permissions, and queries.
  - Elegant Light and Dark themes with smooth micro-animations.

---

## System Architecture

```mermaid
graph TD
    User["User / Web Browser<br/>(React 19 + Vite)"]
    
    subgraph FastAPI_Backend ["FastAPI Backend (port 8000)"]
        Auth["Session & CSRF Auth<br/>(Argon2 / SHA-256)"]
        StreamAPI["POST /api/v1/ask/stream<br/>(Server-Sent Events)"]
        SyncAPI["POST /api/v1/ask"]
        Cache["LRU Embedding Cache<br/>(1024 entries, <1ms)"]
        Pool["psycopg Connection Pool<br/>(2-10 connections)"]
        Parser["Streaming JSON Parser<br/>(Regex Fallback + Guardrails)"]
    end
    
    subgraph Data_Storage ["PostgreSQL 16 + pgvector (Docker)"]
        Chunks["document_chunks<br/>(HNSW Vector Index)"]
        TSV["Full-Text tsvector<br/>(GIN Index)"]
        Perms["document_permissions<br/>(Principal RBAC)"]
        Audit["audit_logs & observability_events"]
    end
    
    subgraph Local_Inference ["Local Ollama Service (port 11434)"]
        Embedder["nomic-embed-text<br/>(768 dimensions)"]
        StdGen["qwen3:4b<br/>(Standard Profile)"]
        FastGen["qwen2.5-coder:1.5b<br/>(Fast Profile)"]
    end
    
    User -->|HTTP / SSE| Auth
    Auth --> StreamAPI
    Auth --> SyncAPI
    StreamAPI & SyncAPI --> Cache
    Cache -->|Cache Miss| Embedder
    Cache -->|Query Vector| Pool
    Pool -->|Hybrid RRF Query| Chunks
    Pool -->|Keyword Match| TSV
    Pool -->|Filter Permitted| Perms
    Chunks & TSV --> Parser
    Parser -->|Generate Answer| StdGen
    Parser -->|Generate Fast| FastGen
    Parser -->|Token Stream / Chunks| User
```

---

## Project Directory Structure

```text
enterprise-knowledge-copilot/
├── app/
│   ├── api/
│   │   ├── main.py                  # FastAPI application, routes, lifespan & health checks
│   │   └── auth_routes.py           # Session login, logout, me, and CSRF token endpoints
│   ├── core/
│   │   ├── audit.py                 # Structured security audit logging
│   │   ├── auth.py                  # API token hashing, session management, and auth filters
│   │   ├── config.py                # Centralized environment variable loader and defaults
│   │   ├── db_pool.py               # psycopg connection pool with graceful cleanup
│   │   ├── ollama_client.py         # Shared persistent httpx connection pool for Ollama
│   │   └── retry.py                 # Resilient retry with exponential backoff and jitter
│   ├── db/
│   │   └── schema.sql               # Unified database schema, HNSW indexes, GIN indexes, and tables
│   ├── evaluation/
│   │   ├── benchmark_cases.py       # Ground-truth test datasets for retrieval and answer evaluation
│   │   └── routes.py                # Benchmark execution, metric calculation, and comparison routes
│   ├── generation/
│   │   └── answer.py                # Dual-model RAG generator, streaming parser, and citation validator
│   ├── ingestion/
│   │   ├── chunking.py              # Overlapping sentence/character chunker with contextual headers
│   │   ├── embeddings.py            # Single & batch embedding creation with LRU caching
│   │   ├── loaders.py               # Document loaders for PDF, DOCX, Markdown, and TXT
│   │   └── pipeline.py              # Ingestion pipeline coordinating loaders, chunkers, and DB writes
│   ├── observability/
│   │   └── routes.py                # Telemetry event ingestion, latency percentiles, and metrics
│   └── retrieval/
│       ├── query_rewriter.py        # LLM query expansion and reformulator
│       └── retriever.py             # Hybrid RRF retriever, permission filters, and relevance checks
├── frontend/
│   ├── src/
│   │   ├── App.jsx                  # Main application container, live streaming chat, model toggle
│   │   ├── App.css                  # Modern design system, themes, animations, responsive layout
│   │   ├── Evaluation.jsx           # Interactive benchmark UI with SVG charts & run comparison
│   │   ├── Evaluation.css           # Styling for evaluation charts, diff views, and cards
│   │   ├── KnowledgeBase.jsx        # Document upload, table listing, and deletion interface
│   │   ├── Observability.jsx        # Operational metrics, telemetry events, and latency percentiles
│   │   ├── SecurityActivity.jsx     # Audit log viewer and security activity monitor
│   │   ├── Settings.jsx             # System configurations and session inspector
│   │   ├── Workplace.jsx            # Enterprise workplace overview and quick actions
│   │   └── Login.jsx                # Secure login screen
│   ├── package.json                 # Frontend dependencies (React 19, Lucide icons, Vite)
│   └── vite.config.js               # Vite build and dev server configuration
├── tests/                           # 75 automated backend tests (100% pass rate)
│   ├── test_answer.py               # Answer generation and citation formatting tests
│   ├── test_api_auth.py             # Authentication and authorization endpoint tests
│   ├── test_api_documents.py        # Document upload, listing, and permission tests
│   ├── test_audit.py                # Security audit logging tests
│   ├── test_bugfixes.py             # Regression tests for initial bug discoveries
│   ├── test_chunking_quality.py     # Chunk overlap and contextual header tests
│   ├── test_ingestion.py            # Document parsing and embedding pipeline tests
│   ├── test_phase3.py               # Confidence scoring and structured sources tests
│   ├── test_phase5.py               # Lifespan, health check, and timeout middleware tests
│   ├── test_phase6.py               # LRU cache, fast JSON mode, and connection pool tests
│   ├── test_phase7.py               # Server-Sent Events (SSE) streaming and parser tests
│   ├── test_phase8.py               # Model keep-alive, residency, and fast profile tests
│   ├── test_query_rewriter.py       # Query rewriting and fallback tests
│   └── test_retriever.py            # Hybrid RRF and permission boundary tests
├── scripts/
│   ├── create_dev_user.py           # CLI tool to create users and generate API tokens
│   ├── set_user_password.py         # CLI tool to configure username/password for session auth
│   ├── run_answer_demo.py           # Interactive CLI question answering verification script
│   └── run_retriever_demo.py        # Interactive CLI retrieval verification script
├── data/
│   └── sample_documents/            # Sample enterprise security and compliance documents
├── improvement_plan.md              # Living engineering plan, bug reports, and benchmark metrics
├── requirements.txt                 # Pinned Python backend dependencies
└── README.md                        # Project documentation (this file)
```

---

## Prerequisites

Ensure your system meets the following requirements:

| Component | Minimum Requirement | Recommended |
|---|---|---|
| **Operating System** | Windows 10/11, Ubuntu 22.04+, macOS 12+ | Windows 11 / Ubuntu 22.04 LTS |
| **RAM** | 8 GB System Memory | 16 GB+ |
| **Python** | Python 3.11+ | Python 3.11, 3.12, 3.13, or 3.14 |
| **Node.js** | Node.js v18.0+ | Node.js v20 LTS / v22 |
| **Docker** | Docker Desktop (with Compose) | Latest Docker Desktop |
| **Ollama** | Latest Ollama installer | Version 0.3.0+ |

---

## Quick Start Guide

### 1. Database Setup (Docker + pgvector)

Start a PostgreSQL 16 container with the `pgvector` extension installed:

```powershell
docker run -d `
  --name rag-postgres `
  -e POSTGRES_USER=raguser `
  -e POSTGRES_PASSWORD=ragpassword `
  -e POSTGRES_DB=knowledge_copilot `
  -p 5432:5432 `
  pgvector/pgvector:pg16
```

Initialize the database schema, tables, and vector indexes:

```powershell
# Copy the unified schema into the container and apply it:
docker cp app/db/schema.sql rag-postgres:/tmp/schema.sql
docker exec -i rag-postgres psql -U raguser -d knowledge_copilot -f /tmp/schema.sql
```

---

### 2. Local LLM Setup (Ollama)

1. Download and install [Ollama](https://ollama.com/).
2. Pull the required models:

```powershell
# 1. Embedding Model (768-dim vectors)
ollama pull nomic-embed-text

# 2. Standard Generation Model (4B parameters, deep compliance precision)
ollama pull qwen3:4b

# 3. Fast Generation Model (1.5B parameters, rapid lookups)
ollama pull qwen2.5-coder:1.5b
```

3. **Multi-Model Residency Configuration (Critical for Performance)**:
   By default, Ollama unloads models when switching between embeddings and generation. To keep all models concurrent in memory without thrashing, configure `OLLAMA_MAX_LOADED_MODELS`:
   - **Windows PowerShell**:
     ```powershell
     $env:OLLAMA_MAX_LOADED_MODELS="2"
     $env:OLLAMA_KEEP_ALIVE="30m"
     ollama serve
     ```
   - **Linux / macOS**:
     ```bash
     OLLAMA_MAX_LOADED_MODELS=2 OLLAMA_KEEP_ALIVE=30m ollama serve
     ```

---

### 3. Backend Setup

1. Open PowerShell / terminal in the project root:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1   # On Linux/macOS: source .venv/bin/activate
   ```

2. Install Python dependencies:
   ```powershell
   python -m pip install --upgrade pip
   python -m pip install -r requirements.txt
   ```

3. Configure your local `.env` file (copy from `.env.example`):
   ```powershell
   Copy-Item .env.example .env
   ```
   Ensure `DATABASE_URL` matches your PostgreSQL configuration:
   ```dotenv
   DATABASE_URL=postgresql://raguser:ragpassword@localhost:5432/knowledge_copilot
   OLLAMA_BASE_URL=http://localhost:11434
   EMBEDDING_MODEL=nomic-embed-text
   EMBEDDING_DIMENSION=768
   GENERATION_MODEL=qwen3:4b
   FAST_GENERATION_MODEL=qwen2.5-coder:1.5b
   OLLAMA_KEEP_ALIVE=30m
   OLLAMA_MAX_LOADED_MODELS=2
   ```

---

### 4. Create Development Users

Create an authorized enterprise employee and an unauthorized user for testing permission boundaries:

```powershell
# 1. Create primary employee
python scripts/create_dev_user.py employee-001

# 2. Set password for Web UI session login
python scripts/set_user_password.py employee-001 password123

# 3. Create unauthorized user for RBAC testing
python scripts/create_dev_user.py employee-unauthorized
python scripts/set_user_password.py employee-unauthorized password123
```

Now, ingest sample documents into the system:

```powershell
python -c "from app.ingestion.pipeline import ingest_document; ingest_document('data/sample_documents/security_policy.md', owner_principal_id='employee-001')"
```

---

### 5. Frontend Setup

1. In a new terminal window, navigate to the `frontend/` directory:
   ```powershell
   cd frontend
   npm install
   ```

2. Start the Vite development server:
   ```powershell
   npm run dev
   ```

3. In your initial backend terminal, start the FastAPI API server:
   ```powershell
   uvicorn app.api.main:app --reload --port 8000
   ```

4. Open your browser:
   - **Frontend UI**: [http://localhost:5173](http://localhost:5173) (Sign in with `employee-001` / `password123`)
   - **Interactive API Swagger**: [http://localhost:8000/docs](http://localhost:8000/docs)
   - **System Health Diagnostics**: [http://localhost:8000/health](http://localhost:8000/health)

---

## Configuration Reference (`.env`)

| Variable | Type | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | String | *Required* | PostgreSQL connection URI (`postgresql://user:pass@host:5432/dbname`) |
| `OLLAMA_BASE_URL` | String | `http://localhost:11434` | Base URL of local Ollama inference service |
| `EMBEDDING_MODEL` | String | `nomic-embed-text` | Dense vector embedding model name in Ollama |
| `EMBEDDING_DIMENSION` | Integer | `768` | Vector dimensions produced by embedding model |
| `GENERATION_MODEL` | String | `qwen3:4b` | Default standard generator model (high analytical depth) |
| `FAST_GENERATION_MODEL`| String | `qwen2.5-coder:1.5b` | Optional lightweight generator profile (~2× faster) |
| `MODEL_PROFILE` | String | `standard` | Default active model profile (`standard` or `fast`) |
| `GENERATION_NUM_PREDICT`| Integer | `200` | Max tokens generated by LLM (capped to reduce trailing latency) |
| `DEFAULT_TOP_K` | Integer | `3` | Default number of chunks retrieved per question |
| `RELEVANCE_THRESHOLD` | Float | `0.50` | Maximum cosine distance filter for chunk retrieval |
| `ENABLE_QUERY_REWRITING`| Boolean | `false` | Enable LLM query expansion before vector search |
| `OLLAMA_KEEP_ALIVE` | String | `30m` | Time to keep models resident in RAM/VRAM after inactivity |
| `OLLAMA_MAX_LOADED_MODELS`| Integer | `2` | Number of models kept concurrent in Ollama without eviction |
| `EMBEDDING_BATCH_SIZE`| Integer | `32` | Number of chunks sent per HTTP batch during document ingestion |
| `OLLAMA_MAX_RETRIES` | Integer | `3` | Max automatic retries for transient Ollama connection timeouts |
| `REQUEST_TIMEOUT_SECONDS`| Float | `120.0` | Global async HTTP request timeout before returning 504 |

---

## API Reference

Interactive OpenAPI documentation is available live at `http://localhost:8000/docs`.

### Core Endpoints

#### 1. Ask Question (Real-Time SSE Streaming)
`POST /api/v1/ask/stream`  
*Streams answer tokens progressively with Server-Sent Events (SSE).*

- **Headers**: `Accept: text/event-stream`, `X-CSRF-Token: <token>`, `Cookie: session_token=...`
- **Body**:
  ```json
  {
    "question": "What is the policy on database access?",
    "top_k": 3,
    "model_profile": "standard"
  }
  ```
- **Events Emitted**:
  - `event: start` — Emitted immediately after vector retrieval with candidate sources (`model`, `sources`).
  - `event: token` — Emitted token-by-token as generated by Ollama (`token`).
  - `event: done` — Emitted on completion with verified citations, clean answer, confidence score, and abstention flag.

---

#### 2. Ask Question (Synchronous JSON)
`POST /api/v1/ask`  
*Returns a single structured JSON response with citations.*

- **Response**:
  ```json
  {
    "answer": "Production database access requires approval from your manager. [Source 1]",
    "clean_answer": "Production database access requires approval from your manager.",
    "abstained": false,
    "confidence_score": 0.88,
    "average_distance": 0.12,
    "model": "qwen3:4b",
    "sources": [
      {
        "source_id": 1,
        "document_id": 4,
        "chunk_index": 0,
        "filename": "security_policy.md",
        "content": "Production database access requires manager approval...",
        "distance": 0.12,
        "citation_tag": "[Source 1]"
      }
    ]
  }
  ```

---

#### 3. Health & Model Residency Diagnostics
`GET /health`  
*Verifies database connectivity, Ollama status, and active models currently loaded in RAM/VRAM.*

- **Response**:
  ```json
  {
    "status": "ok",
    "ollama": {
      "connected": true,
      "base_url": "http://localhost:11434",
      "embedding_model": "nomic-embed-text",
      "generation_model": "qwen3:4b",
      "fast_generation_model": "qwen2.5-coder:1.5b",
      "embedding_model_available": true,
      "generation_model_available": true,
      "fast_generation_model_available": true,
      "loaded_models": ["qwen3:4b", "qwen2.5-coder:1.5b", "nomic-embed-text:latest"],
      "multi_model_ready": true,
      "keep_alive": "30m"
    }
  }
  ```

---

#### 4. Document Management
- `POST /api/v1/documents/upload` — Upload and ingest PDF, DOCX, Markdown, or TXT file with automatic chunking and embedding.
- `GET /api/v1/documents` — List authorized documents accessible by the authenticated user.
- `DELETE /api/v1/documents/{document_id}` — Delete a document and all associated vector chunks.

---

#### 5. Session Authentication
- `POST /api/v1/auth/login` — Authenticate with username and password; sets secure `HttpOnly` session cookie and returns CSRF token.
- `POST /api/v1/auth/logout` — Invalidate active session token.
- `GET /api/v1/auth/me` — Return current authenticated principal ID.

---

## Performance & Latency Optimization

To achieve sub-second perceived response times while running locally on consumer hardware, this project implemented an extensive 3-phase latency engineering overhaul:

### Benchmark Progression

| Metric | Original Baseline | Phase 6 (Quick Wins) | Phase 7 (Streaming UI) | Phase 8 (Keep-Alive & Fast Profile) | Total Speedup |
|---|:---:|:---:|:---:|:---:|:---:|
| **Time-to-First-Token (TTFT)** | 17.70s | 4.63s (cached) / 14.7s | **~2.80s** | **~2.00s – 2.50s** | **86% – 88% faster** |
| **Raw Generation Time** | 15.80s | 4.60s (cached) / 12.5s | 4.60s – 12.5s | **3.53s – 5.41s** | **66% – 78% faster** |
| **Total Pipeline Time** | 17.70s | 4.63s | 4.63s | **4.37s** | **75.3% faster** |
| **Repeat / Cached Queries** | 17.70s | 4.63s | < 1.0s TTFT | **0.013s (13ms)** retrieval | **>99% faster** |

### Key Optimizations Implemented:
1. **Fast JSON Mode**: Replaced rigid GBNF grammar compilation in Ollama with native JSON mode and regex-based streaming parsing, eliminating token-by-token state machine validation overhead.
2. **HNSW Vector Indexing**: Replaced O(n) sequential table scans with pgvector HNSW indexing, reducing vector retrieval from ~400ms to 7–15ms.
3. **In-Memory LRU Cache**: Thread-safe cache (`maxsize=1024`) for query embeddings, allowing common or repeated questions to bypass embedding generation entirely (<1ms vs ~2.5s).
4. **Shared Persistent Connection Pools**: Implemented persistent HTTP connection pooling (`httpx.Client`) and PostgreSQL pooling (`psycopg_pool.ConnectionPool`), cutting TCP handshake latency across all operations.
5. **Context Prefill Reduction**: Tuned default retrieval `top_k` from 5 to 3 for standard queries, reducing prompt token prefill overhead by ~40% with zero recall degradation.
6. **Multi-Model Residency & Keep-Alive (`30m`)**: Keeps both embedder and generator resident in memory simultaneously (`OLLAMA_MAX_LOADED_MODELS=2`), eliminating cold-start reload penalties.

---

## Automated Testing & Quality Verification

The test suite covers the entire RAG pipeline, authentication, permission boundaries, streaming, and caching:

```powershell
# Run the complete test suite (46 tests):
.venv\Scripts\python.exe -m pytest -v
```

```text
======================= 46 passed, 1 warning in 11.53s ========================
```

### Frontend Code Quality & Production Build:

```powershell
# Run frontend linter (oxlint):
npm --prefix frontend run lint

# Verify clean production bundle build:
npm --prefix frontend run build
```

---

## Security & Compliance Architecture

- **Defense-in-Depth Authorization**: The retriever explicitly joins `document_permissions` on `principal_id`, guaranteeing that unauthorized chunks are never fetched or fed to the LLM.
- **Credential & Secret Protection**: API tokens and session tokens are hashed using SHA-256 before storage in PostgreSQL. Raw tokens are never logged or persisted.
- **CSRF & Cookie Hardening**: Browser sessions use `HttpOnly`, `SameSite=Lax` cookies coupled with `X-CSRF-Token` header verification on mutating requests.
- **Zero Cloud Leakage**: All inference (embeddings, query rewriting, and answer generation) executes strictly on local hardware via Ollama. No proprietary documents or questions ever leave the enterprise network.
- **Audit Trails**: Every login, authorization attempt, and query is logged to `audit_logs` with timestamps, outcomes, and principal IDs.

---

## Troubleshooting & FAQs

### 1. `Ollama service at http://localhost:11434 is not reachable`
- Confirm that Ollama is installed and running (`ollama list`).
- On Windows, verify that the Ollama taskbar tray icon is visible, or run `ollama serve` in a terminal.

### 2. `Expected 768 dimensions, got ...`
- The database schema is configured for `VECTOR(768)` matching `nomic-embed-text`.
- If using an alternate embedding model, update `EMBEDDING_DIMENSION` in `.env` and recreate the column in PostgreSQL.

### 3. Model Thrashing or High First-Token Latency (~15-18s)
- Ensure Ollama was started with `OLLAMA_MAX_LOADED_MODELS=2`:
  ```powershell
  $env:OLLAMA_MAX_LOADED_MODELS="2"
  ollama serve
  ```
- Check `http://localhost:8000/health` to confirm `"multi_model_ready": true`.

### 4. Database Connection Refused (`localhost:5432`)
- Ensure the Docker container is active: `docker ps`.
- If stopped, start it with `docker start rag-postgres`.

---

## License

This project is licensed under the Apache 2.0 License. Designed and engineered for secure enterprise knowledge retrieval and compliance.
