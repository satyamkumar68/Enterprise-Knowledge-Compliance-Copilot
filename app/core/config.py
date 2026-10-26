
import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://localhost:11434",
)
EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "nomic-embed-text",
)
EMBEDDING_DIMENSION = int(
    os.getenv("EMBEDDING_DIMENSION", "768")
)
RELEVANCE_THRESHOLD = float(
    os.getenv("RELEVANCE_THRESHOLD", "0.50")
)
ENABLE_QUERY_REWRITING = os.getenv(
    "ENABLE_QUERY_REWRITING", "false"
).lower() in ("true", "1", "yes")
GENERATION_MODEL = os.getenv(
    "GENERATION_MODEL",
    "qwen3:4b",
)
GENERATION_NUM_PREDICT = int(
    os.getenv("GENERATION_NUM_PREDICT", "200")
)
DEFAULT_TOP_K = int(
    os.getenv("DEFAULT_TOP_K", "3")
)
OLLAMA_MAX_RETRIES = int(
    os.getenv("OLLAMA_MAX_RETRIES", "3")
)
OLLAMA_BACKOFF_FACTOR = float(
    os.getenv("OLLAMA_BACKOFF_FACTOR", "0.5")
)
EMBEDDING_BATCH_SIZE = int(
    os.getenv("EMBEDDING_BATCH_SIZE", "32")
)

# Runtime and memory performance settings (Phase 8)
OLLAMA_KEEP_ALIVE = os.getenv("OLLAMA_KEEP_ALIVE", "30m")
OLLAMA_MAX_LOADED_MODELS = int(os.getenv("OLLAMA_MAX_LOADED_MODELS", "2"))
FAST_GENERATION_MODEL = os.getenv("FAST_GENERATION_MODEL", "qwen2.5-coder:1.5b")
MODEL_PROFILE = os.getenv("MODEL_PROFILE", "standard")

# Optional cross-encoder / second-stage reranker (Phase 5)
RERANKER_ENABLED = os.getenv("RERANKER_ENABLED", "false").lower() in ("true", "1", "yes")
RERANKER_TYPE = os.getenv("RERANKER_TYPE", "heuristic")  # "heuristic", "ollama", or "cross_encoder"
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "qwen2.5-coder:1.5b")


if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not configured.")
