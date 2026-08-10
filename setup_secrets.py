"""
One-time setup script: creates the Databricks secret scopes and stores the
TMDB access token and Lakebase URL. Run this locally (with the Databricks CLI configured) or
from a notebook - never commit the resulting secret values anywhere.

Usage:
    python setup_secrets.py
"""
from databricks.sdk import WorkspaceClient
from databricks.sdk.service import workspace
import getpass
import time

w = WorkspaceClient()

start_time = time.time()

try:
    w.secrets.create_scope(scope="movie-planner")
except Exception:
    pass  # Scope already exists

w.secrets.put_secret(
    scope="movie-planner",
    key="tmdb-access-token",
    string_value=getpass.getpass("Paste your TMDB access token: ")
)

try:
    w.secrets.create_scope(scope="database")
except Exception:
    pass  # Scope already exists

w.secrets.put_secret(
    scope="database",
    key="mcp-movie-lakebase-url",
    string_value=getpass.getpass("Paste your MCP Movie Planner Lakebase URL: ")
)

w.secrets.put_acl(
    scope="database",
    principal="users",
    permission=workspace.AclPermission.READ,
)

w.secrets.put_acl(
    scope="movie-planner",
    principal="users",
    permission=workspace.AclPermission.READ,
)

print(f"Setup completed in {time.time() - start_time:.2f} seconds.")