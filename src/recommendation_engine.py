"""Movie recommendation engine with agent capabilities."""

from typing import List, Dict, Optional
import json
from db_connection import DatabaseConnection
from embeddings import EmbeddingGenerator


class MovieRecommendationEngine:
    """AI-powered movie recommendation engine for groups."""
    
    def __init__(self):
        """Initialize recommendation engine."""
        self.db = DatabaseConnection()
        self.embedder = EmbeddingGenerator()
    
    def search_movies_semantic(self, query: str, limit: int = 10, group_id: Optional[int] = None) -> List[Dict]:
        """Search for movies using semantic similarity.
        
        Args:
            query: Natural language search query (e.g., "funny sci-fi under 2 hours")
            limit: Maximum number of results
            group_id: Optional group ID to filter out already watched movies
        
        Returns:
            List of matching movies with similarity scores
        """
        # Generate embedding for query
        query_embedding = self.embedder.generate_query_embedding(query)
        
        # Build SQL query
        sql = """
            SELECT 
                m.*,
                1 - (m.embeddings <=> %s::vector) AS similarity_score
            FROM movies m
        """
        
        # If group_id provided, exclude already watched movies
        if group_id:
            sql += """
                LEFT JOIN watchlist_items w ON m.movie_id = w.movie_id 
                    AND w.group_id = %s AND w.watched = true
                WHERE w.watchlist_id IS NULL
            """
            params = (json.dumps(query_embedding), group_id)
        else:
            params = (json.dumps(query_embedding),)
        
        sql += """
            ORDER BY m.embeddings <=> %s::vector
            LIMIT %s
        """
        params = params + (json.dumps(query_embedding), limit)
        
        results = self.db.execute_query(sql, params)
        return results
    
    def get_group_preferences(self, group_id: int) -> Dict:
        """Analyze group preferences based on ratings.
        
        Args:
            group_id: Group ID
        
        Returns:
            Dictionary with group preferences (avg ratings by genre, etc.)
        """
        # Get all ratings from group members
        sql = """
            SELECT 
                m.genres,
                AVG(r.rating) as avg_rating,
                COUNT(*) as rating_count
            FROM ratings r
            JOIN group_members gm ON r.user_id = gm.user_id
            JOIN movies m ON r.movie_id = m.movie_id
            WHERE gm.group_id = %s
            GROUP BY m.genres
            HAVING COUNT(*) >= 2
            ORDER BY avg_rating DESC
        """
        
        genre_prefs = self.db.execute_query(sql, (group_id,))
        
        return {
            "genre_preferences": genre_prefs,
            "group_id": group_id
        }
    
    def recommend_for_group(self, group_id: int, query: str, limit: int = 5) -> List[Dict]:
        """Recommend movies for a group based on query and preferences.
        
        Args:
            group_id: Group ID
            query: Natural language query describing what they want to watch
            limit: Number of recommendations
        
        Returns:
            List of recommended movies with explanations
        """
        # Get semantic matches
        candidates = self.search_movies_semantic(query, limit=limit*3, group_id=group_id)
        
        # Get group preferences
        prefs = self.get_group_preferences(group_id)
        
        # Get movies with negative ratings from group members
        sql = """
            SELECT DISTINCT m.movie_id
            FROM ratings r
            JOIN group_members gm ON r.user_id = gm.user_id
            JOIN movies m ON r.movie_id = m.movie_id
            WHERE gm.group_id = %s AND r.rating < 5
        """
        disliked_movies = self.db.execute_query(sql, (group_id,))
        disliked_ids = {m["movie_id"] for m in disliked_movies}
        
        # Filter and rank candidates
        recommendations = []
        for movie in candidates:
            # Skip disliked movies
            if movie["movie_id"] in disliked_ids:
                continue
            
            # Calculate relevance score
            relevance = movie.get("similarity_score", 0.5)
            
            # Add to recommendations
            recommendations.append({
                **movie,
                "relevance_score": relevance,
                "explanation": self._generate_explanation(movie, query, relevance)
            })
            
            if len(recommendations) >= limit:
                break
        
        # Save recommendations to database
        for rec in recommendations:
            self.db.execute_query(
                """
                INSERT INTO recommendations (group_id, movie_id, query_text, relevance_score, explanation)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (group_id, rec["movie_id"], query, rec["relevance_score"], rec["explanation"]),
                fetch=False
            )
        
        return recommendations
    
    def _generate_explanation(self, movie: Dict, query: str, relevance: float) -> str:
        """Generate explanation for why a movie was recommended.
        
        Args:
            movie: Movie data
            query: User query
            relevance: Relevance score
        
        Returns:
            Explanation string
        """
        parts = []
        
        # Mention high match
        if relevance > 0.8:
            parts.append("Excellent match for your request.")
        elif relevance > 0.6:
            parts.append("Good match for your request.")
        
        # Mention genres
        genres = movie.get("genres")
        if genres:
            if isinstance(genres, str):
                genres = json.loads(genres)
            genre_names = [g["name"] for g in genres[:3] if "name" in g]
            if genre_names:
                parts.append(f"Genres: {', '.join(genre_names)}.")
        
        # Mention runtime
        if movie.get("runtime"):
            parts.append(f"Runtime: {movie['runtime']} minutes.")
        
        # Mention rating
        if movie.get("vote_average"):
            parts.append(f"Rating: {movie['vote_average']}/10.")
        
        return " ".join(parts)
    
    def add_to_watchlist(self, group_id: int, movie_id: int, user_id: int) -> bool:
        """Add a movie to group's watchlist.
        
        Args:
            group_id: Group ID
            movie_id: Movie ID
            user_id: User ID who added it
        
        Returns:
            True if successful
        """
        try:
            self.db.execute_query(
                """
                INSERT INTO watchlist_items (group_id, movie_id, added_by)
                VALUES (%s, %s, %s)
                ON CONFLICT (group_id, movie_id) DO NOTHING
                """,
                (group_id, movie_id, user_id),
                fetch=False
            )
            return True
        except Exception as e:
            print(f"Error adding to watchlist: {e}")
            return False
    
    def record_rating(self, user_id: int, movie_id: int, rating: float, review: Optional[str] = None) -> bool:
        """Record a user's rating for a movie.
        
        Args:
            user_id: User ID
            movie_id: Movie ID
            rating: Rating (0-10)
            review: Optional text review
        
        Returns:
            True if successful
        """
        try:
            self.db.execute_query(
                """
                INSERT INTO ratings (user_id, movie_id, rating, review)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id, movie_id) 
                DO UPDATE SET rating = EXCLUDED.rating, review = EXCLUDED.review, rated_at = CURRENT_TIMESTAMP
                """,
                (user_id, movie_id, rating, review),
                fetch=False
            )
            return True
        except Exception as e:
            print(f"Error recording rating: {e}")
            return False
    
    def mark_as_watched(self, group_id: int, movie_id: int) -> bool:
        """Mark a movie as watched by the group.
        
        Args:
            group_id: Group ID
            movie_id: Movie ID
        
        Returns:
            True if successful
        """
        try:
            self.db.execute_query(
                """
                UPDATE watchlist_items
                SET watched = true, watched_at = CURRENT_TIMESTAMP
                WHERE group_id = %s AND movie_id = %s
                """,
                (group_id, movie_id),
                fetch=False
            )
            return True
        except Exception as e:
            print(f"Error marking as watched: {e}")
            return False
    
    def compare_movies(self, movie_ids: List[int]) -> List[Dict]:
        """Compare multiple movies side by side.
        
        Args:
            movie_ids: List of movie IDs to compare
        
        Returns:
            List of movie details for comparison
        """
        if not movie_ids:
            return []
        
        placeholders = ",".join(["%s"] * len(movie_ids))
        sql = f"""
            SELECT 
                movie_id,
                title,
                genres,
                runtime,
                vote_average,
                overview,
                cast_info
            FROM movies
            WHERE movie_id IN ({placeholders})
        """
        
        results = self.db.execute_query(sql, tuple(movie_ids))
        return results