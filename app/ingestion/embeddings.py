from functools import lru_cache
import httpx

from app.core.config import (
    OLLAMA_BASE_URL,
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSION,
    OLLAMA_MAX_RETRIES,
    OLLAMA_BACKOFF_FACTOR,
    EMBEDDING_BATCH_SIZE,
    OLLAMA_KEEP_ALIVE,
)
from app.core.ollama_client import post_ollama
from app.core.retry import execute_with_retry


@lru_cache(maxsize=1024)
def _cached_create_embedding(text: str) -> tuple[float, ...]:
    """Internal LRU-cached embedding retrieval returning an immutable tuple."""
    payload = {
        "model": EMBEDDING_MODEL,
        "input": text,
        "keep_alive": OLLAMA_KEEP_ALIVE,
    }

    response = execute_with_retry(
        lambda: post_ollama(
            "/api/embed",
            payload,
            timeout=60.0,
            mock_target=httpx.post,
        ),
        max_retries=OLLAMA_MAX_RETRIES,
        backoff_factor=OLLAMA_BACKOFF_FACTOR,
        operation_name="Ollama single embedding",
    )

    embeddings = response.json().get("embeddings", [])
    if not embeddings:
        raise ValueError("Ollama returned an empty embeddings list.")

    embedding = embeddings[0]
    if len(embedding) != EMBEDDING_DIMENSION:
        raise ValueError(
            f"Expected {EMBEDDING_DIMENSION} dimensions, got {len(embedding)}"
        )

    return tuple(embedding)


def create_embedding(text: str) -> list[float]:
    """Generate an embedding vector for a single text input with retry support and LRU caching."""
    if not text or not text.strip():
        raise ValueError("Text cannot be empty.")

    clean_text = text.strip()
    return list(_cached_create_embedding(clean_text))


def clear_embedding_cache() -> None:
    """Clear in-memory LRU cache for embeddings."""
    _cached_create_embedding.cache_clear()


def get_embedding_cache_info():
    """Return LRU cache statistics."""
    return _cached_create_embedding.cache_info()


def create_embeddings_batch(
    texts: list[str],
    batch_size: int = EMBEDDING_BATCH_SIZE,
) -> list[list[float]]:
    """
    Generate embedding vectors for multiple texts in batches.
    Significantly reduces HTTP overhead during document ingestion.
    """
    if not texts:
        return []

    if batch_size <= 0:
        batch_size = 32

    # Validate all texts
    for index, text in enumerate(texts):
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"Text at index {index} cannot be empty.")

    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        payload = {
            "model": EMBEDDING_MODEL,
            "input": batch,
            "keep_alive": OLLAMA_KEEP_ALIVE,
        }

        response = execute_with_retry(
            lambda: post_ollama(
                "/api/embed",
                payload,
                timeout=120.0,
                mock_target=httpx.post,
            ),
            max_retries=OLLAMA_MAX_RETRIES,
            backoff_factor=OLLAMA_BACKOFF_FACTOR,
            operation_name=f"Ollama batch embedding ({len(batch)} items)",
        )

        batch_embeddings = response.json().get("embeddings", [])
        if len(batch_embeddings) != len(batch):
            raise ValueError(
                f"Expected {len(batch)} embeddings from Ollama, got {len(batch_embeddings)}"
            )

        for emb in batch_embeddings:
            if len(emb) != EMBEDDING_DIMENSION:
                raise ValueError(
                    f"Expected {EMBEDDING_DIMENSION} dimensions, got {len(emb)}"
                )
            all_embeddings.append(emb)

    return all_embeddings
