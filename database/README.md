# Database Schema

## IMPORTANT: Schema Consolidation

The authoritative database schema is now **`../mcp_server/schema.sql`**.

This directory's `schema.sql` has been renamed to `schema.sql.deprecated` to prevent accidental use.

## Why the Change?

The original `database/schema.sql` had several issues:
- Used `movie_id` as PRIMARY KEY (which was actually the TMDB ID)
- Stored embeddings directly in the movies table
- Less organized structure
- Conflicting with the MCP server schema

The MCP server schema (`../mcp_server/schema.sql`) is better designed:
- Uses proper `id` (SERIAL) as PRIMARY KEY
- Separate `tmdb_id` field for TMDB references
- Dedicated `movie_embeddings` table for semantic search
- Cleaner foreign key relationships
- Better indexing strategy

## For New Deployments

Run the schema from the MCP server directory:
```bash
psql <connection_string> < ../mcp_server/schema.sql
```

Or use the setup script in `../mcp_server/setup_database.py`.
