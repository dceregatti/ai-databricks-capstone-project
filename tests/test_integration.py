"""Integration Tests for Movie Night Planner MCP Server

Tests the full end-to-end pipeline:
1. Seed movies from TMDB
2. Generate embeddings
3. Test semantic search

Run after deploying the MCP server and initializing the database.
"""

import sys
import json
import logging
from datetime import datetime

# Add MCP server modules to path
sys.path.append('/Workspace/Users/dceregatti@gmail.com/ai-databricks-capstone-project/mcp_server')

import lakebase
import tmdb_client
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IntegrationTest:
    """End-to-end integration test suite."""
    
    def __init__(self):
        self.model = None
        self.test_movies = [
            "The Shawshank Redemption",
            "Inception"
        ]
        self.test_movie_ids = []
    
    def load_model(self):
        """Load embedding model."""
        if self.model is None:
            logger.info("Loading embedding model...")
            self.model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')
        return self.model
    
    def test_1_database_connection(self):
        """Test 1: Verify database connection."""
        logger.info("\n" + "=" * 80)
        logger.info("TEST 1: Database Connection")
        logger.info("=" * 80)
        
        try:
            result = lakebase.run_query("SELECT 1 as test")
            assert result[0]['test'] == 1
            logger.info("✅ Database connection successful")
            return True
        except Exception as e:
            logger.error(f"❌ Database connection failed: {e}")
            return False
    
    def test_2_tmdb_api(self):
        """Test 2: Verify TMDB API connection."""
        logger.info("\n" + "=" * 80)
        logger.info("TEST 2: TMDB API Connection")
        logger.info("=" * 80)
        
        try:
            result = tmdb_client.search_movies("Inception")
            assert result.get('results'), "No results from TMDB search"
            logger.info(f"✅ TMDB API working (found {len(result['results'])} results)")
            return True
        except Exception as e:
            logger.error(f"❌ TMDB API failed: {e}")
            return False
    
    def test_3_seed_movies(self):
        """Test 3: Seed test movies into database."""
        logger.info("\n" + "=" * 80)
        logger.info("TEST 3: Seed Test Movies")
        logger.info("=" * 80)
        
        seeded = 0
        
        for title in self.test_movies:
            try:
                # Search for movie
                search_result = tmdb_client.search_movies(title)
                if not search_result.get('results'):
                    logger.warning(f"⚠️  Movie not found on TMDB: {title}")
                    continue
                
                movie = search_result['results'][0]
                movie_id = movie['id']
                
                # Fetch full details
                details = tmdb_client.get_movie_details(movie_id)
                
                # Check if exists
                existing = lakebase.run_query(
                    "SELECT id FROM movies WHERE tmdb_id = %s",
                    (movie_id,)
                )
                
                if existing:
                    logger.info(f"⏭️  Already exists: {title}")
                    self.test_movie_ids.append(movie_id)
                    continue
                
                # Insert movie
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
                        details.get('id'),
                        details.get('title'),
                        details.get('original_title'),
                        details.get('overview'),
                        details.get('tagline'),
                        details.get('release_date'),
                        details.get('runtime'),
                        json.dumps([g['name'] for g in details.get('genres', [])]),
                        details.get('vote_average'),
                        details.get('vote_count'),
                        details.get('popularity'),
                        details.get('poster_path'),
                        details.get('backdrop_path'),
                        details.get('original_language'),
                        details.get('status'),
                        details.get('budget'),
                        details.get('revenue'),
                        datetime.now(),
                        datetime.now()
                    )
                )
                
                self.test_movie_ids.append(movie_id)
                seeded += 1
                logger.info(f"✅ Seeded: {title}")
            
            except Exception as e:
                logger.error(f"❌ Failed to seed {title}: {e}")
        
        logger.info(f"\nSeeded {seeded} new movies, {len(self.test_movie_ids)} total test movies")
        return len(self.test_movie_ids) > 0
    
    def test_4_generate_embeddings(self):
        """Test 4: Generate embeddings for test movies."""
        logger.info("\n" + "=" * 80)
        logger.info("TEST 4: Generate Embeddings")
        logger.info("=" * 80)
        
        model = self.load_model()
        generated = 0
        
        for tmdb_id in self.test_movie_ids:
            try:
                # Get movie details
                movie = lakebase.run_query(
                    "SELECT * FROM movies WHERE tmdb_id = %s",
                    (tmdb_id,)
                )[0]
                
                # Create context
                context_parts = []
                if movie.get('title'):
                    context_parts.append(f"Title: {movie['title']}")
                if movie.get('overview'):
                    context_parts.append(f"Plot: {movie['overview']}")
                if movie.get('genres'):
                    genres = json.loads(movie['genres']) if isinstance(movie['genres'], str) else movie['genres']
                    context_parts.append(f"Genres: {', '.join(genres)}")
                
                context = " | ".join(context_parts)
                
                # Generate embedding
                embedding = model.encode(context).tolist()
                embedding_str = '[' + ','.join(map(str, embedding)) + ']'
                
                # Store embedding
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
                    (tmdb_id, embedding_str, 'sentence-transformers/all-MiniLM-L6-v2', datetime.now())
                )
                
                generated += 1
                logger.info(f"✅ Generated embedding for: {movie['title']}")
            
            except Exception as e:
                logger.error(f"❌ Failed to generate embedding for movie ID {tmdb_id}: {e}")
        
        logger.info(f"\nGenerated {generated} embeddings")
        return generated > 0
    
    def test_5_semantic_search(self):
        """Test 5: Test semantic search."""
        logger.info("\n" + "=" * 80)
        logger.info("TEST 5: Semantic Search")
        logger.info("=" * 80)
        
        model = self.load_model()
        
        test_queries = [
            "mind-bending heist movie",
            "prison escape drama",
            "dream thriller"
        ]
        
        all_passed = True
        
        for query in test_queries:
            try:
                logger.info(f"\nQuery: '{query}'")
                
                # Generate query embedding
                query_embedding = model.encode(query).tolist()
                embedding_str = '[' + ','.join(map(str, query_embedding)) + ']'
                
                # Perform semantic search
                results = lakebase.run_query(
                    """
                    SELECT 
                        m.title,
                        m.overview,
                        m.genres,
                        1 - (me.embedding <=> %s::vector) as similarity
                    FROM movies m
                    JOIN movie_embeddings me ON m.tmdb_id = me.movie_id
                    ORDER BY me.embedding <=> %s::vector
                    LIMIT 3
                    """,
                    (embedding_str, embedding_str)
                )
                
                if not results:
                    logger.error("❌ No results returned")
                    all_passed = False
                    continue
                
                logger.info(f"Found {len(results)} results:")
                for i, result in enumerate(results, 1):
                    logger.info(f"  {i}. {result['title']} (similarity: {result['similarity']:.3f})")
                
                logger.info("✅ Search successful")
            
            except Exception as e:
                logger.error(f"❌ Search failed: {e}")
                all_passed = False
        
        return all_passed
    
    def run_all_tests(self):
        """Run the complete test suite."""
        logger.info("\n" + "#" * 80)
        logger.info("# INTEGRATION TEST SUITE - Movie Night Planner MCP Server")
        logger.info("#" * 80)
        
        tests = [
            ("Database Connection", self.test_1_database_connection),
            ("TMDB API", self.test_2_tmdb_api),
            ("Seed Movies", self.test_3_seed_movies),
            ("Generate Embeddings", self.test_4_generate_embeddings),
            ("Semantic Search", self.test_5_semantic_search)
        ]
        
        results = []
        
        for test_name, test_func in tests:
            try:
                passed = test_func()
                results.append((test_name, passed))
            except Exception as e:
                logger.error(f"❌ Test '{test_name}' crashed: {e}")
                results.append((test_name, False))
        
        # Summary
        logger.info("\n" + "#" * 80)
        logger.info("# TEST SUMMARY")
        logger.info("#" * 80)
        
        passed_count = sum(1 for _, passed in results if passed)
        total_count = len(results)
        
        for test_name, passed in results:
            status = "✅ PASS" if passed else "❌ FAIL"
            logger.info(f"{status} - {test_name}")
        
        logger.info("\n" + "=" * 80)
        logger.info(f"Result: {passed_count}/{total_count} tests passed")
        
        if passed_count == total_count:
            logger.info("🎉 ALL TESTS PASSED! System is operational.")
        else:
            logger.error(f"⚠️  {total_count - passed_count} test(s) failed. Check logs above.")
        
        logger.info("=" * 80)
        
        return passed_count == total_count


if __name__ == "__main__":
    test_suite = IntegrationTest()
    success = test_suite.run_all_tests()
    sys.exit(0 if success else 1)
