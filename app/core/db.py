
"""Database connection utilities.

The application currently uses direct psycopg connections while
connection-pool initialization is being investigated.
"""

from app.core.config import DATABASE_URL


def get_database_url() -> str:
    """Return the configured PostgreSQL connection string."""
    return DATABASE_URL
