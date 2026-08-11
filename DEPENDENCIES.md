# Project Dependencies

The authoritative requirements file is:

**➡️ `mcp_server/requirements.txt`**

This file is used by:
* `mcp_server/app.yaml` for Databricks App deployment
* All jobs in `jobs/` directory
* Integration tests in `tests/` directory

## Installation

```bash
pip install -r mcp_server/requirements.txt
```

## Key Dependencies

### Core
* `databricks-sdk` - Databricks SDK for secrets and workspace access
* `psycopg2-binary` - PostgreSQL adapter (Lakebase)
* `sqlalchemy` - SQL toolkit and ORM

### MCP Server
* `fastmcp` - Model Context Protocol server framework
* `fastapi` - Web framework
* `uvicorn` - ASGI server
* `pydantic` - Data validation

### External APIs
* `requests` - HTTP client (TMDB API)
* `tenacity` - Retry/backoff logic

### Machine Learning
* `sentence-transformers` - Semantic embeddings

### Development
* `python-dotenv` - Environment variable management
* `ipython` - Interactive shell

## Deprecated Files

* `requirements.txt.deprecated` - Old root requirements (consolidated into mcp_server/requirements.txt)
