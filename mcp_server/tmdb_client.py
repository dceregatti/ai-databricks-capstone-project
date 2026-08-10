"""TMDB API client using Bearer token authentication."""

import os
import requests
from databricks.sdk import WorkspaceClient

_w = None  # Lazy-loaded WorkspaceClient

_TMDB_SCOPE = os.environ.get("TMDB_SECRET_SCOPE", "movie-planner")
_TMDB_KEY = os.environ.get("TMDB_SECRET_KEY", "tmdb-access-token")

BASE_URL = "https://api.themoviedb.org/3"


def _get_workspace_client():
    """Lazy-load the WorkspaceClient (only when secrets need to be fetched)."""
    global _w
    if _w is None:
        _w = WorkspaceClient()
    return _w


def _get_access_token() -> str:
    """Fetch TMDB access token from Databricks secrets."""
    w = _get_workspace_client()
    secret = w.secrets.get_secret(scope=_TMDB_SCOPE, key=_TMDB_KEY)
    return secret.value


def _make_request(endpoint: str, params: dict = None) -> dict:
    """Make authenticated request to TMDB API using Bearer token."""
    url = f"{BASE_URL}{endpoint}"
    headers = {
        "Authorization": f"Bearer {_get_access_token()}",
        "accept": "application/json"
    }
    response = requests.get(url, headers=headers, params=params or {})
    response.raise_for_status()
    return response.json()


def search_movies(query: str, page: int = 1) -> dict:
    """Search for movies by title."""
    return _make_request("/search/movie", {"query": query, "page": page})


def get_movie_details(movie_id: int) -> dict:
    """Get detailed information about a specific movie."""
    return _make_request(f"/movie/{movie_id}")


def get_popular_movies(page: int = 1) -> dict:
    """Get popular movies."""
    return _make_request("/movie/popular", {"page": page})


def get_movie_recommendations(movie_id: int, page: int = 1) -> dict:
    """Get movie recommendations based on a movie."""
    return _make_request(f"/movie/{movie_id}/recommendations", {"page": page})


def discover_movies(params: dict = None) -> dict:
    """Discover movies with filters (genre, year, etc.)."""
    return _make_request("/discover/movie", params or {})
