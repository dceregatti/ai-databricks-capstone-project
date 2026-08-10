"""Movie Night Planner MCP Server.

Exposes movie planning tools over MCP (Model Context Protocol) so a
Databricks Agent can help users find and plan movie nights:
    - search_movies(query, filters)
    - get_movie_details(movie_id)
    - add_to_watchlist(user_id, movie_id)
    - get_recommendations(user_id, preferences)
    - create_movie_night(group_id, preferences)

Deploy this as a Databricks App (FastMCP + app.yaml pattern) so an Agent
can register its URL as an external MCP server.

Run locally:
    python movie_mcp_server.py
"""

import os
import logging
from datetime import datetime
from fastmcp import FastMCP
from sentence_transformers import SentenceTransformer

import lakebase
import tmdb_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("movie-mcp-server")

# Embedding model for semantic search
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
_embedding_model = None

def get_embedding_model():
    """Lazy-load the embedding model (expensive operation, only on first use)."""
    global _embedding_model
    if _embedding_model is None:
        logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
        _embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    return _embedding_model

mcp = FastMCP("movie-night-planner")


@mcp.prompt()
def system_context() -> str:
    """
    System prompt that describes the Movie Night Planner capabilities and constraints.
    Agents should read this to understand what the system can and cannot do.
    """
    return """# Movie Night Planner MCP Server - System Context

You are assisting users with a Movie Night Planner that helps groups find and organize movies to watch together.

## DATA SOURCES

1. **TMDB (The Movie Database) API**: External movie database
   - Provides: Movie titles, descriptions, ratings, genres, cast, crew, release dates
   - Limitations: Only movies in TMDB's catalog (no private/unreleased content)
   - Ratings: TMDB community ratings (vote_average), NOT internal user ratings

2. **Lakebase Postgres Database**: Internal user data
   - Stores: User watchlists, group memberships, ratings, watched status
   - Limitations: Only data explicitly saved by users through this system

## WHAT YOU CAN DO

✅ Search for movies by title, genre, or year using TMDB
✅ Get detailed information about specific movies (by TMDB ID)
✅ Compare multiple movies side-by-side
✅ Add movies to user watchlists
✅ Record user ratings (0-5 scale) with optional reviews
✅ Track which movies users/groups have watched
✅ Get smart recommendations that filter out watched/disliked movies
✅ Semantic search using natural language descriptions

## WHAT YOU CANNOT DO

❌ Access movies not in TMDB's database
❌ Provide streaming availability or where to watch
❌ Access user data from other systems or apps
❌ Recommend movies based on viewing history from Netflix, etc.
❌ Make assumptions about user preferences unless explicitly stored
❌ Access real-time data (TMDB data is cached when movies are fetched)

## CRITICAL: AVOIDING HALLUCINATIONS

**ONLY return data that is explicitly provided by tool responses.**

- If a movie is not in the response, say "I couldn't find that movie" - do NOT make up details
- If a user hasn't rated a movie, say "No rating recorded" - do NOT assume a rating
- If a group hasn't watched a movie, say "Not watched yet" - do NOT infer from other data
- When tools return empty results, acknowledge it explicitly: "No movies match those criteria"
- All movie IDs are TMDB IDs - do NOT confuse with internal database IDs

## RESPONSE HANDLING

All tools return standardized responses:
```json
{
  "tool_name": "tool_name",
  "success": true/false,
  "message": "human-readable explanation",
  "data": { /* actual data or null */ }
}
```

**Check success=false responses:**
- If success=false, explain the error to the user clearly
- Do NOT retry with made-up parameters
- Do NOT assume data exists if the tool reported failure

## WORKING WITH GROUPS

Sample users for testing:
- User ID 1: Test User (test@example.com)
- User ID 2: Alice Smith (alice@example.com)
- User ID 3: Bob Johnson (bob@example.com)
- Group ID 1: "Friday Night Movies" (all 3 users)

When recommending movies for a group:
1. Use `get_group_watched_movies()` to see what they've already seen
2. Use `get_group_disliked_movies()` to see what they didn't like
3. Use `get_smart_recommendations()` which auto-filters these out

## BEST PRACTICES

1. **Be explicit about data sources**: "According to TMDB..." vs "In your watchlist..."
2. **Acknowledge limitations**: "I can only search TMDB's catalog"
3. **Confirm before assumptions**: "Which user would you like to add this to?"
4. **Use structured comparisons**: When comparing movies, present data in tables
5. **Explain filters**: When recommendations exclude movies, explain why

## EXAMPLE GOOD BEHAVIORS

✅ "I found 3 action movies from 2023 in TMDB: [list]. Would you like details on any?"
✅ "Your group has already watched 5 movies: [list]. I'll recommend something new."
✅ "I couldn't find a movie with that title. Could you check the spelling?"
✅ "This movie has a TMDB rating of 7.5/10 based on 2,340 votes."

## EXAMPLE BAD BEHAVIORS (HALLUCINATIONS)

❌ "This movie is available on Netflix" (we don't have streaming data)
❌ "Based on your viewing history..." (we only have what's in watchlist/ratings)
❌ "This movie is perfect for you" (without checking preferences/ratings)
❌ Making up movie details not returned by TMDB
❌ Assuming ratings or watch status without checking the database

Remember: **Only state facts explicitly provided by tool responses. When in doubt, acknowledge the limitation.**
"""


def standardize_response(tool_name: str, success: bool, message: str, data: dict = None) -> dict:
    """Create a standardized response format for all MCP tools."""
    response = {
        "tool_name": tool_name,
        "success": success,
        "message": message
    }
    if data:
        response["data"] = data
    return response


@mcp.tool
def search_movies(query: str, genre: str = None, year: int = None) -> dict:
    """
    Search for movies by title with optional filters.

    Args:
        query: Movie title to search for
        genre: Optional genre filter (e.g., "Action", "Comedy")
        year: Optional release year

    Returns:
        Standardized response with search results
    """
    try:
        # Build TMDB discover/search params
        params = {}
        if genre:
            params["with_genres"] = genre
        if year:
            params["year"] = year

        if params:
            results = tmdb_client.discover_movies(params)
        else:
            results = tmdb_client.search_movies(query)

        movies = results.get("results", [])
        return standardize_response(
            tool_name="search_movies",
            success=True,
            message=f"Found {len(movies)} movies matching '{query}'",
            data={"movies": movies, "total_results": results.get("total_results", 0)}
        )
    except Exception as e:
        logger.exception(f"Error searching movies: {e}")
        return standardize_response(
            tool_name="search_movies",
            success=False,
            message=f"Failed to search movies: {str(e)}",
            data={"error": str(e)}
        )


@mcp.tool
def get_movie_details(movie_id: int) -> dict:
    """
    Get detailed information about a specific movie.

    Args:
        movie_id: TMDB movie ID

    Returns:
        Standardized response with movie details
    """
    try:
        movie = tmdb_client.get_movie_details(movie_id)
        return standardize_response(
            tool_name="get_movie_details",
            success=True,
            message=f"Retrieved details for {movie.get('title', 'movie')}",
            data=movie
        )
    except Exception as e:
        logger.exception(f"Error getting movie details: {e}")
        return standardize_response(
            tool_name="get_movie_details",
            success=False,
            message=f"Failed to get movie details: {str(e)}",
            data={"error": str(e)}
        )


@mcp.tool
def add_to_watchlist(user_id: int, movie_id: int, notes: str = None) -> dict:
    """
    Add a movie to a user's watchlist.

    Args:
        user_id: User ID
        movie_id: TMDB movie ID
        notes: Optional notes about why they want to watch it

    Returns:
        Standardized response
    """
    try:
        # Check if already in watchlist
        existing = lakebase.run_query(
            "SELECT id FROM watchlist WHERE user_id = %s AND movie_id = %s",
            (user_id, movie_id)
        )
        
        if existing:
            return standardize_response(
                tool_name="add_to_watchlist",
                success=False,
                message="Movie is already in your watchlist"
            )

        # Add to watchlist
        lakebase.run_write(
            """INSERT INTO watchlist (user_id, movie_id, notes, added_at) 
               VALUES (%s, %s, %s, %s)""",
            (user_id, movie_id, notes, datetime.now())
        )

        return standardize_response(
            tool_name="add_to_watchlist",
            success=True,
            message="Movie added to watchlist"
        )
    except Exception as e:
        logger.exception(f"Error adding to watchlist: {e}")
        return standardize_response(
            tool_name="add_to_watchlist",
            success=False,
            message=f"Failed to add to watchlist: {str(e)}",
            data={"error": str(e)}
        )


@mcp.tool
def get_user_watchlist(user_id: int) -> dict:
    """
    Get a user's watchlist.

    Args:
        user_id: User ID

    Returns:
        Standardized response with watchlist
    """
    try:
        watchlist = lakebase.run_query(
            """SELECT w.*, m.title, m.overview, m.runtime, m.vote_average 
               FROM watchlist w 
               JOIN movies m ON w.movie_id = m.tmdb_id 
               WHERE w.user_id = %s 
               ORDER BY w.added_at DESC""",
            (user_id,)
        )

        return standardize_response(
            tool_name="get_user_watchlist",
            success=True,
            message=f"Retrieved {len(watchlist)} movies from watchlist",
            data={"watchlist": watchlist}
        )
    except Exception as e:
        logger.exception(f"Error getting watchlist: {e}")
        return standardize_response(
            tool_name="get_user_watchlist",
            success=False,
            message=f"Failed to get watchlist: {str(e)}",
            data={"error": str(e)}
        )


@mcp.tool
def semantic_movie_search(query: str, limit: int = 10) -> dict:
    """
    Semantic search for movies using natural language.
    Example: "a funny sci-fi movie under two hours"

    Args:
        query: Natural language description of desired movie
        limit: Maximum number of results

    Returns:
        Standardized response with matching movies
    """
    try:
        # Use pgvector similarity search
        # This requires embeddings to be pre-computed for movies
        results = lakebase.run_query(
            """
            SELECT m.*, 
                   1 - (e.embedding <=> %s::vector) as similarity
            FROM movies m
            JOIN movie_embeddings e ON m.tmdb_id = e.movie_id
            ORDER BY e.embedding <=> %s::vector
            LIMIT %s
            """,
            (query, query, limit)
        )

        return standardize_response(
            tool_name="semantic_movie_search",
            success=True,
            message=f"Found {len(results)} movies matching description",
            data={"movies": results}
        )
    except Exception as e:
        logger.exception(f"Error in semantic search: {e}")
        return standardize_response(
            tool_name="semantic_movie_search",
            success=False,
            message=f"Failed to perform semantic search: {str(e)}",
            data={"error": str(e)}
        )


@mcp.tool
def compare_movies(movie_ids: list[int]) -> dict:
    """
    Compare multiple movies side-by-side with key metrics.

    Args:
        movie_ids: List of TMDB movie IDs to compare (2-5 movies)

    Returns:
        Standardized response with comparison data
    """
    try:
        if len(movie_ids) < 2:
            return standardize_response(
                tool_name="compare_movies",
                success=False,
                message="Need at least 2 movies to compare"
            )
        
        if len(movie_ids) > 5:
            return standardize_response(
                tool_name="compare_movies",
                success=False,
                message="Can compare at most 5 movies at a time"
            )

        # Fetch details for all movies
        movies = []
        for movie_id in movie_ids:
            try:
                movie = tmdb_client.get_movie_details(movie_id)
                movies.append(movie)
            except Exception as e:
                logger.warning(f"Could not fetch movie {movie_id}: {e}")

        if not movies:
            return standardize_response(
                tool_name="compare_movies",
                success=False,
                message="Could not fetch any movie details"
            )

        # Create comparison matrix
        comparison = {
            "movies": movies,
            "comparison_fields": {
                "title": [m.get("title") for m in movies],
                "runtime_minutes": [m.get("runtime") for m in movies],
                "rating": [m.get("vote_average") for m in movies],
                "vote_count": [m.get("vote_count") for m in movies],
                "release_year": [m.get("release_date", "")[:4] if m.get("release_date") else None for m in movies],
                "genres": [[g["name"] for g in m.get("genres", [])] for m in movies],
            },
            "best_rated": max(movies, key=lambda m: m.get("vote_average", 0)).get("title"),
            "shortest": min((m for m in movies if m.get("runtime")), key=lambda m: m.get("runtime", 999), default={}).get("title"),
            "longest": max((m for m in movies if m.get("runtime")), key=lambda m: m.get("runtime", 0), default={}).get("title"),
        }

        return standardize_response(
            tool_name="compare_movies",
            success=True,
            message=f"Compared {len(movies)} movies",
            data=comparison
        )
    except Exception as e:
        logger.exception(f"Error comparing movies: {e}")
        return standardize_response(
            tool_name="compare_movies",
            success=False,
            message=f"Failed to compare movies: {str(e)}",
            data={"error": str(e)}
        )


@mcp.tool
def record_rating(user_id: int, movie_id: int, rating: float, review: str = None) -> dict:
    """
    Record a user's rating for a movie after watching it.

    Args:
        user_id: User ID
        movie_id: TMDB movie ID
        rating: Rating from 0.0 to 5.0 (e.g., 4.5)
        review: Optional text review

    Returns:
        Standardized response
    """
    try:
        if not (0 <= rating <= 5):
            return standardize_response(
                tool_name="record_rating",
                success=False,
                message="Rating must be between 0.0 and 5.0"
            )

        # Check if rating already exists
        existing = lakebase.run_query(
            "SELECT id FROM ratings WHERE user_id = %s AND movie_id = %s",
            (user_id, movie_id)
        )

        if existing:
            # Update existing rating
            lakebase.run_write(
                """UPDATE ratings 
                   SET rating = %s, review = %s, updated_at = %s
                   WHERE user_id = %s AND movie_id = %s""",
                (rating, review, datetime.now(), user_id, movie_id)
            )
            message = "Rating updated"
        else:
            # Insert new rating
            lakebase.run_write(
                """INSERT INTO ratings (user_id, movie_id, rating, review, created_at)
                   VALUES (%s, %s, %s, %s, %s)""",
                (user_id, movie_id, rating, review, datetime.now())
            )
            message = "Rating recorded"

        # Also mark as watched in watchlist if it exists
        lakebase.run_write(
            """UPDATE watchlist 
               SET watched = TRUE, watched_at = %s
               WHERE user_id = %s AND movie_id = %s AND watched = FALSE""",
            (datetime.now(), user_id, movie_id)
        )

        return standardize_response(
            tool_name="record_rating",
            success=True,
            message=message,
            data={"rating": rating, "movie_id": movie_id}
        )
    except Exception as e:
        logger.exception(f"Error recording rating: {e}")
        return standardize_response(
            tool_name="record_rating",
            success=False,
            message=f"Failed to record rating: {str(e)}",
            data={"error": str(e)}
        )


@mcp.tool
def mark_as_watched(user_id: int, movie_id: int) -> dict:
    """
    Mark a movie as watched by a user (without rating it).

    Args:
        user_id: User ID
        movie_id: TMDB movie ID

    Returns:
        Standardized response
    """
    try:
        # Update watchlist if exists, or create entry
        existing = lakebase.run_query(
            "SELECT id FROM watchlist WHERE user_id = %s AND movie_id = %s",
            (user_id, movie_id)
        )

        if existing:
            lakebase.run_write(
                """UPDATE watchlist 
                   SET watched = TRUE, watched_at = %s
                   WHERE user_id = %s AND movie_id = %s""",
                (datetime.now(), user_id, movie_id)
            )
        else:
            lakebase.run_write(
                """INSERT INTO watchlist (user_id, movie_id, watched, watched_at, added_at)
                   VALUES (%s, %s, TRUE, %s, %s)""",
                (user_id, movie_id, datetime.now(), datetime.now())
            )

        return standardize_response(
            tool_name="mark_as_watched",
            success=True,
            message="Movie marked as watched"
        )
    except Exception as e:
        logger.exception(f"Error marking as watched: {e}")
        return standardize_response(
            tool_name="mark_as_watched",
            success=False,
            message=f"Failed to mark as watched: {str(e)}",
            data={"error": str(e)}
        )


@mcp.tool
def get_group_watched_movies(group_id: int) -> dict:
    """
    Get all movies watched by any member of a group.
    Use this to avoid recommending movies the group has already seen.

    Args:
        group_id: Group ID

    Returns:
        Standardized response with list of watched movies
    """
    try:
        watched = lakebase.run_query(
            """SELECT DISTINCT m.tmdb_id, m.title, m.release_date, m.vote_average,
                      ARRAY_AGG(u.name) as watched_by
               FROM watchlist w
               JOIN users u ON w.user_id = u.id
               JOIN movies m ON w.movie_id = m.tmdb_id
               JOIN group_members gm ON u.id = gm.user_id
               WHERE gm.group_id = %s AND w.watched = TRUE
               GROUP BY m.tmdb_id, m.title, m.release_date, m.vote_average
               ORDER BY MAX(w.watched_at) DESC""",
            (group_id,)
        )

        return standardize_response(
            tool_name="get_group_watched_movies",
            success=True,
            message=f"Found {len(watched)} watched movies",
            data={"watched_movies": watched, "count": len(watched)}
        )
    except Exception as e:
        logger.exception(f"Error getting watched movies: {e}")
        return standardize_response(
            tool_name="get_group_watched_movies",
            success=False,
            message=f"Failed to get watched movies: {str(e)}",
            data={"error": str(e)}
        )


@mcp.tool
def get_group_disliked_movies(group_id: int, threshold: float = 2.0) -> dict:
    """
    Get movies that group members disliked (rated below threshold).
    Use this to avoid recommending movies the group won't enjoy.

    Args:
        group_id: Group ID
        threshold: Rating threshold (default 2.0, movies rated below this are considered disliked)

    Returns:
        Standardized response with list of disliked movies
    """
    try:
        disliked = lakebase.run_query(
            """SELECT DISTINCT m.tmdb_id, m.title, m.release_date,
                      AVG(r.rating) as avg_group_rating,
                      ARRAY_AGG(u.name) as rated_by
               FROM ratings r
               JOIN users u ON r.user_id = u.id
               JOIN movies m ON r.movie_id = m.tmdb_id
               JOIN group_members gm ON u.id = gm.user_id
               WHERE gm.group_id = %s AND r.rating < %s
               GROUP BY m.tmdb_id, m.title, m.release_date
               ORDER BY AVG(r.rating) ASC""",
            (group_id, threshold)
        )

        return standardize_response(
            tool_name="get_group_disliked_movies",
            success=True,
            message=f"Found {len(disliked)} disliked movies (rated below {threshold})",
            data={"disliked_movies": disliked, "count": len(disliked), "threshold": threshold}
        )
    except Exception as e:
        logger.exception(f"Error getting disliked movies: {e}")
        return standardize_response(
            tool_name="get_group_disliked_movies",
            success=False,
            message=f"Failed to get disliked movies: {str(e)}",
            data={"error": str(e)}
        )


@mcp.tool
def get_smart_recommendations(group_id: int, genre: str = None, limit: int = 10) -> dict:
    """
    Get smart movie recommendations for a group that:
    - Filters out movies already watched by the group
    - Filters out movies disliked by any member (rated < 2.0)
    - Considers group preferences

    Args:
        group_id: Group ID
        genre: Optional genre filter
        limit: Maximum number of recommendations

    Returns:
        Standardized response with filtered recommendations
    """
    try:
        # Get movies to exclude (watched or disliked)
        exclude_query = """
            SELECT DISTINCT m.tmdb_id
            FROM movies m
            WHERE m.tmdb_id IN (
                -- Watched movies
                SELECT w.movie_id FROM watchlist w
                JOIN group_members gm ON w.user_id = gm.user_id
                WHERE gm.group_id = %s AND w.watched = TRUE
                UNION
                -- Disliked movies (rated < 2.0)
                SELECT r.movie_id FROM ratings r
                JOIN group_members gm ON r.user_id = gm.user_id
                WHERE gm.group_id = %s AND r.rating < 2.0
            )
        """
        excluded_ids = [row["tmdb_id"] for row in lakebase.run_query(exclude_query, (group_id, group_id))]

        # Search for popular movies and filter out excluded ones
        popular = tmdb_client.get_popular_movies()
        recommendations = []
        
        for movie in popular.get("results", []):
            if movie["id"] not in excluded_ids:
                # Apply genre filter if specified
                if genre:
                    movie_details = tmdb_client.get_movie_details(movie["id"])
                    movie_genres = [g["name"] for g in movie_details.get("genres", [])]
                    if genre.lower() not in [g.lower() for g in movie_genres]:
                        continue
                
                recommendations.append(movie)
                
                if len(recommendations) >= limit:
                    break

        return standardize_response(
            tool_name="get_smart_recommendations",
            success=True,
            message=f"Found {len(recommendations)} recommended movies (filtered {len(excluded_ids)} watched/disliked)",
            data={
                "recommendations": recommendations,
                "excluded_count": len(excluded_ids),
                "filters_applied": {
                    "exclude_watched": True,
                    "exclude_disliked": True,
                    "genre": genre
                }
            }
        )
    except Exception as e:
        logger.exception(f"Error getting smart recommendations: {e}")
        return standardize_response(
            tool_name="get_smart_recommendations",
            success=False,
            message=f"Failed to get recommendations: {str(e)}",
            data={"error": str(e)}
        )


# Export stateless HTTP app for Databricks Apps
# (App creation moved to end after all route handlers are defined)

# ============================================================================
# DASHBOARD ROUTES (Web UI for humans)
# ============================================================================

from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route
import json

async def dashboard_home(request):
    """Serve the main dashboard page."""
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Movie Planner Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 {
            color: white;
            text-align: center;
            margin-bottom: 20px;
            font-size: 2.5em;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .nav {
            display: flex;
            justify-content: center;
            gap: 20px;
            margin-bottom: 30px;
        }
        .nav a {
            color: white;
            text-decoration: none;
            padding: 10px 20px;
            background: rgba(255,255,255,0.2);
            border-radius: 8px;
            transition: all 0.3s;
        }
        .nav a:hover {
            background: rgba(255,255,255,0.3);
            transform: translateY(-2px);
        }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: white;
            border-radius: 15px;
            padding: 25px;
            text-align: center;
            box-shadow: 0 10px 25px rgba(0,0,0,0.2);
            transition: transform 0.3s ease;
        }
        .stat-card:hover { transform: translateY(-5px); }
        .stat-value {
            font-size: 3em;
            font-weight: bold;
            color: #667eea;
            margin: 10px 0;
        }
        .stat-label {
            color: #666;
            font-size: 1.1em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .top-movies {
            background: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.2);
            margin-bottom: 30px;
        }
        .top-movies h2 {
            color: #333;
            margin-bottom: 20px;
            font-size: 1.8em;
        }
        .movie-list {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
        }
        .movie-item {
            text-align: center;
            padding: 15px;
            border-radius: 10px;
            background: #f8f9fa;
            transition: all 0.3s ease;
        }
        .movie-item:hover {
            background: #e9ecef;
            transform: scale(1.05);
        }
        .movie-poster {
            width: 100%;
            height: 250px;
            object-fit: cover;
            border-radius: 8px;
            margin-bottom: 10px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.2);
        }
        .movie-title {
            font-weight: bold;
            color: #333;
            margin-bottom: 5px;
            font-size: 1.1em;
        }
        .movie-rating {
            color: #667eea;
            font-size: 1.3em;
            font-weight: bold;
        }
        .charts-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .chart-card {
            background: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.2);
        }
        .chart-card h2 {
            color: #333;
            margin-bottom: 20px;
            font-size: 1.5em;
        }
        .watched-movies {
            background: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.2);
        }
        .watched-movies h2 {
            color: #333;
            margin-bottom: 20px;
            font-size: 1.8em;
        }
        .watched-list { max-height: 500px; overflow-y: auto; }
        .watched-item {
            display: flex;
            align-items: center;
            padding: 15px;
            border-bottom: 1px solid #eee;
            transition: background 0.3s ease;
        }
        .watched-item:hover { background: #f8f9fa; }
        .watched-info { flex: 1; }
        .watched-title {
            font-weight: bold;
            color: #333;
            margin-bottom: 5px;
        }
        .watched-meta {
            color: #999;
            font-size: 0.9em;
        }
        .watched-rating {
            font-size: 1.5em;
            color: #f39c12;
            margin-left: 15px;
        }
        .loading {
            text-align: center;
            padding: 40px;
            color: white;
            font-size: 1.5em;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎬 Movie Planner Dashboard</h1>
        <div class="nav">
            <a href="/">🏠 Home</a>
            <a href="/groups">👫 Groups</a>
            <a href="/recommendations">🎬 Get Recommendations</a>
            </div>
        
        <div id="loading" class="loading">Loading dashboard...</div>
        
        <div id="dashboard" style="display: none;">
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-label">Total Movies</div>
                    <div class="stat-value" id="stat-total">0</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Watched</div>
                    <div class="stat-value" id="stat-watched">0</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Rated Movies</div>
                    <div class="stat-value" id="stat-rated">0</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Avg Rating</div>
                    <div class="stat-value" id="stat-avg-rating">0</div>
                </div>
            </div>
            
            <div class="top-movies">
                <h2>🏆 Top 5 Rated Movies</h2>
                <div class="movie-list" id="top-movies-list"></div>
            </div>
            
            <div class="charts-grid">
                <div class="chart-card">
                    <h2>📊 Rating Distribution</h2>
                    <canvas id="rating-chart"></canvas>
                </div>
                <div class="chart-card">
                    <h2>📈 Watchlist Overview</h2>
                    <canvas id="watchlist-chart"></canvas>
                </div>
            </div>
            
            <div class="watched-movies">
                <h2>✅ Recently Watched Movies</h2>
                <div class="watched-list" id="watched-list"></div>
            </div>
        </div>
    </div>
    
    <script>
        async function loadDashboard() {
            try {
                const statsRes = await fetch('/api/watchlist-stats');
                const stats = await statsRes.json();
                document.getElementById('stat-total').textContent = stats.total;
                document.getElementById('stat-watched').textContent = stats.watched;
                document.getElementById('stat-rated').textContent = stats.rated;
                document.getElementById('stat-avg-rating').textContent = stats.avg_rating.toFixed(1) + '⭐';
                
                const topRatedRes = await fetch('/api/top-rated');
                const topRated = await topRatedRes.json();
                const topMoviesList = document.getElementById('top-movies-list');
                topMoviesList.innerHTML = topRated.map((movie, index) => `
                    <div class="movie-item">
                        <img src="https://image.tmdb.org/t/p/w500${movie.poster_path || ''}" 
                             class="movie-poster" 
                             onerror="this.src='https://via.placeholder.com/200x300?text=No+Poster'"
                             alt="${movie.title}">
                        <div class="movie-title">${index + 1}. ${movie.title}</div>
                        <div class="movie-rating">${movie.avg_rating.toFixed(1)} ⭐</div>
                        <div style="color: #999; font-size: 0.9em;">(${movie.rating_count} ratings)</div>
                    </div>
                `).join('');
                
                const ratingDistRes = await fetch('/api/rating-distribution');
                const ratingDist = await ratingDistRes.json();
                const ratingChart = new Chart(document.getElementById('rating-chart'), {
                    type: 'bar',
                    data: {
                        labels: ratingDist.map(d => d.rating_floor + ' stars'),
                        datasets: [{
                            label: 'Number of Ratings',
                            data: ratingDist.map(d => d.count),
                            backgroundColor: 'rgba(102, 126, 234, 0.8)',
                            borderColor: 'rgba(102, 126, 234, 1)',
                            borderWidth: 2
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: { legend: { display: false } },
                        scales: { y: { beginAtZero: true, ticks: { precision: 0 } } }
                    }
                });
                
                const watchlistChart = new Chart(document.getElementById('watchlist-chart'), {
                    type: 'doughnut',
                    data: {
                        labels: ['Watched', 'Unwatched'],
                        datasets: [{
                            data: [stats.watched, stats.unwatched],
                            backgroundColor: ['rgba(46, 213, 115, 0.8)', 'rgba(255, 159, 64, 0.8)'],
                            borderColor: ['rgba(46, 213, 115, 1)', 'rgba(255, 159, 64, 1)'],
                            borderWidth: 2
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: { legend: { position: 'bottom' } }
                    }
                });
                
                const watchedRes = await fetch('/api/watched-movies');
                const watched = await watchedRes.json();
                const watchedList = document.getElementById('watched-list');
                watchedList.innerHTML = watched.map(movie => `
                    <div class="watched-item">
                        <div class="watched-info">
                            <div class="watched-title">${movie.title}</div>
                            <div class="watched-meta">
                                ${movie.username ? `Watched by ${movie.username}` : 'No user info'}
                                ${movie.rated_at ? ` on ${new Date(movie.rated_at).toLocaleDateString()}` : ''}
                            </div>
                            ${movie.comment ? `<div class="watched-meta" style="margin-top: 5px;">"${movie.comment}"</div>` : ''}
                        </div>
                        ${movie.rating ? `<div class="watched-rating">${movie.rating} ⭐</div>` : ''}
                    </div>
                `).join('');
                
                document.getElementById('loading').style.display = 'none';
                document.getElementById('dashboard').style.display = 'block';
                
            } catch (error) {
                console.error('Error loading dashboard:', error);
                document.getElementById('loading').textContent = 'Error loading dashboard: ' + error.message;
            }
        }
        loadDashboard();
    </script>
</body>
</html>"""
    return HTMLResponse(content=html_content)

async def api_watched_movies(request):
    """Get watched movies with ratings."""
    try:
        query = """
        SELECT 
            m.title,
            m.tmdb_id,
            m.release_date,
            m.poster_path,
            r.rating,
            r.review as comment,
            r.created_at as rated_at,
            u.name as username
        FROM watchlist w
        JOIN movies m ON w.movie_id = m.tmdb_id
        LEFT JOIN ratings r ON w.user_id = r.user_id AND w.movie_id = r.movie_id
        LEFT JOIN users u ON w.user_id = u.id
        WHERE w.watched = TRUE
        ORDER BY w.watched_at DESC
        LIMIT 50
        """
        results = lakebase.run_query(query)
        # Convert datetime objects to strings
        for row in results:
            if row.get('rated_at'):
                row['rated_at'] = row['rated_at'].isoformat() if hasattr(row['rated_at'], 'isoformat') else str(row['rated_at'])
            if row.get('release_date'):
                row['release_date'] = str(row['release_date'])
        return JSONResponse(results)
    except Exception as e:
        logger.exception(f"Error fetching watched movies: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_top_rated(request):
    """Get top 5 rated movies."""
    try:
        query = """
        SELECT 
            m.title,
            m.tmdb_id,
            m.poster_path,
            AVG(r.rating) as avg_rating,
            COUNT(r.id) as rating_count
        FROM movies m
        JOIN ratings r ON m.tmdb_id = r.movie_id
        GROUP BY m.tmdb_id, m.title, m.poster_path
        HAVING COUNT(r.id) >= 1
        ORDER BY avg_rating DESC, rating_count DESC
        LIMIT 5
        """
        results = lakebase.run_query(query)
        # Convert Decimal to float
        for row in results:
            if row.get('avg_rating'):
                row['avg_rating'] = float(row['avg_rating'])
        return JSONResponse(results)
    except Exception as e:
        logger.exception(f"Error fetching top rated movies: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_watchlist_stats(request):
    """Get watchlist statistics."""
    try:
        total = lakebase.run_query("SELECT COUNT(*) as total FROM watchlist")[0]['total']
        watched = lakebase.run_query("SELECT COUNT(*) as watched FROM watchlist WHERE watched = TRUE")[0]['watched']
        rated = lakebase.run_query("SELECT COUNT(DISTINCT movie_id) as rated FROM ratings")[0]['rated']
        avg_result = lakebase.run_query("SELECT AVG(rating) as avg_rating FROM ratings")[0]
        avg_rating = float(avg_result['avg_rating']) if avg_result['avg_rating'] else 0
        
        return JSONResponse({
            'total': total,
            'watched': watched,
            'unwatched': total - watched,
            'rated': rated,
            'avg_rating': round(avg_rating, 2)
        })
    except Exception as e:
        logger.exception(f"Error fetching watchlist stats: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_rating_distribution(request):
    """Get distribution of ratings."""
    try:
        query = """
        SELECT 
            FLOOR(rating) as rating_floor,
            COUNT(*) as count
        FROM ratings
        GROUP BY FLOOR(rating)
        ORDER BY rating_floor
        """
        results = lakebase.run_query(query)
        return JSONResponse(results)
    except Exception as e:
        logger.exception(f"Error fetching rating distribution: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

async def groups_page(request):
    """Groups management page with full CRUD operations."""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Groups - Movie Night Planner</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; padding: 20px; }
            .container { max-width: 1200px; margin: 0 auto; }
            .header { background: white; padding: 30px; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); margin-bottom: 30px; }
            .header h1 { color: #333; margin-bottom: 10px; }
            .nav { display: flex; gap: 15px; margin-top: 20px; }
            .nav a { color: #667eea; text-decoration: none; padding: 8px 16px; border-radius: 8px; transition: all 0.3s; }
            .nav a:hover { background: #667eea; color: white; }
            .card { background: white; padding: 25px; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); margin-bottom: 20px; }
            .card h2 { color: #333; margin-bottom: 20px; }
            .form-group { margin-bottom: 15px; }
            .form-group label { display: block; margin-bottom: 5px; color: #555; font-weight: 600; }
            .form-group input, .form-group textarea, .form-group select { width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; font-size: 14px; }
            .btn { background: #667eea; color: white; border: none; padding: 12px 24px; border-radius: 8px; cursor: pointer; font-size: 16px; transition: all 0.3s; }
            .btn:hover { background: #5568d3; transform: translateY(-2px); }
            .btn-sm { padding: 6px 12px; font-size: 14px; }
            .btn-danger { background: #e74c3c; }
            .btn-danger:hover { background: #c0392b; }
            .group-list { display: grid; gap: 15px; }
            .group-item { background: #f8f9fa; padding: 20px; border-radius: 10px; border-left: 4px solid #667eea; cursor: pointer; transition: all 0.3s; }
            .group-item:hover { box-shadow: 0 5px 15px rgba(0,0,0,0.1); transform: translateY(-2px); }
            .group-item h3 { color: #333; margin-bottom: 8px; }
            .group-item .meta { color: #666; font-size: 0.9em; margin-bottom: 10px; }
            .group-item .description { color: #555; margin-bottom: 10px; }
            .members-section { margin-top: 15px; padding-top: 15px; border-top: 1px solid #ddd; display: none; }
            .members-section.active { display: block; }
            .member-list { margin-top: 10px; }
            .member-item { background: white; padding: 10px; border-radius: 5px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; }
            .member-info { flex: 1; }
            .member-name { font-weight: 600; color: #333; }
            .member-email { color: #666; font-size: 0.9em; }
            .member-role { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.85em; font-weight: 600; }
            .role-admin { background: #667eea; color: white; }
            .role-member { background: #e8eaf6; color: #667eea; }
            .add-member-form { margin-top: 15px; padding: 15px; background: #e8f5e9; border: 2px dashed #4caf50; border-radius: 8px; }
            .add-member-form h4 { color: #2e7d32; }
            .no-users-available { margin-top: 15px; padding: 15px; background: #fff3e0; border: 2px dashed #ff9800; border-radius: 8px; color: #e65100; text-align: center; }
            .loading { text-align: center; padding: 40px; color: #667eea; }
            .message { padding: 12px; border-radius: 8px; margin-bottom: 15px; }
            .message.success { background: #d4edda; color: #155724; }
            .message.error { background: #f8d7da; color: #721c24; }
            .member-selector { padding: 10px; border: 1px solid #ddd; border-radius: 8px; background: white; transition: all 0.3s; font-size: 14px; cursor: pointer; }
            .member-selector:hover { border-color: #667eea; }
            .member-selector:focus { border-color: #667eea; box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1); outline: none; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>👫 Movie Night Groups</h1>
                <p style="color: #666; margin-top: 10px;">Create and manage your movie night groups</p>
                <div class="nav">
                    <a href="/">🏠 Home</a>
                    <a href="/groups">👫 Groups</a>
                    <a href="/recommendations">🎬 Get Recommendations</a>
            </div>
            </div>
            
            <div id="message-container"></div>
            
            <div class="card">
                <h2>➕ Create New Group</h2>
                <form id="createGroupForm">
                    <div class="form-group">
                        <label>Group Name *</label>
                        <input type="text" id="groupName" required placeholder="Friday Night Movies">
                    </div>
                    <div class="form-group">
                        <label>Description</label>
                        <textarea id="groupDescription" rows="3" placeholder="Weekly movie night with friends"></textarea>
                    </div>
                    <div class="form-group">
                        <label>Add Member</label>
                        <select id="groupMembers" class="member-selector">
                            <option value="">-- Select a member to add (optional) --</option>
                            <!-- Will be populated with users -->
                        </select>
                    </div>
                    <button type="submit" class="btn">✅ Create Group</button>
                </form>
            </div>
            
            <div class="card">
                <h2>👥 All Groups</h2>
                <div id="groupsList" class="loading">Loading groups...</div>
            </div>
        </div>
        
        <script>
            let allUsers = [];
            
            function showMessage(text, type = 'success') {
                const container = document.getElementById('message-container');
                container.innerHTML = `<div class="message ${type}">${text}</div>`;
                setTimeout(() => container.innerHTML = '', 5000);
            }
            
            async function loadUsers() {
                try {
                    const response = await fetch('/api/users');
                    allUsers = await response.json();
                    
                    // Populate the create group form members dropdown
                    const membersSelect = document.getElementById('groupMembers');
                    membersSelect.innerHTML = '<option value="">-- Select a member to add (optional) --</option>' + 
                        allUsers.map(u => 
                            `<option value="${u.id}">${u.name} (${u.email})</option>`
                        ).join('');
                } catch (error) {
                    console.error('Error loading users:', error);
                }
            }
            
            async function loadGroups() {
                try {
                    const response = await fetch('/api/groups');
                    const groups = await response.json();
                    
                    const container = document.getElementById('groupsList');
                    
                    if (groups.length === 0) {
                        container.innerHTML = '<p style="color: #666; text-align: center;">No groups yet. Create one above!</p>';
                        return;
                    }
                    
                    container.innerHTML = '<div class="group-list">' + groups.map(g => `
                        <div class="group-item" onclick="toggleMembers(${g.id})" data-group-id="${g.id}">
                            <h3>${g.name} <span style="float: right; color: #667eea; font-size: 0.8em;">▼</span></h3>
                            ${g.description ? `<div class="description">${g.description}</div>` : ''}
                            <div class="meta">
                                <span>👤 ${g.creator_name || 'Unknown'}</span>
                                <span style="margin-left: 20px;">👥 ${g.member_count} member${g.member_count === 1 ? '' : 's'}</span>
                                <span style="margin-left: 20px;">📅 ${new Date(g.created_at).toLocaleDateString()}</span>
                            </div>
                            
                            <div class="members-section" id="members-${g.id}" onclick="event.stopPropagation()">
                                <div class="loading">Loading members...</div>
                            </div>
                        </div>
                    `).join('') + '</div>';
                } catch (error) {
                    document.getElementById('groupsList').innerHTML = `<p style="color: #e74c3c;">Error loading groups: ${error.message}</p>`;
                }
            }
            
            async function toggleMembers(groupId) {
                const membersDiv = document.getElementById(`members-${groupId}`);
                
                if (membersDiv.classList.contains('active')) {
                    membersDiv.classList.remove('active');
                    return;
                }
                
                membersDiv.classList.add('active');
                
                try {
                    const response = await fetch(`/api/groups/${groupId}/members`);
                    const data = await response.json();
                    
                    const availableUsers = allUsers.filter(u => 
                        !data.members.find(m => m.id === u.id)
                    );
                    
                    membersDiv.innerHTML = `
                        <h4 style="margin-bottom: 10px;">👥 Members</h4>
                        <div class="member-list">
                            ${data.members.map(m => `
                                <div class="member-item">
                                    <div class="member-info">
                                        <div class="member-name">${m.name} <span class="member-role role-${m.role}">${m.role}</span></div>
                                        <div class="member-email">${m.email}</div>
                                    </div>
                                    ${m.role !== 'admin' ? `<button class="btn btn-sm btn-danger" onclick="removeMember(${groupId}, ${m.id}, '${m.name}')">Remove</button>` : ''}
                                </div>
                            `).join('')}
                        </div>
                        
                        ${availableUsers.length > 0 ? `
                            <div class="add-member-form">
                                <h4 style="margin-bottom: 10px;">➕ Add Member <span style="background: #4caf50; color: white; padding: 2px 8px; border-radius: 12px; font-size: 0.8em; margin-left: 8px;">${availableUsers.length} available</span></h4>
                                <div style="display: flex; gap: 10px; align-items: flex-end;">
                                    <div class="form-group" style="flex: 1; margin-bottom: 0;">
                                        <select id="newMember-${groupId}" class="form-control">
                                            ${availableUsers.map(u => `<option value="${u.id}">${u.name} (${u.email})</option>`).join('')}
                                        </select>
                                    </div>
                                    <button class="btn" onclick="addMember(${groupId})">Add</button>
                                </div>
                            </div>
                        ` : '<div class="no-users-available"><strong>✅ All users are already members!</strong><br><small>Create more users in the database to add them to this group.</small></div>'}
                    `;
                } catch (error) {
                    membersDiv.innerHTML = `<p style="color: #e74c3c;">Error loading members: ${error.message}</p>`;
                }
            }
            
            async function addMember(groupId) {
                const select = document.getElementById(`newMember-${groupId}`);
                const userId = select.value;
                
                try {
                    const response = await fetch('/api/groups/add-member', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ group_id: groupId, user_id: parseInt(userId), role: 'member' })
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok) {
                        showMessage('✅ Member added successfully!');
                        await loadGroups();
                        setTimeout(() => toggleMembers(groupId), 100);
                    } else {
                        showMessage('❌ ' + (result.error || 'Failed to add member'), 'error');
                    }
                } catch (error) {
                    showMessage('❌ Error: ' + error.message, 'error');
                }
            }
            
            async function removeMember(groupId, userId, userName) {
                if (!confirm(`Remove ${userName} from this group?`)) return;
                
                try {
                    const response = await fetch('/api/groups/remove-member', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ group_id: groupId, user_id: userId })
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok) {
                        showMessage('✅ Member removed successfully!');
                        await loadGroups();
                        setTimeout(() => toggleMembers(groupId), 100);
                    } else {
                        showMessage('❌ ' + (result.error || 'Failed to remove member'), 'error');
                    }
                } catch (error) {
                    showMessage('❌ Error: ' + error.message, 'error');
                }
            }
            
            document.getElementById('createGroupForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const name = document.getElementById('groupName').value;
                const description = document.getElementById('groupDescription').value;
                const selectedMemberId = document.getElementById('groupMembers').value;
                
                try {
                    // First create the group
                    const response = await fetch('/api/groups/create', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ name, description, created_by: 1 })
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok) {
                        const groupId = result.group.id;
                        
                        // If a member was selected, add them to the group
                        if (selectedMemberId) {
                            await fetch('/api/groups/add-member', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ 
                                    group_id: groupId, 
                                    user_id: parseInt(selectedMemberId), 
                                    role: 'member' 
                                })
                            });
                        }
                        
                        showMessage(`✅ Group "${name}" created successfully!`);
                        document.getElementById('createGroupForm').reset();
                        await loadUsers(); // Reload the dropdown
                        loadGroups();
                    } else {
                        showMessage('❌ ' + (result.error || 'Failed to create group'), 'error');
                    }
                } catch (error) {
                    showMessage('❌ Error: ' + error.message, 'error');
                }
            });
            
            // Initialize
            loadUsers();
            loadGroups();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(html)

async def recommendations_page(request):
    """AI-powered recommendations page with chat interface."""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Get Recommendations - Movie Night Planner</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; padding: 20px; }
            .container { max-width: 1200px; margin: 0 auto; }
            .header { background: white; padding: 30px; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); margin-bottom: 30px; }
            .header h1 { color: #333; margin-bottom: 10px; }
            .nav { display: flex; gap: 15px; margin-top: 20px; }
            .nav a { color: #667eea; text-decoration: none; padding: 8px 16px; border-radius: 8px; transition: all 0.3s; }
            .nav a:hover { background: #667eea; color: white; }
            .card { background: white; padding: 25px; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); margin-bottom: 20px; }
            .card h2 { color: #333; margin-bottom: 20px; }
            
            /* Chat Interface */
            .chat-container { background: white; border-radius: 15px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.2); height: 600px; display: flex; flex-direction: column; }
            .chat-messages { flex: 1; overflow-y: auto; padding: 20px; background: #f8f9fa; }
            .message { margin-bottom: 15px; display: flex; gap: 10px; animation: slideIn 0.3s ease; }
            @keyframes slideIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
            .message.user { flex-direction: row-reverse; }
            .message .avatar { width: 40px; height: 40px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 20px; flex-shrink: 0; }
            .message.user .avatar { background: #667eea; color: white; }
            .message.agent .avatar { background: #e8eaf6; color: #667eea; }
            .message .content { max-width: 70%; padding: 12px 16px; border-radius: 12px; }
            .message.user .content { background: #667eea; color: white; border-bottom-right-radius: 4px; }
            .message.agent .content { background: white; color: #333; border-bottom-left-radius: 4px; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
            .message .content .movie-card { margin-top: 10px; padding: 10px; background: rgba(0,0,0,0.03); border-radius: 8px; }
            .message .content .movie-card h4 { margin-bottom: 5px; color: #667eea; }
            .message .content .movie-card p { margin: 3px 0; font-size: 0.9em; }
            
            .chat-input-area { padding: 20px; border-top: 1px solid #e0e0e0; background: white; }
            .chat-input-container { display: flex; gap: 10px; }
            .chat-input { flex: 1; padding: 12px 16px; border: 2px solid #e0e0e0; border-radius: 25px; font-size: 14px; outline: none; transition: all 0.3s; }
            .chat-input:focus { border-color: #667eea; }
            .send-btn { background: #667eea; color: white; border: none; padding: 12px 24px; border-radius: 25px; cursor: pointer; font-size: 16px; transition: all 0.3s; min-width: 100px; }
            .send-btn:hover:not(:disabled) { background: #5568d3; transform: translateY(-2px); }
            .send-btn:disabled { opacity: 0.5; cursor: not-allowed; }
            
            /* Quick prompts */
            .quick-prompts { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 15px; }
            .quick-prompt { background: #e8eaf6; color: #667eea; border: none; padding: 8px 16px; border-radius: 20px; cursor: pointer; font-size: 13px; transition: all 0.3s; }
            .quick-prompt:hover { background: #667eea; color: white; transform: translateY(-2px); }
            
            .typing-indicator { display: none; padding: 12px 16px; background: white; border-radius: 12px; width: fit-content; box-shadow: 0 2px 5px rgba(0,0,0,0.05); }
            .typing-indicator.active { display: block; }
            .typing-indicator span { display: inline-block; width: 8px; height: 8px; background: #667eea; border-radius: 50%; margin: 0 2px; animation: bounce 1.4s infinite; }
            .typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
            .typing-indicator span:nth-child(3) { animation-delay: 0.4s; }
            @keyframes bounce { 0%, 60%, 100% { transform: translateY(0); } 30% { transform: translateY(-10px); } }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎬 AI Movie Recommendations</h1>
                <p style="color: #666; margin-top: 10px;">Chat with our AI agent to discover your next favorite movie</p>
                <div class="nav">
                    <a href="/">🏠 Home</a>
                    <a href="/groups">👫 Groups</a>
                    <a href="/recommendations">🎬 Get Recommendations</a>
                </div>
            </div>
            
            <div class="chat-container">
                <div class="chat-messages" id="chatMessages">
                    <div class="message agent">
                        <div class="avatar">🤖</div>
                        <div class="content">
                            <strong>Movie AI Assistant</strong><br>
                            Hi! I'm your movie recommendation assistant. I can help you discover movies based on your preferences, mood, favorite genres, or similar movies you've enjoyed. What kind of movie are you in the mood for today?
                        </div>
                    </div>
                </div>
                <div class="chat-input-area">
                    <div class="quick-prompts" id="quickPrompts">
                        <button class="quick-prompt" onclick="sendQuickPrompt('Recommend action movies like John Wick')">🎯 Action movies</button>
                        <button class="quick-prompt" onclick="sendQuickPrompt('I want a feel-good comedy')">😊 Feel-good comedy</button>
                        <button class="quick-prompt" onclick="sendQuickPrompt('Suggest sci-fi movies with time travel')">🚀 Sci-fi time travel</button>
                        <button class="quick-prompt" onclick="sendQuickPrompt('I love The Shawshank Redemption, what else should I watch?')">❤️ Movies like favorites</button>
                    </div>
                    <div class="chat-input-container">
                        <input type="text" id="chatInput" class="chat-input" placeholder="Ask for movie recommendations..." onkeypress="if(event.key==='Enter') sendMessage()">
                        <button class="send-btn" id="sendBtn" onclick="sendMessage()">Send 🚀</button>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            async function sendMessage() {
                const input = document.getElementById('chatInput');
                const message = input.value.trim();
                if (!message) return;
                
                // Add user message
                addMessage(message, 'user');
                input.value = '';
                
                // Show typing indicator
                showTyping();
                
                try {
                    // Call MCP tool to get recommendations
                    const response = await fetch('/mcp/tools/call', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            method: 'tools/call',
                            params: {
                                name: 'get_recommendations',
                                arguments: { query: message, user_id: 1 }
                            }
                        })
                    });
                    
                    const result = await response.json();
                    hideTyping();
                    
                    if (result.content && result.content[0]) {
                        const recommendations = JSON.parse(result.content[0].text);
                        displayRecommendations(recommendations);
                    } else {
                        addMessage('Sorry, I couldn\'t find any recommendations. Try a different query!', 'agent');
                    }
                } catch (error) {
                    hideTyping();
                    addMessage('Oops! Something went wrong. Please try again.', 'agent');
                    console.error('Error:', error);
                }
            }
            
            function sendQuickPrompt(prompt) {
                document.getElementById('chatInput').value = prompt;
                sendMessage();
            }
            
            function addMessage(text, sender) {
                const messagesDiv = document.getElementById('chatMessages');
                const messageDiv = document.createElement('div');
                messageDiv.className = `message ${sender}`;
                messageDiv.innerHTML = `
                    <div class="avatar">${sender === 'user' ? '👤' : '🤖'}</div>
                    <div class="content">${text}</div>
                `;
                messagesDiv.appendChild(messageDiv);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            }
            
            function displayRecommendations(recommendations) {
                const messagesDiv = document.getElementById('chatMessages');
                const messageDiv = document.createElement('div');
                messageDiv.className = 'message agent';
                
                let content = '<strong>Here are my recommendations:</strong>';
                
                if (recommendations.movies && recommendations.movies.length > 0) {
                    recommendations.movies.forEach(movie => {
                        content += `
                            <div class="movie-card">
                                <h4>🎬 ${movie.title}</h4>
                                ${movie.tagline ? `<p style="font-style: italic; color: #666;">"${movie.tagline}"</p>` : ''}
                                <p>${movie.overview || 'No description available.'}</p>
                                ${movie.genres ? `<p><strong>Genres:</strong> ${movie.genres.join(', ')}</p>` : ''}
                                ${movie.vote_average ? `<p><strong>Rating:</strong> ⭐ ${movie.vote_average}/10</p>` : ''}
                                ${movie.reason ? `<p><strong>Why this movie:</strong> ${movie.reason}</p>` : ''}
                            </div>
                        `;
                    });
                } else {
                    content += '<p>No movies found matching your criteria. Try a different search!</p>';
                }
                
                messageDiv.innerHTML = `
                    <div class="avatar">🤖</div>
                    <div class="content">${content}</div>
                `;
                messagesDiv.appendChild(messageDiv);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            }
            
            function showTyping() {
                const messagesDiv = document.getElementById('chatMessages');
                const typingDiv = document.createElement('div');
                typingDiv.className = 'message agent';
                typingDiv.id = 'typing-indicator';
                typingDiv.innerHTML = `
                    <div class="avatar">🤖</div>
                    <div class="typing-indicator active">
                        <span></span><span></span><span></span>
                    </div>
                `;
                messagesDiv.appendChild(typingDiv);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
                document.getElementById('sendBtn').disabled = true;
            }
            
            function hideTyping() {
                const typingDiv = document.getElementById('typing-indicator');
                if (typingDiv) typingDiv.remove();
                document.getElementById('sendBtn').disabled = false;
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(html)

async def api_groups(request):
    """Get all groups."""
    try:
        query = """
        SELECT g.id, g.name, g.description, g.created_at,
               u.name as creator_name,
               COUNT(gm.id) as member_count
        FROM groups g
        LEFT JOIN users u ON g.created_by = u.id
        LEFT JOIN group_members gm ON g.id = gm.group_id
        GROUP BY g.id, g.name, g.description, g.created_at, u.name
        ORDER BY g.name
        """
        results = lakebase.run_query(query)
        
        # Convert datetime to string
        for group in results:
            if group.get('created_at'):
                group['created_at'] = group['created_at'].isoformat() if hasattr(group['created_at'], 'isoformat') else str(group['created_at'])
        
        return JSONResponse(results)
    except Exception as e:
        logger.exception(f"Error fetching groups: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_group_members(request):
    """Get members of a specific group."""
    try:
        group_id = request.path_params['group_id']
        
        # Get group info
        group_query = "SELECT id, name FROM groups WHERE id = %s"
        group_info = lakebase.run_query(group_query, (group_id,))
        
        if not group_info:
            return JSONResponse({"error": "Group not found"}, status_code=404)
        
        # Get members
        members_query = """
        SELECT u.id, u.name, u.email, gm.role, gm.joined_at
        FROM group_members gm
        JOIN users u ON gm.user_id = u.id
        WHERE gm.group_id = %s
        ORDER BY gm.role DESC, u.name
        """
        members = lakebase.run_query(members_query, (group_id,))
        
        # Convert datetime to string
        for member in members:
            if member.get('joined_at'):
                member['joined_at'] = member['joined_at'].isoformat() if hasattr(member['joined_at'], 'isoformat') else str(member['joined_at'])
        
        return JSONResponse({
            "group": group_info[0],
            "members": members
        })
    except Exception as e:
        logger.exception(f"Error fetching group members: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_create_group(request):
    """Create a new group."""
    try:
        data = await request.json()
        name = data.get('name')
        description = data.get('description', '')
        created_by = data.get('created_by', 1)  # Default to user 1
        
        if not name:
            return JSONResponse({"error": "Group name is required"}, status_code=400)
        
        # Create group
        lakebase.run_write(
            "INSERT INTO groups (name, description, created_by, created_at) VALUES (%s, %s, %s, %s) RETURNING id",
            (name, description, created_by, datetime.now())
        )
        
        # Get the created group
        group = lakebase.run_query(
            "SELECT id, name, description FROM groups WHERE name = %s ORDER BY id DESC LIMIT 1",
            (name,)
        )[0]
        
        # Add creator as admin
        lakebase.run_write(
            "INSERT INTO group_members (group_id, user_id, role, joined_at) VALUES (%s, %s, 'admin', %s)",
            (group['id'], created_by, datetime.now())
        )
        
        return JSONResponse({"success": True, "group": group})
    except Exception as e:
        logger.exception(f"Error creating group: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_add_member(request):
    """Add a user to a group."""
    try:
        data = await request.json()
        group_id = data.get('group_id')
        user_id = data.get('user_id')
        role = data.get('role', 'member')
        
        if not group_id or not user_id:
            return JSONResponse({"error": "group_id and user_id are required"}, status_code=400)
        
        # Check if already a member
        existing = lakebase.run_query(
            "SELECT id FROM group_members WHERE group_id = %s AND user_id = %s",
            (group_id, user_id)
        )
        
        if existing:
            return JSONResponse({"error": "User is already a member of this group"}, status_code=400)
        
        # Add member
        lakebase.run_write(
            "INSERT INTO group_members (group_id, user_id, role, joined_at) VALUES (%s, %s, %s, %s)",
            (group_id, user_id, role, datetime.now())
        )
        
        return JSONResponse({"success": True, "message": "User added to group"})
    except Exception as e:
        logger.exception(f"Error adding member: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_remove_member(request):
    """Remove a user from a group."""
    try:
        data = await request.json()
        group_id = data.get('group_id')
        user_id = data.get('user_id')
        
        if not group_id or not user_id:
            return JSONResponse({"error": "group_id and user_id are required"}, status_code=400)
        
        # Remove member
        lakebase.run_write(
            "DELETE FROM group_members WHERE group_id = %s AND user_id = %s",
            (group_id, user_id)
        )
        
        return JSONResponse({"success": True, "message": "User removed from group"})
    except Exception as e:
        logger.exception(f"Error removing member: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

async def api_all_users(request):
    """Get all users for selection."""
    try:
        users = lakebase.run_query(
            "SELECT id, name, email FROM users ORDER BY name"
        )
        return JSONResponse(users)
    except Exception as e:
        logger.exception(f"Error fetching users: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

# Create app and add dashboard routes
app = mcp.http_app(stateless_http=True)

# Add dashboard routes at the beginning so they're checked before MCP routes
app.routes.insert(0, Route("/", dashboard_home))
app.routes.insert(1, Route("/groups", groups_page))
app.routes.insert(2, Route("/recommendations", recommendations_page))
app.routes.insert(3, Route("/api/watched-movies", api_watched_movies))
app.routes.insert(4, Route("/api/top-rated", api_top_rated))
app.routes.insert(5, Route("/api/watchlist-stats", api_watchlist_stats))
app.routes.insert(6, Route("/api/rating-distribution", api_rating_distribution))
app.routes.insert(7, Route("/api/groups", api_groups))
app.routes.insert(8, Route("/api/groups/{group_id}/members", api_group_members))
app.routes.insert(9, Route("/api/groups/create", api_create_group, methods=["POST"]))
app.routes.insert(10, Route("/api/groups/add-member", api_add_member, methods=["POST"]))
app.routes.insert(11, Route("/api/groups/remove-member", api_remove_member, methods=["POST"]))
app.routes.insert(12, Route("/api/users", api_all_users))
