import json
import logging
import re
import time
from typing import Any

from app.core.config import (
    RERANKER_ENABLED,
    RERANKER_MODEL,
    RERANKER_TYPE,
)
from app.core.ollama_client import post_ollama

logger = logging.getLogger(__name__)

# Cached cross-encoder model instance if sentence_transformers is available
_CROSS_ENCODER_INSTANCE = None


def _get_cross_encoder():
    global _CROSS_ENCODER_INSTANCE
    if _CROSS_ENCODER_INSTANCE is None:
        try:
            from sentence_transformers import CrossEncoder

            _CROSS_ENCODER_INSTANCE = CrossEncoder(
                "cross-encoder/ms-marco-MiniLM-L-6-v2", max_length=512
            )
            logger.info("Initialized CrossEncoder: ms-marco-MiniLM-L-6-v2")
        except ImportError:
            logger.debug(
                "sentence_transformers not installed; cross-encoder unavailable."
            )
            return None
    return _CROSS_ENCODER_INSTANCE


def _score_with_ollama(query: str, chunks: list[dict[str, Any]]) -> list[float]:
    """Score candidate chunks against query using local Ollama fast model."""
    if not chunks:
        return []

    # Compact scoring prompt asking for integer relevance 0-10
    snippets = []
    for idx, c in enumerate(chunks):
        content = c.get("content", "")[:250].replace("\n", " ")
        snippets.append(f"[{idx}] {content}")
    
    prompt = (
        f"Query: {query}\n\n"
        "Score each candidate text on relevance to the query from 0 to 10.\n"
        "Return a JSON object: {\"scores\": [score_0, score_1, ...]}\n\n"
        "Candidates:\n" + "\n".join(snippets) + "\n\n"
        "JSON:"
    )

    try:
        response = post_ollama(
            "/api/generate",
            json_data={
                "model": RERANKER_MODEL,
                "prompt": prompt,
                "format": "json",
                "stream": False,
                "keep_alive": "10m",
                "options": {
                    "temperature": 0.0,
                    "num_predict": 100,
                },
            },
            timeout=10.0,
        )
        data = response.json()
        raw_text = data.get("response", "{}")
        # Strip <think> tags if present
        raw_text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()
        parsed = json.loads(raw_text)
        scores = parsed.get("scores", [])
        if isinstance(scores, list) and len(scores) == len(chunks):
            return [float(s) for s in scores]
    except Exception as exc:
        logger.warning("Ollama reranker scoring failed: %s; falling back to RRF rank.", exc)

    # Fallback to inverse index ranks
    return [float(len(chunks) - i) for i in range(len(chunks))]


def _score_with_heuristic(query: str, chunks: list[dict[str, Any]]) -> list[float]:
    """Fast lexical overlap and phrase proximity cross-scoring (0 latency overhead)."""
    q_tokens = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 2]
    scores = []
    for c in chunks:
        content = c.get("content", "").lower()
        score = 0.0
        # Token presence
        matches = sum(1 for t in q_tokens if t in content)
        score += (matches / max(1, len(q_tokens))) * 5.0
        # Exact substring / phrase bonus
        if query.lower() in content:
            score += 5.0
        # Distance bonus (from vector search if present)
        dist = c.get("distance")
        if dist is not None:
            score += max(0.0, (1.0 - dist) * 3.0)
        scores.append(score)
    return scores


def rerank_chunks(
    query: str,
    chunks: list[dict[str, Any]],
    top_k: int = 5,
    enabled: bool | None = None,
) -> list[dict[str, Any]]:
    """Rerank candidate chunks using cross-encoder, Ollama scoring, or lexical heuristic.
    
    If disabled (default), returns candidates sliced to top_k with 0ms overhead.
    """
    is_enabled = RERANKER_ENABLED if enabled is None else enabled

    if not is_enabled or not chunks:
        return chunks[:top_k]

    start_time = time.perf_counter()

    # Attempt 1: sentence_transformers CrossEncoder if configured/installed
    cross_enc = _get_cross_encoder() if RERANKER_TYPE == "cross_encoder" else None

    if cross_enc is not None:
        pairs = [(query, c.get("content", "")) for c in chunks]
        scores = cross_enc.predict(pairs).tolist()
    elif RERANKER_TYPE == "ollama":
        scores = _score_with_ollama(query, chunks)
    else:
        scores = _score_with_heuristic(query, chunks)

    # Pair chunks with scores
    scored_chunks = []
    for chunk, score in zip(chunks, scores):
        scored_chunk = dict(chunk)
        scored_chunk["rerank_score"] = round(float(score), 4)
        scored_chunks.append(scored_chunk)

    # Sort descending by rerank_score
    scored_chunks.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0
    logger.info(
        "Reranked %d candidates to top %d in %.2f ms (type=%s)",
        len(chunks),
        top_k,
        elapsed_ms,
        RERANKER_TYPE,
    )

    return scored_chunks[:top_k]
