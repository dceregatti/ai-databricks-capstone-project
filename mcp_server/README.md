# Movie Night Planner MCP Server

This MCP (Model Context Protocol) server exposes movie planning tools that can be used by Databricks Agents.

## 🎯 Features

* **search_movies** - Search movies by title with optional filters (genre, year)
* **get_movie_details** - Get detailed information about a specific movie
* **add_to_watchlist** - Add movies to a user's watchlist
* **get_user_watchlist** - Retrieve a user's watchlist
* **semantic_movie_search** - Natural language movie search using pgvector

## 🚀 Deploy as Databricks App

### Prerequisites

1. **Secrets configured** (via `setup_secrets.py`):
   * `movie-planner/tmdb-access-token` - TMDB Bearer token
   * `database/mcp-movie-lakebase-url` - Lakebase connection URL

2. **Database setup**:
   * Lakebase project, branch, and endpoint created
   * Schema initialized with tables: `users`, `movies`, `watchlist`, `movie_embeddings`

### Deploy

```bash
cd mcp_server
databricks apps create mcp-movie-planner
databricks apps deploy mcp-movie-planner --source-code-path .
```

### Get the App URL

```bash
databricks apps get mcp-movie-planner
```

The app will be available at: `https://<workspace>.cloud.databricks.com/apps/<app-id>`

## 🔧 Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables (or use Databricks secrets)
export LAKEBASE_SECRET_SCOPE=database
export LAKEBASE_SECRET_KEY=mcp-movie-lakebase-url
export TMDB_SECRET_SCOPE=movie-planner
export TMDB_SECRET_KEY=tmdb-access-token

# Run the server
python movie_mcp_server.py
```

Server will start on `http://0.0.0.0:8000`

## 📡 Connecting to an Agent

Once deployed, register this MCP server with your Databricks Agent:

1. Get your app URL from `databricks apps get mcp-movie-planner`
2. In Agent Bricks, add external MCP server with the URL
3. The agent can now call the movie planning tools

## 🔑 Port Configuration

The server runs on port **8000** by default (configured in `app.yaml`). This is the standard port for FastMCP apps on Databricks.

To change the port:
* Update `PORT` in `app.yaml`
* Or set the `PORT` environment variable

## 📚 API Documentation

Once running, FastMCP automatically provides:
* OpenAPI documentation at `/docs`
* MCP protocol endpoints for agent integration

## 🎬 Example Usage

```python
# Example agent conversation:
# User: "Find me a sci-fi movie under 2 hours"
# Agent calls: search_movies(query="sci-fi", ...)

# User: "Add Inception to my watchlist"
# Agent calls: add_to_watchlist(user_id=1, movie_id=27205)

# User: "What's in my watchlist?"
# Agent calls: get_user_watchlist(user_id=1)
```
