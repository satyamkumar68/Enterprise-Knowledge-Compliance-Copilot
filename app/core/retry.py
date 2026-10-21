import logging
import time
from typing import Callable, TypeVar

import httpx

logger = logging.getLogger(__name__)

T = TypeVar("T")

TRANSIENT_STATUS_CODES = {408, 429, 500, 502, 503, 504}


def is_transient_error(exc: Exception) -> bool:
    """Determine if an exception is transient and safe to retry."""
    if isinstance(exc, (httpx.TransportError, ConnectionError, TimeoutError)):
        return True

    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in TRANSIENT_STATUS_CODES

    return False


def execute_with_retry(
    fn: Callable[[], T],
    max_retries: int = 3,
    backoff_factor: float = 0.5,
    operation_name: str = "HTTP request",
) -> T:
    """Execute a callable with exponential backoff for transient failures."""
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            result = fn()
            if hasattr(result, "raise_for_status"):
                result.raise_for_status()
            return result
        except Exception as exc:
            last_error = exc
            if attempt >= max_retries or not is_transient_error(exc):
                raise

            delay = backoff_factor * (2 ** attempt)
            logger.warning(
                f"[RETRY] {operation_name} failed with {type(exc).__name__}: {exc}. "
                f"Retrying in {delay:.2f}s (attempt {attempt + 1}/{max_retries})..."
            )
            time.sleep(delay)

    if last_error:
        raise last_error
    raise RuntimeError(f"{operation_name} failed with no result.")
