"""TMDB API client for fetching movie data."""

import requests
import os
import json
from typing import List, Dict, Optional
from datetime import datetime


class TMDBClient:
    """Client for interacting with The Movie Database (TMDB) API using Bearer token authentication."""
    
    BASE_URL = "https://api.themoviedb.org/3"
    IMAGE_BASE_URL = "https://image.tmdb.org/t/p/w500"
    
    def __init__(self, access_token: Optional[str] = None):
        """Initialize TMDB client.
        
        Args:
            access_token: TMDB Bearer access token. If not provided, reads from Databricks secrets or env var.
        """
        if access_token:
            self.access_token = access_token
        else:
            # Try Databricks secrets first
            try:
                from databricks.sdk import WorkspaceClient
                w = WorkspaceClient()
                self.access_token = w.secrets.get_secret(scope="movie-planner", key="tmdb-access-token").value
            except Exception:
                # Fallback to environment variable for local development
                self.access_token = os.getenv("TMDB_ACCESS_TOKEN")
        
        if not self.access_token:
            raise ValueError(
                "TMDB access token not provided. Either:\n"
                "  1. Run setup_secrets.py to store in Databricks secrets, or\n"
                "  2. Set TMDB_ACCESS_TOKEN environment variable for local development"
            )
    
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """Make a request to TMDB API using Bearer token authentication.
        
        Args:
            endpoint: API endpoint (e.g., '/movie/popular')
            params: Additional query parameters
        
        Returns:
            JSON response as dictionary
        """
        url = f"{self.BASE_URL}{endpoint}"
        params = params or {}
        
        # Use Bearer token authentication (more secure than API key in URL)
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "accept": "application/json"
        }
        
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()
    
    def search_movies(self, query: str, page: int = 1) -> List[Dict]:
        """Search for movies by title.
        
        Args:
            query: Search query
            page: Page number for pagination
        
        Returns:
            List of movie dictionaries
        """
        data = self._make_request("/search/movie", {"query": query, "page": page})
        return data.get("results", [])
    
    def get_movie_details(self, movie_id: int) -> Dict:
        """Get detailed information about a movie.
        
        Args:
            movie_id: TMDB movie ID
        
        Returns:
            Movie details dictionary
        """
        return self._make_request(f"/movie/{movie_id}")
    
    def get_movie_credits(self, movie_id: int) -> Dict:
        """Get cast and crew information for a movie.
        
        Args:
            movie_id: TMDB movie ID
        
        Returns:
            Dictionary with 'cast' and 'crew' lists
        """
        return self._make_request(f"/movie/{movie_id}/credits")
    
    def get_movie_keywords(self, movie_id: int) -> List[Dict]:
        """Get keywords associated with a movie.
        
        Args:
            movie_id: TMDB movie ID
        
        Returns:
            List of keyword dictionaries
        """
        data = self._make_request(f"/movie/{movie_id}/keywords")
        return data.get("keywords", [])
    
    def get_movie_videos(self, movie_id: int) -> List[Dict]:
        """Get videos (trailers, teasers) for a movie.
        
        Args:
            movie_id: TMDB movie ID
        
        Returns:
            List of video dictionaries
        """
        data = self._make_request(f"/movie/{movie_id}/videos")
        return data.get("results", [])
    
    def get_movie_watch_providers(self, movie_id: int) -> Dict:
        """Get streaming/watch provider information for a movie.
        
        Args:
            movie_id: TMDB movie ID
        
        Returns:
            Dictionary of watch providers by region
        """
        data = self._make_request(f"/movie/{movie_id}/watch/providers")
        return data.get("results", {})
    
    def get_popular_movies(self, page: int = 1) -> List[Dict]:
        """Get popular movies.
        
        Args:
            page: Page number for pagination
        
        Returns:
            List of movie dictionaries
        """
        data = self._make_request("/movie/popular", {"page": page})
        return data.get("results", [])
    
    def get_top_rated_movies(self, page: int = 1) -> List[Dict]:
        """Get top rated movies.
        
        Args:
            page: Page number for pagination
        
        Returns:
            List of movie dictionaries
        """
        data = self._make_request("/movie/top_rated", {"page": page})
        return data.get("results", [])
    
    def discover_movies(self, **kwargs) -> List[Dict]:
        """Discover movies based on various filters.
        
        Args:
            **kwargs: Filter parameters (genre, year, rating, etc.)
                     See TMDB API docs for available filters.
        
        Returns:
            List of movie dictionaries
        """
        data = self._make_request("/discover/movie", kwargs)
        return data.get("results", [])
    
    def get_complete_movie_data(self, movie_id: int) -> Dict:
        """Get complete movie data including details, cast, keywords, etc.
        
        Args:
            movie_id: TMDB movie ID
        
        Returns:
            Complete movie data dictionary
        """
        # Get basic details
        movie = self.get_movie_details(movie_id)
        
        # Add credits (cast)
        credits = self.get_movie_credits(movie_id)
        movie["cast_info"] = credits.get("cast", [])[:10]  # Top 10 cast members
        
        # Add keywords
        keywords = self.get_movie_keywords(movie_id)
        movie["keywords"] = keywords
        
        # Add videos (trailers)
        videos = self.get_movie_videos(movie_id)
        # Find YouTube trailer
        trailer = next(
            (v for v in videos if v.get("type") == "Trailer" and v.get("site") == "YouTube"),
            None
        )
        movie["trailer_url"] = f"https://www.youtube.com/watch?v={trailer['key']}" if trailer else None
        
        # Add watch providers
        movie["streaming_providers"] = self.get_movie_watch_providers(movie_id)
        
        return movie
    
    def format_for_database(self, movie_data: Dict) -> Dict:
        """Format movie data for database insertion.
        
        Args:
            movie_data: Raw movie data from TMDB
        
        Returns:
            Formatted dictionary ready for database insertion
        """
        return {
            "movie_id": movie_data["id"],
            "title": movie_data.get("title"),
            "original_title": movie_data.get("original_title"),
            "overview": movie_data.get("overview"),
            "release_date": movie_data.get("release_date"),
            "runtime": movie_data.get("runtime"),
            "genres": json.dumps(movie_data.get("genres", [])),
            "cast_info": json.dumps(movie_data.get("cast_info", [])),
            "keywords": json.dumps(movie_data.get("keywords", [])),
            "poster_path": movie_data.get("poster_path"),
            "backdrop_path": movie_data.get("backdrop_path"),
            "vote_average": movie_data.get("vote_average"),
            "vote_count": movie_data.get("vote_count"),
            "popularity": movie_data.get("popularity"),
            "streaming_providers": json.dumps(movie_data.get("streaming_providers", {})),
            "trailer_url": movie_data.get("trailer_url")
        }
