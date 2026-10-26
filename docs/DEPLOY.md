# Deployment & Infrastructure Guide

This guide details deployment architectures for the **Enterprise Knowledge & Compliance Copilot**, ranging from 1-command local Dockerization to cloud VPS and managed PaaS environments.

---

## Architecture Overview

```
                        ┌───────────────────────────────┐
                        │      Client Browser (SPA)     │
                        └───────────────┬───────────────┘
                                        │ HTTPS / Port 443
                                        ▼
                        ┌───────────────────────────────┐
                        │     Reverse Proxy / Caddy     │
                        │  • Automated Let's Encrypt    │
                        │  • Rate Limiting & SSL Term   │
                        └───────────────┬───────────────┘
                                        │ Port 8000
                                        ▼
                        ┌───────────────────────────────┐
                        │   FastAPI App (Container)    │
                        │  • Backend API & Ingestion    │
                        │  • Static SPA Distribution    │
                        └───────┬───────────────┬───────┘
            SQL / Port 5432     │               │ HTTP / Port 11434
                                ▼               ▼
            ┌───────────────────────┐   ┌───────────────────────┐
            │ PostgreSQL + pgvector │   │     Ollama Server     │
            │ • HNSW Vector Index   │   │ • nomic-embed-text    │
            │ • GIN FTS Index       │   │ • qwen3:4b (or Cloud) │
            └───────────────────────┘   └───────────────────────┘
```

---

## 1. Quick Start: Local Turnkey Dockerization

The entire stack (PostgreSQL with pgvector, auto-initialized schema, backend API, and compiled React SPA) can be launched in a single command.

### Prerequisites
- Docker & Docker Compose installed.
- [Ollama](https://ollama.ai) installed and running locally with models downloaded:
  ```bash
  ollama pull nomic-embed-text
  ollama pull qwen3:4b
  ollama pull qwen2.5-coder:1.5b
  ```

### Step 1: Launch Stack
```bash
docker compose up --build
```

### What Happens Automatically
1. **`postgres` container** starts `pgvector/pgvector:pg16` on port `5432`.
2. **`schema.sql`** is mounted into `/docker-entrypoint-initdb.d/` and executes immediately on first boot:
   - Enables `vector` extension.
   - Builds `documents`, `document_chunks`, and permission tables.
   - Initializes HNSW index (`m=16, ef_construction=64`) and GIN full-text search index.
3. **`app` container** compiles the frontend SPA via multi-stage Node 20 builder, packages Python 3.11 runtime, and exposes port `8000`.
4. The container communicates with your host Ollama via `host.docker.internal:11434`.

### Step 2: Access the Application
- Web UI & Copilot: `http://localhost:8000`
- Interactive OpenAPI Docs: `http://localhost:8000/docs`

---

## 2. Production VPS Deployment (Ubuntu / Debian / AWS EC2)

For production deployments on dedicated Linux hosts (e.g. Hetzner, DigitalOcean Droplet, AWS EC2):

### 1. Host Preparation
```bash
# Update and install Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# Install Ollama with GPU acceleration (NVIDIA CUDA or CPU)
curl -fsSL https://ollama.com/install.sh | sh
```

### 2. Configure Systemd for Ollama Residency
To prevent cold-model reload latency in production, configure Ollama environment variables:
```bash
sudo systemctl edit ollama.service
```
Add the following lines:
```ini
[Service]
Environment="OLLAMA_KEEP_ALIVE=30m"
Environment="OLLAMA_MAX_LOADED_MODELS=2"
Environment="OLLAMA_HOST=0.0.0.0:11434"
```
Restart Ollama:
```bash
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

### 3. Production Environment File (`.env`)
Create a production `.env` file on the server:
```ini
DATABASE_URL=postgresql://raguser:STRONG_PRODUCTION_PASSWORD@postgres:5432/knowledge_copilot
OLLAMA_BASE_URL=http://host.docker.internal:11434
EMBEDDING_MODEL=nomic-embed-text
GENERATION_MODEL=qwen3:4b
FAST_GENERATION_MODEL=qwen2.5-coder:1.5b
COOKIE_SECURE=true
SESSION_DURATION_HOURS=24
RERANKER_ENABLED=false
```

### 4. Reverse Proxy with Automated SSL (Caddy)
Create a `Caddyfile` for automated HTTPS:
```caddy
copilot.yourdomain.com {
    reverse_proxy localhost:8000
    
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        Referrer-Policy "strict-origin-when-cross-origin"
    }
}
```
Run Caddy:
```bash
sudo apt install -y caddy
sudo systemctl restart caddy
```

---

## 3. PaaS Cloud Deployment (Render / Railway)

If deploying to managed PaaS environments without self-hosted GPUs:

### Database (PostgreSQL + pgvector)
1. Provision a PostgreSQL instance supporting pgvector (e.g., [Supabase](https://supabase.com), [Neon](https://neon.tech), or Railway PostgreSQL).
2. Run the initialization script:
   ```bash
   psql "$DATABASE_URL" -f app/db/schema.sql
   ```

### Web Service
1. Connect your GitHub repository to Render or Railway.
2. Select **Docker** as the deployment runtime (uses the multi-stage `Dockerfile`).
3. Set environment variables:
   - `DATABASE_URL`: Connection string from your managed database.
   - `COOKIE_SECURE`: `true`.
   - `OLLAMA_BASE_URL`: URL to your hosted Ollama or OpenAI-compatible endpoint.

---

## 4. Hosted LLM / OpenAI-Compatible Cloud Toggle

In resource-constrained environments where hosting local LLMs is impractical, the copilot can route to hosted OpenAI-compatible APIs (e.g. vLLM, LiteLLM, Groq, Together AI, or OpenRouter):

```ini
# Route through a LiteLLM proxy or OpenAI-compatible server:
OLLAMA_BASE_URL=https://api.together.xyz/v1
# Or local LiteLLM gateway:
# OLLAMA_BASE_URL=http://litellm-proxy:4000
```

Since the application uses standard JSON REST payloads (`/api/chat` and `/api/embeddings`), pairing with LiteLLM translates calls between Ollama and OpenAI/Anthropic/Bedrock endpoints with zero backend code changes.

---

## 5. Maintenance & Operational Probes

### Health Checks
- API Status: `GET /docs` (Returns 200 OK)
- Model Residency Status: `GET /api/models` (Returns loaded memory models and VRAM footprint)

### Ingestion Verification
Seed documents into production from the command line:
```bash
docker compose exec app python eval/seed_eval_corpus.py
```

### Database Backup
```bash
docker compose exec postgres pg_dump -U raguser knowledge_copilot > backup_$(date +%Y%m%d).sql
```
