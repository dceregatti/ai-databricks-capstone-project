# Databricks notebook source
# DBTITLE 1,Introduction
# MAGIC %md
# MAGIC # Context Engineering for Movie Semantic Search
# MAGIC
# MAGIC This notebook demonstrates how to build a semantic search system for movies using:
# MAGIC
# MAGIC 1. **TMDB API** - Fetch rich movie metadata
# MAGIC 2. **Context Engineering** - Combine multiple fields into rich text representations
# MAGIC 3. **Sentence Transformers** - Generate embeddings from text
# MAGIC 4. **pgvector** - Store and search embeddings in Postgres
# MAGIC
# MAGIC ## Pipeline Overview
# MAGIC
# MAGIC ```
# MAGIC TMDB API → Movie Metadata → Rich Context → Embeddings → pgvector → Semantic Search
# MAGIC ```
# MAGIC
# MAGIC ## What You'll Learn
# MAGIC
# MAGIC * How to fetch comprehensive movie data from TMDB
# MAGIC * How to engineer rich text contexts for better embeddings
# MAGIC * How to generate and store embeddings at scale
# MAGIC * How to perform semantic search with natural language queries
# MAGIC
# MAGIC Let's get started! 🎬

# COMMAND ----------

# DBTITLE 1,Setup and Imports
import sys
import json
from datetime import datetime

# Add MCP server modules to path
sys.path.append('/Workspace/Users/dceregatti@gmail.com/ai-databricks-capstone-project/mcp_server')

import lakebase
import tmdb_client

from sentence_transformers import SentenceTransformer

print("✅ Imports successful")
print(f"📅 Timestamp: {datetime.now()}")

# COMMAND ----------

# DBTITLE 1,Step 1: Fetch Movies from TMDB
# MAGIC %md
# MAGIC ## Step 1: Fetch Movies from TMDB API
# MAGIC
# MAGIC We'll fetch popular movies with comprehensive metadata including:
# MAGIC * Basic info (title, overview, genres)
# MAGIC * Keywords (thematic tags)
# MAGIC * Cast and crew (top actors, director)
# MAGIC * Reviews and ratings
# MAGIC
# MAGIC This rich metadata will help us create better text representations for embeddings.

# COMMAND ----------

# DBTITLE 1,Fetch Popular Movies
# Configuration
NUM_PAGES = 5  # Each page has ~20 movies, so 5 pages = ~100 movies
BATCH_SIZE = 50  # Process embeddings in batches

print(f"🎬 Fetching popular movies from TMDB...")
print(f"   Pages to fetch: {NUM_PAGES}")
print()

# Fetch popular movies across multiple pages
all_movies = []
for page in range(1, NUM_PAGES + 1):
    try:
        result = tmdb_client.get_popular_movies(page=page)
        movies = result.get('results', [])
        all_movies.extend(movies)
        print(f"   Page {page}/{NUM_PAGES}: Fetched {len(movies)} movies")
    except Exception as e:
        print(f"   ⚠️  Error on page {page}: {e}")
        continue

print()
print(f"✅ Total movies fetched: {len(all_movies)}")
print()
print("Sample movie:")
if all_movies:
    sample = all_movies[0]
    print(f"  Title: {sample.get('title')}")
    print(f"  ID: {sample.get('id')}")
    print(f"  Rating: {sample.get('vote_average')}/10")
    print(f"  Overview: {sample.get('overview', 'N/A')[:100]}...")

# COMMAND ----------

# DBTITLE 1,Step 2: Enrich and Store Movies
# MAGIC %md
# MAGIC ## Step 2: Enrich Movies with Detailed Metadata
# MAGIC
# MAGIC For each movie, we'll:
# MAGIC 1. Fetch full details (including keywords, cast, crew)
# MAGIC 2. Store the movie in the `movies` table
# MAGIC 3. Prepare rich context for embedding generation
# MAGIC
# MAGIC We'll process in batches and handle errors gracefully.

# COMMAND ----------

# DBTITLE 1,Store Movies in Database
print("💾 Storing movies in database...")
print()

stored_count = 0
skipped_count = 0
enriched_movies = []

for i, movie in enumerate(all_movies, 1):
    movie_id = movie.get('id')
    
    try:
        # Check if movie already exists
        existing = lakebase.run_query(
            "SELECT id FROM movies WHERE tmdb_id = %s",
            (movie_id,)
        )
        
        if existing:
            # Just fetch the enriched version for embedding
            enriched = tmdb_client.get_movie_details(movie_id)
            enriched_movies.append(enriched)
            if i % 10 == 0:
                print(f"   [{i}/{len(all_movies)}] Already exists: {movie.get('title')}")
            continue
        
        # Fetch full details
        enriched = tmdb_client.get_movie_details(movie_id)
        
        # Insert into database
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
                enriched.get('id'),
                enriched.get('title'),
                enriched.get('original_title'),
                enriched.get('overview'),
                enriched.get('tagline'),
                enriched.get('release_date'),
                enriched.get('runtime'),
                json.dumps([g['name'] for g in enriched.get('genres', [])]),
                enriched.get('vote_average'),
                enriched.get('vote_count'),
                enriched.get('popularity'),
                enriched.get('poster_path'),
                enriched.get('backdrop_path'),
                enriched.get('original_language'),
                enriched.get('status'),
                enriched.get('budget'),
                enriched.get('revenue'),
                datetime.now(),
                datetime.now()
            )
        )
        
        enriched_movies.append(enriched)
        stored_count += 1
        
        if i % 10 == 0:
            print(f"   [{i}/{len(all_movies)}] Stored: {enriched.get('title')}")
    
    except Exception as e:
        skipped_count += 1
        print(f"   ⚠️  Skipped {movie.get('title', 'unknown')}: {e}")
        continue

print()
print(f"✅ Stored: {stored_count} movies")
print(f"🔄 Already existed: {len(all_movies) - stored_count - skipped_count}")
print(f"⚠️  Skipped: {skipped_count} movies")
print(f"📊 Total enriched: {len(enriched_movies)} movies ready for embedding")

# COMMAND ----------

# DBTITLE 1,Step 3: Context Engineering
# MAGIC %md
# MAGIC ## Step 3: Context Engineering - Creating Rich Text Representations
# MAGIC
# MAGIC **This is the most important step!**
# MAGIC
# MAGIC We'll combine multiple metadata fields into a single rich text representation:
# MAGIC
# MAGIC * **Title** - The movie name
# MAGIC * **Overview** - Plot summary
# MAGIC * **Genres** - Action, Comedy, Drama, etc.
# MAGIC * **Keywords** - Thematic tags (time-travel, heist, romance)
# MAGIC * **Cast** - Top 5 actors
# MAGIC * **Director** - Who directed it
# MAGIC * **Tagline** - Marketing tagline
# MAGIC
# MAGIC By combining these, our embeddings will capture:
# MAGIC - Plot themes
# MAGIC - Genre classification  
# MAGIC - Casting style
# MAGIC - Directorial style
# MAGIC - Thematic elements
# MAGIC
# MAGIC This creates **context-rich** embeddings that enable semantic search like:
# MAGIC - "a funny sci-fi movie about time travel"
# MAGIC - "action thriller with Tom Cruise"
# MAGIC - "Oscar-winning drama by Christopher Nolan"

# COMMAND ----------

# DBTITLE 1,Create Rich Context Function
def create_movie_context(movie: dict) -> str:
    """
    Create a rich text representation of a movie by combining multiple fields.
    
    This is context engineering - we're crafting the input that will be embedded
    to maximize semantic search quality.
    """
    parts = []
    
    # Title
    if movie.get('title'):
        parts.append(f"Title: {movie['title']}")
    
    # Overview (plot summary)
    if movie.get('overview'):
        parts.append(f"Plot: {movie['overview']}")
    
    # Genres
    genres = movie.get('genres', [])
    if genres:
        genre_names = [g['name'] for g in genres]
        parts.append(f"Genres: {', '.join(genre_names)}")
    
    # Keywords (thematic tags)
    keywords = movie.get('keywords', {}).get('keywords', [])
    if keywords:
        keyword_names = [k['name'] for k in keywords[:10]]  # Top 10 keywords
        parts.append(f"Themes: {', '.join(keyword_names)}")
    
    # Cast (top 5 actors)
    cast = movie.get('credits', {}).get('cast', [])
    if cast:
        top_actors = [actor['name'] for actor in cast[:5]]
        parts.append(f"Starring: {', '.join(top_actors)}")
    
    # Director
    crew = movie.get('credits', {}).get('crew', [])
    directors = [person['name'] for person in crew if person.get('job') == 'Director']
    if directors:
        parts.append(f"Directed by: {', '.join(directors)}")
    
    # Tagline
    if movie.get('tagline'):
        parts.append(f"Tagline: {movie['tagline']}")
    
    # Combine everything with newlines
    context = "\n".join(parts)
    
    return context


# Test with first movie
if enriched_movies:
    sample_context = create_movie_context(enriched_movies[0])
    print("📝 Sample Rich Context:")
    print("=" * 70)
    print(sample_context)
    print("=" * 70)
    print()
    print(f"📊 Context length: {len(sample_context)} characters")

# COMMAND ----------

# DBTITLE 1,Step 4: Generate Embeddings
# MAGIC %md
# MAGIC ## Step 4: Generate Embeddings
# MAGIC
# MAGIC We'll use **sentence-transformers/all-MiniLM-L6-v2**:
# MAGIC * Fast and efficient (384 dimensions)
# MAGIC * Good for semantic similarity
# MAGIC * Balanced performance/size tradeoff
# MAGIC
# MAGIC The model converts our rich text contexts into dense vectors that capture semantic meaning.

# COMMAND ----------

# DBTITLE 1,Load Embedding Model
print("🧪 Loading embedding model...")
print("   Model: sentence-transformers/all-MiniLM-L6-v2")
print("   Dimensions: 384")
print()

model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

print("✅ Model loaded successfully")
print()

# Test embedding generation
test_text = "A sci-fi action movie about space travel"
test_embedding = model.encode(test_text)

print(f"🧪 Test embedding:")
print(f"   Input: '{test_text}'")
print(f"   Output shape: {test_embedding.shape}")
print(f"   First 5 values: {test_embedding[:5]}")

# COMMAND ----------

# DBTITLE 1,Generate and Store Embeddings
print("🧪 Generating embeddings for all movies...")
print(f"   Processing {len(enriched_movies)} movies in batches of {BATCH_SIZE}")
print()

embedding_stored = 0
embedding_skipped = 0
embedding_updated = 0

for i in range(0, len(enriched_movies), BATCH_SIZE):
    batch = enriched_movies[i:i + BATCH_SIZE]
    batch_num = (i // BATCH_SIZE) + 1
    total_batches = (len(enriched_movies) + BATCH_SIZE - 1) // BATCH_SIZE
    
    print(f"📦 Batch {batch_num}/{total_batches}: Processing {len(batch)} movies")
    
    for movie in batch:
        movie_id = movie.get('id')
        
        try:
            # Check if embedding already exists
            existing = lakebase.run_query(
                "SELECT id FROM movie_embeddings WHERE movie_id = %s",
                (movie_id,)
            )
            
            if existing:
                embedding_skipped += 1
                continue
            
            # Create rich context
            context = create_movie_context(movie)
            
            # Generate embedding
            embedding = model.encode(context)
            
            # Convert to list for Postgres
            embedding_list = embedding.tolist()
            
            # Store in database
            lakebase.run_write(
                """
                INSERT INTO movie_embeddings (movie_id, embedding, embedding_model, created_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (movie_id) DO UPDATE SET
                    embedding = EXCLUDED.embedding,
                    embedding_model = EXCLUDED.embedding_model,
                    created_at = EXCLUDED.created_at
                """,
                (movie_id, embedding_list, 'all-MiniLM-L6-v2', datetime.now())
            )
            
            embedding_stored += 1
            
        except Exception as e:
            embedding_skipped += 1
            print(f"   ⚠️  Error for {movie.get('title', 'unknown')}: {e}")
            continue
    
    print(f"   ✅ Batch complete: {embedding_stored} stored, {embedding_skipped} skipped")
    print()

print("=" * 70)
print(f"✅ Embedding generation complete!")
print(f"   Stored: {embedding_stored}")
print(f"   Skipped: {embedding_skipped}")
print("=" * 70)

# COMMAND ----------

# DBTITLE 1,Step 5: Verify Database
# MAGIC %md
# MAGIC ## Step 5: Verify Database
# MAGIC
# MAGIC Let's check that everything was stored correctly in Postgres with pgvector.

# COMMAND ----------

# DBTITLE 1,Verify Tables
print("🔍 Verifying database contents...")
print()

# Check movies table
movie_count = lakebase.run_query("SELECT COUNT(*) as count FROM movies")[0]['count']
print(f"🎬 Movies table: {movie_count} movies")

# Check embeddings table
embedding_count = lakebase.run_query("SELECT COUNT(*) as count FROM movie_embeddings")[0]['count']
print(f"🧪 Embeddings table: {embedding_count} embeddings")

print()

# Show sample movies with embeddings
print("Sample movies with embeddings:")
print("=" * 70)

samples = lakebase.run_query("""
    SELECT m.title, m.release_date, m.vote_average,
           ARRAY_LENGTH(e.embedding, 1) as embedding_dim
    FROM movies m
    JOIN movie_embeddings e ON m.tmdb_id = e.movie_id
    ORDER BY m.popularity DESC
    LIMIT 5
""")

for i, movie in enumerate(samples, 1):
    print(f"{i}. {movie['title']} ({movie['release_date'][:4] if movie['release_date'] else 'N/A'})")
    print(f"   Rating: {movie['vote_average']}/10 | Embedding: {movie['embedding_dim']} dimensions")

print("=" * 70)

# COMMAND ----------

# DBTITLE 1,Step 6: Semantic Search Demo
# MAGIC %md
# MAGIC ## Step 6: Semantic Search Demo 🔍
# MAGIC
# MAGIC Now for the magic! We'll test semantic search with natural language queries.
# MAGIC
# MAGIC ### How It Works
# MAGIC
# MAGIC 1. User enters a natural language query (e.g., "a funny sci-fi movie about time travel")
# MAGIC 2. We generate an embedding for the query using the same model
# MAGIC 3. pgvector finds movies with similar embeddings using **cosine similarity**
# MAGIC 4. Results are ranked by similarity score
# MAGIC
# MAGIC The beauty: **No keyword matching!** The embeddings capture semantic meaning.

# COMMAND ----------

# DBTITLE 1,Semantic Search Function
def semantic_search(query: str, limit: int = 10):
    """
    Perform semantic search for movies using natural language.
    
    Args:
        query: Natural language description (e.g., "a funny sci-fi movie")
        limit: Maximum number of results
    
    Returns:
        List of matching movies with similarity scores
    """
    print(f"🔎 Searching for: '{query}'")
    print()
    
    # Generate embedding for the query
    query_embedding = model.encode(query)
    query_embedding_list = query_embedding.tolist()
    
    # Search using pgvector cosine similarity
    results = lakebase.run_query(
        """
        SELECT 
            m.title,
            m.release_date,
            m.overview,
            m.genres,
            m.vote_average,
            m.runtime,
            1 - (e.embedding <=> %s::vector) as similarity
        FROM movies m
        JOIN movie_embeddings e ON m.tmdb_id = e.movie_id
        ORDER BY e.embedding <=> %s::vector
        LIMIT %s
        """,
        (query_embedding_list, query_embedding_list, limit)
    )
    
    return results


print("✅ Semantic search function ready!")

# COMMAND ----------

# DBTITLE 1,Test Query 1: Funny Sci-Fi Time Travel
# Test 1: Funny sci-fi about time travel
results = semantic_search("a funny sci-fi movie about time travel", limit=5)

print("=" * 70)
print("TOP RESULTS:")
print("=" * 70)
print()

for i, movie in enumerate(results, 1):
    genres = json.loads(movie['genres']) if isinstance(movie['genres'], str) else movie['genres']
    year = movie['release_date'][:4] if movie['release_date'] else 'N/A'
    
    print(f"{i}. {movie['title']} ({year})")
    print(f"   Similarity: {movie['similarity']:.4f}")
    print(f"   Rating: {movie['vote_average']}/10")
    print(f"   Genres: {', '.join(genres)}")
    print(f"   Runtime: {movie['runtime']} min")
    print(f"   Plot: {movie['overview'][:150]}...")
    print()

# COMMAND ----------

# DBTITLE 1,Test Query 2: Action Thriller
# Test 2: Action thriller with espionage
results = semantic_search("action thriller with spies and espionage", limit=5)

print("=" * 70)
print("🔎 Query: 'action thriller with spies and espionage'")
print("=" * 70)
print()

for i, movie in enumerate(results, 1):
    genres = json.loads(movie['genres']) if isinstance(movie['genres'], str) else movie['genres']
    year = movie['release_date'][:4] if movie['release_date'] else 'N/A'
    
    print(f"{i}. {movie['title']} ({year}) - Similarity: {movie['similarity']:.4f}")
    print(f"   Genres: {', '.join(genres)} | Rating: {movie['vote_average']}/10")
    print()

# COMMAND ----------

# DBTITLE 1,Test Query 3: Animated Family Adventure
# Test 3: Animated family adventure
results = semantic_search("animated family movie with adventure and magic", limit=5)

print("=" * 70)
print("🔎 Query: 'animated family movie with adventure and magic'")
print("=" * 70)
print()

for i, movie in enumerate(results, 1):
    genres = json.loads(movie['genres']) if isinstance(movie['genres'], str) else movie['genres']
    year = movie['release_date'][:4] if movie['release_date'] else 'N/A'
    
    print(f"{i}. {movie['title']} ({year}) - Similarity: {movie['similarity']:.4f}")
    print(f"   Genres: {', '.join(genres)} | Rating: {movie['vote_average']}/10")
    print()

# COMMAND ----------

# DBTITLE 1,Test Query 4: Emotional Drama
# Test 4: Emotional drama
results = semantic_search("emotional drama about love and loss", limit=5)

print("=" * 70)
print("🔎 Query: 'emotional drama about love and loss'")
print("=" * 70)
print()

for i, movie in enumerate(results, 1):
    genres = json.loads(movie['genres']) if isinstance(movie['genres'], str) else movie['genres']
    year = movie['release_date'][:4] if movie['release_date'] else 'N/A'
    
    print(f"{i}. {movie['title']} ({year}) - Similarity: {movie['similarity']:.4f}")
    print(f"   Genres: {', '.join(genres)} | Rating: {movie['vote_average']}/10")
    print()

# COMMAND ----------

# DBTITLE 1,Summary and Next Steps
# MAGIC %md
# MAGIC ## 🎉 Summary
# MAGIC
# MAGIC Congratulations! You've built a complete semantic search system for movies.
# MAGIC
# MAGIC ### What We Accomplished
# MAGIC
# MAGIC 1. ✅ Fetched 100+ popular movies from TMDB API
# MAGIC 2. ✅ Stored movies in Postgres with rich metadata
# MAGIC 3. ✅ **Context Engineering** - Created rich text representations by combining:
# MAGIC    - Title, overview, genres
# MAGIC    - Keywords (thematic tags)
# MAGIC    - Cast and crew
# MAGIC    - Taglines
# MAGIC 4. ✅ Generated 384-dimensional embeddings using sentence-transformers
# MAGIC 5. ✅ Stored embeddings in pgvector for fast similarity search
# MAGIC 6. ✅ Tested semantic search with natural language queries
# MAGIC
# MAGIC ### Key Insights
# MAGIC
# MAGIC 💡 **Context Engineering is Critical**: The quality of our text representations directly impacts search quality. By combining multiple metadata fields, we created rich contexts that capture:
# MAGIC - Plot themes and story elements
# MAGIC - Genre and mood
# MAGIC - Casting and directorial style
# MAGIC - Thematic keywords
# MAGIC
# MAGIC 💡 **Semantic Search Works**: Unlike keyword search, our system understands **meaning**:
# MAGIC - "funny sci-fi about time travel" finds comedic time-travel movies
# MAGIC - "emotional drama about love" finds romantic dramas
# MAGIC - No exact keyword matching required!
# MAGIC
# MAGIC 💡 **pgvector is Fast**: Cosine similarity search on 384-dimensional vectors is near-instant, even with thousands of movies.
# MAGIC
# MAGIC ### Next Steps
# MAGIC
# MAGIC 1. **Scale Up**: Process thousands more movies
# MAGIC 2. **Experiment**: Try different embedding models (larger for better quality)
# MAGIC 3. **Hybrid Search**: Combine semantic + keyword + filter search
# MAGIC 4. **Production**: Integrate into the MCP Movie Planner app
# MAGIC 5. **Monitor**: Track search quality and iterate on context engineering
# MAGIC
# MAGIC ### Try Your Own Queries!
# MAGIC
# MAGIC Modify the semantic_search() calls above with your own natural language descriptions and see what you find! 🎬

# COMMAND ----------

# DBTITLE 1,Try Your Own Query
# 🔎 TRY YOUR OWN SEMANTIC SEARCH!
# Edit the query below and run this cell

my_query = "a superhero movie with great visual effects"

results = semantic_search(my_query, limit=5)

print("=" * 70)
print(f"🎯 Results for: '{my_query}'")
print("=" * 70)
print()

for i, movie in enumerate(results, 1):
    genres = json.loads(movie['genres']) if isinstance(movie['genres'], str) else movie['genres']
    year = movie['release_date'][:4] if movie['release_date'] else 'N/A'
    
    print(f"{i}. {movie['title']} ({year})")
    print(f"   🎯 Similarity: {movie['similarity']:.4f} (1.0 = perfect match)")
    print(f"   ⭐ Rating: {movie['vote_average']}/10")
    print(f"   🎭 Genres: {', '.join(genres)}")
    print(f"   ⏱️ Runtime: {movie['runtime']} min")
    print(f"   📝 {movie['overview'][:200]}...")
    print()