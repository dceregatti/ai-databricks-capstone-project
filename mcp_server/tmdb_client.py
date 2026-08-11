"""TMDB API client using Bearer token authentication with retry logic."""

import os
import time
import logging
import requests
from databricks.sdk import WorkspaceClient

logger = logging.getLogger(__name__)

_w = None  # Lazy-loaded WorkspaceClient

_TMDB_SCOPE = os.environ.get("TMDB_SECRET_SCOPE", "movie-planner")
_TMDB_KEY = os.environ.get("TMDB_SECRET_KEY", "tmdb-access-token")

BASE_URL = "https://api.themoviedb.org/3"

# Retry configuration for rate limiting
MAX_RETRIES = 3
BASE_BACKOFF = 1.0  # seconds


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
    """Make authenticated request to TMDB API using Bearer token with exponential backoff retry.
    
    Automatically retries on rate limit (HTTP 429) errors with exponential backoff.
    
    Args:
        endpoint: API endpoint path (e.g., '/movie/popular')
        params: Optional query parameters
    
    Returns:
        JSON response as dictionary
    
    Raises:
        requests.HTTPError: If request fails after all retries
    """
    url = f"{BASE_URL}{endpoint}"
    headers = {
        "Authorization": f"Bearer {_get_access_token()}",
        "accept": "application/json"
    }
    
    last_exception = None
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.get(url, headers=headers, params=params or {}, timeout=10)
            
            # Handle rate limiting with exponential backoff
            if response.status_code == 429:
                if attempt < MAX_RETRIES - 1:
                    # Calculate backoff: 1s, 2s, 4s
                    backoff = BASE_BACKOFF * (2 ** attempt)
                    logger.warning(f"TMDB rate limit hit (429). Retrying in {backoff}s... (attempt {attempt + 1}/{MAX_RETRIES})")
                    time.sleep(backoff)
                    continue
                else:
                    logger.error(f"TMDB rate limit hit. Max retries ({MAX_RETRIES}) exceeded.")
            
            # Raise for other HTTP errors
            response.raise_for_status()
            return response.json()
            
        except requests.RequestException as e:
            last_exception = e
            if attempt < MAX_RETRIES - 1:
                backoff = BASE_BACKOFF * (2 ** attempt)
                logger.warning(f"TMDB request failed: {e}. Retrying in {backoff}s... (attempt {attempt + 1}/{MAX_RETRIES})")
                time.sleep(backoff)
            else:
                logger.error(f"TMDB request failed after {MAX_RETRIES} attempts: {e}")
    
    # If we get here, all retries failed
    raise last_exception or requests.HTTPError("TMDB request failed after all retries")


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


def get_movie_credits(movie_id: int) -> dict:
    """Get cast and crew information for a movie.
    
    Args:
        movie_id: TMDB movie ID
    
    Returns:
        Dictionary with 'cast' and 'crew' lists
    """
    return _make_request(f"/movie/{movie_id}/credits")


def get_movie_keywords(movie_id: int) -> dict:
    """Get keywords associated with a movie.
    
    Args:
        movie_id: TMDB movie ID
    
    Returns:
        Dictionary with 'keywords' list
    """
    return _make_request(f"/movie/{movie_id}/keywords")


def get_movie_videos(movie_id: int) -> dict:
    """Get videos (trailers, teasers) for a movie.
    
    Args:
        movie_id: TMDB movie ID
    
    Returns:
        Dictionary with 'results' list of videos
    """
    return _make_request(f"/movie/{movie_id}/videos")
