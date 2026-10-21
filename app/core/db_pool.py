
"""Shared database connection pool.

Every module that needs a database connection should import
``get_connection`` from this module instead of calling
``psycopg.connect()`` directly.  The context manager commits on
clean exit and rolls back on exception, matching the behaviour of
``psycopg.connect()`` used as a context manager.
"""

import atexit
from contextlib import contextmanager

from psycopg_pool import ConnectionPool

from app.core.config import DATABASE_URL


_pool: ConnectionPool | None = None


def _get_pool() -> ConnectionPool:
    """Return the shared pool, creating it on first use."""
    global _pool
    if _pool is None:
        _pool = ConnectionPool(
            DATABASE_URL,
            min_size=2,
            max_size=10,
            timeout=20,
            kwargs={"connect_timeout": 20},
        )
    return _pool


def close_pool() -> None:
    """Close all pooled connections cleanly before process exit."""
    global _pool
    if _pool is not None:
        try:
            _pool.close()
        except Exception:
            pass
        _pool = None


atexit.register(close_pool)


@contextmanager
def get_connection():
    """Borrow a connection from the pool.

    Commits on clean exit, rolls back on exception — the same
    behaviour as ``psycopg.connect()`` used as a context manager.
    """
    with _get_pool().connection() as conn:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
