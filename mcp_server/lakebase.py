"""
Lakebase (Databricks-managed Postgres) connection helper for Movie Planner.

Connects using LAKEBASE_URL from Databricks secrets - a standard Postgres 
connection URL pointing at a native Postgres role.
"""

import os
import base64
from contextlib import contextmanager

import psycopg2
from databricks.sdk import WorkspaceClient
from psycopg2.extras import RealDictCursor
from sqlalchemy import create_engine

_w = None  # Lazy-loaded WorkspaceClient

_SCOPE = os.environ.get("LAKEBASE_SECRET_SCOPE", "database")
_KEY = os.environ.get("LAKEBASE_SECRET_KEY", "mcp-movie-lakebase-url")


def _get_workspace_client():
    """Lazy-load the WorkspaceClient (only when secrets need to be fetched)."""
    global _w
    if _w is None:
        _w = WorkspaceClient()
    return _w


def _lakebase_url() -> str:
    """Fetch the Lakebase connection URL from the Databricks secret scope."""
    w = _get_workspace_client()
    secret = w.secrets.get_secret(scope=_SCOPE, key=_KEY)
    # Decode if base64 encoded (secret values are often base64 encoded)
    value = secret.value
    try:
        # Try to decode as base64
        decoded = base64.b64decode(value).decode('utf-8')
        # Check if it looks like a valid connection string
        if decoded.startswith('postgresql://') or decoded.startswith('postgres://'):
            return decoded
    except Exception:
        pass
    # Return as-is if not base64 encoded
    return value


@contextmanager
def get_connection():
    """Yield a raw psycopg2 connection with a RealDictCursor factory."""
    conn = psycopg2.connect(_lakebase_url(), cursor_factory=RealDictCursor)
    try:
        yield conn
    finally:
        conn.close()


def get_engine():
    """Return a SQLAlchemy engine for Lakebase."""
    return create_engine(_lakebase_url())


def run_query(sql: str, params: tuple | dict | None = None) -> list[dict]:
    """Run a read query against Lakebase and return rows as list[dict]."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            return cur.fetchall()


def run_write(sql: str, params: tuple | dict | None = None) -> int:
    """Run an INSERT/UPDATE/DELETE against Lakebase, return affected row count."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()
            return cur.rowcount
