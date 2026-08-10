"""Database connection utilities for Movie Night Planner."""

from databricks.sdk import WorkspaceClient
import psycopg
from psycopg.rows import dict_row
import os
from typing import Optional


class DatabaseConnection:
    """Manages Lakebase Postgres database connections."""
    
    def __init__(self):
        self.w = WorkspaceClient()
        self.project_name = "projects/movie-night-planner"
        self.branch_name = f"{self.project_name}/branches/production"
        self.endpoint_name = f"{self.branch_name}/endpoints/primary"
        self._conn = None
    
    def get_connection(self):
        """Get a fresh database connection with current OAuth token."""
        # Get database info
        databases = list(self.w.postgres.list_databases(parent=self.branch_name))
        db_name = databases[0].name.split("/")[-1] if databases else "databricks_postgres"
        
        # Get endpoint and credentials
        endpoint = self.w.postgres.get_endpoint(name=self.endpoint_name)
        host = endpoint.status.hosts.host
        username = self.w.current_user.me().user_name
        token = self.w.postgres.generate_database_credential(endpoint=self.endpoint_name).token
        
        # Create connection with dict cursor for easier row access
        conn = psycopg.connect(
            host=host,
            dbname=db_name,
            user=username,
            password=token,
            sslmode="require",
            row_factory=dict_row
        )
        return conn
    
    def execute_query(self, query: str, params: Optional[tuple] = None, fetch: bool = True):
        """Execute a query and return results.
        
        Args:
            query: SQL query to execute
            params: Query parameters
            fetch: Whether to fetch results (False for INSERT/UPDATE/DELETE)
        
        Returns:
            Query results if fetch=True, None otherwise
        """
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(query, params)
                if fetch:
                    results = cur.fetchall()
                    return results
                else:
                    conn.commit()
                    return None
        finally:
            conn.close()
    
    def execute_many(self, query: str, params_list: list):
        """Execute a query multiple times with different parameters.
        
        Args:
            query: SQL query to execute
            params_list: List of parameter tuples
        """
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.executemany(query, params_list)
                conn.commit()
        finally:
            conn.close()
    
    def initialize_schema(self, schema_file: str = "../database/schema.sql"):
        """Initialize the database schema from SQL file.
        
        Args:
            schema_file: Path to SQL schema file
        """
        with open(schema_file, 'r') as f:
            schema_sql = f.read()
        
        conn = self.get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(schema_sql)
                conn.commit()
                print("✓ Database schema initialized successfully")
        finally:
            conn.close()