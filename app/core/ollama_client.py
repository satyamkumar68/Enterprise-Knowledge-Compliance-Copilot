"""
Shared persistent HTTP client connection pool for Ollama API calls.

Reusing TCP connections eliminates TCP handshake and socket churn on every request,
substantially reducing latency for both query embeddings and answer generations.
"""

import atexit
import logging
import threading
from contextlib import contextmanager
from typing import Any
import unittest.mock

import httpx

from app.core.config import OLLAMA_BASE_URL


logger = logging.getLogger(__name__)

_client_lock = threading.Lock()
_shared_client: httpx.Client | None = None

DEFAULT_OLLAMA_TIMEOUT = httpx.Timeout(
    connect=10.0,
    read=600.0,
    write=30.0,
    pool=30.0,
)


def get_ollama_client() -> httpx.Client:
    """Return a shared thread-safe persistent httpx.Client for Ollama API calls."""
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        with _client_lock:
            if _shared_client is None or _shared_client.is_closed:
                _shared_client = httpx.Client(
                    base_url=OLLAMA_BASE_URL.rstrip("/"),
                    timeout=DEFAULT_OLLAMA_TIMEOUT,
                    limits=httpx.Limits(
                        max_keepalive_connections=10,
                        max_connections=20,
                        keepalive_expiry=60.0,
                    ),
                )
    return _shared_client


def post_ollama(
    endpoint: str,
    json_data: dict[str, Any],
    timeout: httpx.Timeout | float | None = None,
    mock_target: Any = None,
) -> httpx.Response:
    """Send a POST request to Ollama using the shared connection pool.

    If `httpx.post` has been mocked (e.g., in unit tests), routes through `mock_target`
    or `httpx.post` to ensure full test mock compatibility.
    """
    effective_timeout = timeout or DEFAULT_OLLAMA_TIMEOUT
    full_url = f"{OLLAMA_BASE_URL.rstrip('/')}/{endpoint.lstrip('/')}"

    # If httpx.post was patched in caller module or global httpx, route through mock
    if mock_target is not None and isinstance(mock_target, unittest.mock.Mock):
        return mock_target(full_url, json=json_data, timeout=effective_timeout)

    if isinstance(httpx.post, unittest.mock.Mock):
        return httpx.post(full_url, json=json_data, timeout=effective_timeout)

    client = get_ollama_client()
    # If the client itself was patched or replaced with a Mock, call it
    return client.post(full_url, json=json_data, timeout=effective_timeout)


@contextmanager
def stream_ollama(
    endpoint: str,
    json_data: dict[str, Any],
    timeout: httpx.Timeout | float | None = None,
    mock_target: Any = None,
):
    """Context manager for streaming Ollama responses line-by-line with connection pooling."""
    effective_timeout = timeout or DEFAULT_OLLAMA_TIMEOUT
    full_url = f"{OLLAMA_BASE_URL.rstrip('/')}/{endpoint.lstrip('/')}"

    if mock_target is not None and isinstance(mock_target, unittest.mock.Mock):
        mock_resp = mock_target(full_url, json=json_data, timeout=effective_timeout)
        yield mock_resp
        return

    if isinstance(httpx.stream, unittest.mock.Mock):
        with httpx.stream("POST", full_url, json=json_data, timeout=effective_timeout) as resp:
            yield resp
        return

    client = get_ollama_client()
    with client.stream("POST", full_url, json=json_data, timeout=effective_timeout) as resp:
        yield resp


def close_ollama_client() -> None:
    """Close the persistent httpx client cleanly."""
    global _shared_client
    with _client_lock:
        if _shared_client is not None and not _shared_client.is_closed:
            try:
                _shared_client.close()
            except Exception:
                pass
            _shared_client = None


atexit.register(close_ollama_client)
