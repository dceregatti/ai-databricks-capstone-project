"""Movie Ingestion and Embedding Generation Job

This job:
1. Fetches movies from TMDB API
2. Stores/updates them in the movies table (idempotent with UPSERT)
3. Generates semantic search embeddings
4. Stores embeddings in movie_embeddings table (idempotent)

Designed to be run as a Databricks Job with proper error handling and logging.
"""

import sys
import json
import logging
from datetime import datetime
from typing import List, Dict, Optional

# Add MCP server modules to path
sys.path.append('/Workspace/Users/dceregatti@gmail.com/ai-databricks-capstone-project/mcp_server')

import lakebase
import tmdb_client
from sentence_transformers import SentenceTransformer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Job configuration
NUM_PAGES = 5  # Each page has ~20 movies
BATCH_SIZE = 50  # Process embeddings in batches
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


class MovieIngestionJob:
    """Orchestrates movie ingestion and embedding generation."""
    
    def __init__(self):
        self.model: Optional[SentenceTransformer] = None
        self.stats = {
            'movies_fetched': 0,
            'movies_inserted': 0,
            'movies_updated': 0,
            'movies_skipped': 0,
            'embeddings_created': 0,
            'embeddings_updated': 0,
            'errors': 0
        }
    
    def load_embedding_model(self):
        """Load the sentence transformer model (lazy load)."""
        if self.model is None:
            logger.info(f"Loading embedding model: {EMBEDDING_MODEL}")
            self.model = SentenceTransformer(EMBEDDING_MODEL)
            logger.info("Model loaded successfully")
        return self.model
    
    def fetch_popular_movies(self, num_pages: int = NUM_PAGES) -> List[Dict]:
        """Fetch popular movies from TMDB API across multiple pages."""
        logger.info(f"Fetching popular movies from TMDB (pages: {num_pages})...")
        all_movies = []
        
        for page in range(1, num_pages + 1):
            try:
                result = tmdb_client.get_popular_movies(page=page)
                movies = result.get('results', [])
                all_movies.extend(movies)
                logger.info(f"Page {page}/{num_pages}: Fetched {len(movies)} movies")
            except Exception as e:
                logger.error(f"Failed to fetch page {page}: {e}")
                self.stats['errors'] += 1
        
        self.stats['movies_fetched'] = len(all_movies)
        logger.info(f"Total movies fetched: {len(all_movies)}")
        return all_movies
    
    def upsert_movie(self, movie_data: Dict) -> tuple[bool, int]:
        """Insert or update a movie in the database (idempotent).
        
        Returns:
            tuple: (was_inserted, movie_db_id)
        """
        movie_id = movie_data.get('id')
        
        # First, check if movie exists
        existing = lakebase.run_query(
            "SELECT id FROM movies WHERE tmdb_id = %s",
            (movie_id,)
        )
        
        if existing:
            # Update existing movie
            db_id = existing[0]['id']
            lakebase.run_write(
                """
                UPDATE movies SET
                    title = %s,
                    original_title = %s,
                    overview = %s,
                    tagline = %s,
                    release_date = %s,
                    runtime = %s,
                    genres = %s,
                    vote_average = %s,
                    vote_count = %s,
                    popularity = %s,
                    poster_path = %s,
                    backdrop_path = %s,
                    original_language = %s,
                    status = %s,
                    budget = %s,
                    revenue = %s,
                    updated_at = %s
                WHERE tmdb_id = %s
                """,
                (
                    movie_data.get('title'),
                    movie_data.get('original_title'),
                    movie_data.get('overview'),
                    movie_data.get('tagline'),
                    movie_data.get('release_date'),
                    movie_data.get('runtime'),
                    json.dumps([g['name'] for g in movie_data.get('genres', [])]),
                    movie_data.get('vote_average'),
                    movie_data.get('vote_count'),
                    movie_data.get('popularity'),
                    movie_data.get('poster_path'),
                    movie_data.get('backdrop_path'),
                    movie_data.get('original_language'),
                    movie_data.get('status'),
                    movie_data.get('budget'),
                    movie_data.get('revenue'),
                    datetime.now(),
                    movie_id
                )
            )
            self.stats['movies_updated'] += 1
            return False, db_id
        else:
            # Insert new movie
            lakebase.run_write(
                """
                INSERT INTO movies (
                    tmdb_id, title, original_title, overview, tagline,
                    release_date, runtime, genres, vote_average, vote_count,
                    popularity, poster_path, backdrop_path, original_language,
                    status, budget, revenue, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    movie_id,
                    movie_data.get('title'),
                    movie_data.get('original_title'),
                    movie_data.get('overview'),
                    movie_data.get('tagline'),
                    movie_data.get('release_date'),
                    movie_data.get('runtime'),
                    json.dumps([g['name'] for g in movie_data.get('genres', [])]),
                    movie_data.get('vote_average'),
                    movie_data.get('vote_count'),
                    movie_data.get('popularity'),
                    movie_data.get('poster_path'),
                    movie_data.get('backdrop_path'),
                    movie_data.get('original_language'),
                    movie_data.get('status'),
                    movie_data.get('budget'),
                    movie_data.get('revenue'),
                    datetime.now(),
                    datetime.now()
                )
            )
            # Get the inserted ID
            result = lakebase.run_query(
                "SELECT id FROM movies WHERE tmdb_id = %s",
                (movie_id,)
            )
            db_id = result[0]['id']
            self.stats['movies_inserted'] += 1
            return True, db_id
    
    def create_movie_context(self, movie: Dict) -> str:
        """Create rich text representation for embedding generation.
        
        Combines multiple fields into a single context string optimized for
        semantic search.
        """
        parts = []
        
        if movie.get('title'):
            parts.append(f"Title: {movie['title']}")
        
        if movie.get('overview'):
            parts.append(f"Plot: {movie['overview']}")
        
        if movie.get('tagline'):
            parts.append(f"Tagline: {movie['tagline']}")
        
        genres = [g['name'] if isinstance(g, dict) else g 
                  for g in (json.loads(movie.get('genres', '[]')) 
                           if isinstance(movie.get('genres'), str) 
                           else movie.get('genres', []))]
        if genres:
            parts.append(f"Genres: {', '.join(genres)}")
        
        # Get keywords if available
        try:
            keywords_data = tmdb_client.get_movie_keywords(movie.get('id'))
            keywords = [kw['name'] for kw in keywords_data.get('keywords', [])][:10]
            if keywords:
                parts.append(f"Keywords: {', '.join(keywords)}")
        except Exception as e:
            logger.debug(f"Could not fetch keywords for {movie.get('title')}: {e}")
        
        # Get top cast if available
        try:
            credits = tmdb_client.get_movie_credits(movie.get('id'))
            top_cast = [actor['name'] for actor in credits.get('cast', [])[:5]]
            if top_cast:
                parts.append(f"Cast: {', '.join(top_cast)}")
        except Exception as e:
            logger.debug(f"Could not fetch cast for {movie.get('title')}: {e}")
        
        return " | ".join(parts)
    
    def upsert_embedding(self, movie_id: int, embedding: List[float]) -> bool:
        """Insert or update movie embedding (idempotent).
        
        Returns:
            bool: True if inserted, False if updated
        """
        # Format embedding as PostgreSQL array
        embedding_str = '[' + ','.join(map(str, embedding)) + ']'
        
        # Use INSERT ... ON CONFLICT for true idempotence
        lakebase.run_write(
            """
            INSERT INTO movie_embeddings (movie_id, embedding, embedding_model, created_at)
            VALUES (%s, %s::vector, %s, %s)
            ON CONFLICT (movie_id) 
            DO UPDATE SET 
                embedding = EXCLUDED.embedding,
                embedding_model = EXCLUDED.embedding_model,
                created_at = EXCLUDED.created_at
            """,
            (movie_id, embedding_str, EMBEDDING_MODEL, datetime.now())
        )
        
        # Check if it was an insert or update by querying the table
        # (Note: In production, you'd use RETURNING clause, but keeping it simple)
        return True
    
    def process_movies(self, movies: List[Dict]):
        """Process all movies: store in DB and generate embeddings."""
        logger.info(f"Processing {len(movies)} movies...")
        enriched_movies = []
        
        for i, movie in enumerate(movies, 1):
            movie_id = movie.get('id')
            title = movie.get('title', 'Unknown')
            
            try:
                # Fetch full details
                enriched = tmdb_client.get_movie_details(movie_id)
                
                # Upsert movie
                was_inserted, db_id = self.upsert_movie(enriched)
                
                # Store for embedding generation
                enriched['db_id'] = db_id
                enriched_movies.append(enriched)
                
                if i % 10 == 0:
                    logger.info(f"[{i}/{len(movies)}] Processed: {title}")
            
            except Exception as e:
                logger.error(f"Failed to process movie {title} (ID: {movie_id}): {e}")
                self.stats['movies_skipped'] += 1
                self.stats['errors'] += 1
        
        logger.info(f"Movies processed: {len(enriched_movies)}")
        return enriched_movies
    
    def generate_and_store_embeddings(self, movies: List[Dict]):
        """Generate embeddings for all movies and store them."""
        logger.info(f"Generating embeddings for {len(movies)} movies...")
        model = self.load_embedding_model()
        
        for i in range(0, len(movies), BATCH_SIZE):
            batch = movies[i:i + BATCH_SIZE]
            logger.info(f"Processing batch {i//BATCH_SIZE + 1}/{(len(movies) + BATCH_SIZE - 1)//BATCH_SIZE}")
            
            # Create contexts for batch
            contexts = [self.create_movie_context(movie) for movie in batch]
            
            # Generate embeddings in batch
            embeddings = model.encode(contexts, show_progress_bar=False)
            
            # Store embeddings
            for movie, embedding in zip(batch, embeddings):
                try:
                    tmdb_id = movie.get('id')
                    self.upsert_embedding(tmdb_id, embedding.tolist())
                    self.stats['embeddings_created'] += 1
                except Exception as e:
                    logger.error(f"Failed to store embedding for {movie.get('title')}: {e}")
                    self.stats['errors'] += 1
        
        logger.info(f"Embeddings generated: {self.stats['embeddings_created']}")
    
    def run(self):
        """Execute the full job pipeline."""
        start_time = datetime.now()
        logger.info("=" * 80)
        logger.info("Movie Ingestion and Embedding Generation Job - STARTED")
        logger.info(f"Start time: {start_time}")
        logger.info("=" * 80)
        
        try:
            # Step 1: Fetch movies
            movies = self.fetch_popular_movies(NUM_PAGES)
            
            if not movies:
                logger.warning("No movies fetched. Exiting.")
                return
            
            # Step 2: Process and store movies
            enriched_movies = self.process_movies(movies)
            
            if not enriched_movies:
                logger.warning("No movies enriched. Exiting.")
                return
            
            # Step 3: Generate and store embeddings
            self.generate_and_store_embeddings(enriched_movies)
            
            # Report statistics
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            
            logger.info("=" * 80)
            logger.info("Job completed successfully!")
            logger.info(f"Duration: {duration:.2f} seconds")
            logger.info("")
            logger.info("Statistics:")
            logger.info(f"  Movies fetched: {self.stats['movies_fetched']}")
            logger.info(f"  Movies inserted: {self.stats['movies_inserted']}")
            logger.info(f"  Movies updated: {self.stats['movies_updated']}")
            logger.info(f"  Movies skipped: {self.stats['movies_skipped']}")
            logger.info(f"  Embeddings created/updated: {self.stats['embeddings_created']}")
            logger.info(f"  Errors: {self.stats['errors']}")
            logger.info("=" * 80)
        
        except Exception as e:
            logger.error(f"Job failed with error: {e}", exc_info=True)
            raise


if __name__ == "__main__":
    job = MovieIngestionJob()
    job.run()
