# Databricks notebook source
# DBTITLE 1,Movie Night Planner - Setup and Test
# MAGIC %md
# MAGIC # Movie Night Planner - Setup and Test
# MAGIC
# MAGIC This notebook helps you set up and test the Movie Night Planner AI system.
# MAGIC
# MAGIC ## Prerequisites
# MAGIC
# MAGIC 1. **TMDB API Key**: Sign up at https://www.themoviedb.org/settings/api to get a free API key
# MAGIC 2. **OpenAI API Key**: Get from https://platform.openai.com/api-keys for embeddings
# MAGIC
# MAGIC ## Environment Variables
# MAGIC
# MAGIC Set these in your `.env` file:
# MAGIC ```
# MAGIC TMDB_API_KEY=your_tmdb_api_key_here
# MAGIC OPENAI_API_KEY=your_openai_api_key_here
# MAGIC ```

# COMMAND ----------

# DBTITLE 1,Install Dependencies
# Install required packages
%pip install -q psycopg[binary]>=3.1.0 requests openai python-dotenv

# COMMAND ----------

# DBTITLE 1,Load Environment Variables
import sys
import os

# Add src directory to path
sys.path.append(os.path.join(os.getcwd(), "src"))

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

print("✓ Environment loaded")
print(f"  TMDB_API_KEY: {'Set' if os.getenv('TMDB_API_KEY') else 'NOT SET'}")
print(f"  OPENAI_API_KEY: {'Set' if os.getenv('OPENAI_API_KEY') else 'NOT SET'}")

# COMMAND ----------

# DBTITLE 1,Initialize Database Schema
from db_connection import DatabaseConnection

# Initialize database
db = DatabaseConnection()

# Run schema initialization
try:
    db.initialize_schema("database/schema.sql")
    print("✓ Database schema initialized")
except Exception as e:
    print(f"Error: {e}")
    print("Make sure schema.sql exists in the database/ directory")

# COMMAND ----------

# DBTITLE 1,Create Test Users and Group
# Create test users
users = [
    ("alice", "alice@example.com"),
    ("bob", "bob@example.com"),
    ("charlie", "charlie@example.com")
]

for username, email in users:
    db.execute_query(
        "INSERT INTO users (username, email) VALUES (%s, %s) ON CONFLICT (email) DO NOTHING",
        (username, email),
        fetch=False
    )

print("✓ Test users created")

# Get user IDs
user_rows = db.execute_query("SELECT user_id, username, email FROM users")
for user in user_rows:
    print(f"  User {user['user_id']}: {user['username']} ({user['email']})")

# Create test group
db.execute_query(
    "INSERT INTO groups (group_name, created_by) VALUES (%s, %s) RETURNING group_id",
    ("Friday Movie Night", user_rows[0]['user_id']),
    fetch=False
)

groups = db.execute_query("SELECT group_id, group_name FROM groups")
group_id = groups[0]['group_id']
print(f"\n✓ Test group created: {groups[0]['group_name']} (ID: {group_id})")

# Add all users to the group
for user in user_rows:
    db.execute_query(
        "INSERT INTO group_members (group_id, user_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
        (group_id, user['user_id']),
        fetch=False
    )

print("✓ Users added to group")

# COMMAND ----------

# DBTITLE 1,Fetch and Store Sample Movies
from tmdb_client import TMDBClient
from embeddings import EmbeddingGenerator
import json

# Initialize clients
tmdb = TMDBClient()
embedder = EmbeddingGenerator()

# Fetch popular movies
print("Fetching popular movies from TMDB...")
popular_movies = tmdb.get_popular_movies(page=1)

# Process and store first 10 movies
for i, movie_summary in enumerate(popular_movies[:10], 1):
    try:
        print(f"Processing {i}/10: {movie_summary['title']}...")
        
        # Get complete movie data
        movie_data = tmdb.get_complete_movie_data(movie_summary['id'])
        
        # Generate embedding
        embedding = embedder.generate_movie_embedding(movie_data)
        
        # Format for database
        db_data = tmdb.format_for_database(movie_data)
        db_data['embeddings'] = json.dumps(embedding)
        
        # Insert into database
        db.execute_query(
            """
            INSERT INTO movies (
                movie_id, title, original_title, overview, release_date, runtime,
                genres, cast_info, keywords, poster_path, backdrop_path,
                vote_average, vote_count, popularity, streaming_providers,
                trailer_url, embeddings
            ) VALUES (
                %(movie_id)s, %(title)s, %(original_title)s, %(overview)s, %(release_date)s,
                %(runtime)s, %(genres)s, %(cast_info)s, %(keywords)s, %(poster_path)s,
                %(backdrop_path)s, %(vote_average)s, %(vote_count)s, %(popularity)s,
                %(streaming_providers)s, %(trailer_url)s, %(embeddings)s::vector
            )
            ON CONFLICT (movie_id) DO UPDATE SET
                title = EXCLUDED.title,
                overview = EXCLUDED.overview,
                embeddings = EXCLUDED.embeddings
            """,
            db_data,
            fetch=False
        )
        
    except Exception as e:
        print(f"  Error processing {movie_summary['title']}: {e}")

print("\n✓ Sample movies loaded")

# Show movies in database
movies = db.execute_query(
    "SELECT movie_id, title, runtime, vote_average FROM movies ORDER BY popularity DESC LIMIT 10"
)

for movie in movies:
    print(f"  {movie['title']} ({movie['runtime']}min, {movie['vote_average']}/10)")

# COMMAND ----------

# DBTITLE 1,Test Semantic Search
from recommendation_engine import MovieRecommendationEngine

# Initialize engine
engine = MovieRecommendationEngine()

# Test semantic search
print("Testing semantic search...\n")

queries = [
    "a funny sci-fi movie",
    "action movie with car chases",
    "romantic comedy"
]

for query in queries:
    print(f"Query: '{query}'")
    results = engine.search_movies_semantic(query, limit=3)
    
    for i, movie in enumerate(results, 1):
        print(f"  {i}. {movie['title']} (similarity: {movie['similarity_score']:.3f})")
    print()

# COMMAND ----------

# DBTITLE 1,Test Group Recommendations
# Add some ratings to simulate preferences
print("Adding sample ratings...")

# Alice likes action movies
action_movies = db.execute_query(
    "SELECT movie_id FROM movies WHERE genres::text LIKE '%Action%' LIMIT 2"
)
for movie in action_movies:
    engine.record_rating(user_rows[0]['user_id'], movie['movie_id'], 8.5)

# Bob likes comedies
comedy_movies = db.execute_query(
    "SELECT movie_id FROM movies WHERE genres::text LIKE '%Comedy%' LIMIT 2"
)
for movie in comedy_movies:
    engine.record_rating(user_rows[1]['user_id'], movie['movie_id'], 9.0)

print("✓ Sample ratings added\n")

# Test group recommendations
print("Testing group recommendations...\n")
query = "fun action-comedy movie for Friday night"
print(f"Query: '{query}'\n")

recommendations = engine.recommend_for_group(group_id, query, limit=3)

for i, rec in enumerate(recommendations, 1):
    print(f"{i}. {rec['title']}")
    print(f"   Score: {rec['relevance_score']:.3f}")
    print(f"   {rec['explanation']}")
    print()

# COMMAND ----------

# DBTITLE 1,Next Steps
# MAGIC %md
# MAGIC ## ✓ Setup Complete!
# MAGIC
# MAGIC Your Movie Night Planner is ready to use. Here's what you can do:
# MAGIC
# MAGIC ### Core Features
# MAGIC
# MAGIC 1. **Semantic Search**: Find movies using natural language queries
# MAGIC 2. **Group Recommendations**: Get AI-powered recommendations based on group preferences
# MAGIC 3. **Watchlist Management**: Add movies to your group's watchlist
# MAGIC 4. **Rating System**: Record ratings and reviews
# MAGIC 5. **Movie Comparison**: Compare multiple movies side-by-side
# MAGIC
# MAGIC ### Example Usage
# MAGIC
# MAGIC ```python
# MAGIC from recommendation_engine import MovieRecommendationEngine
# MAGIC
# MAGIC engine = MovieRecommendationEngine()
# MAGIC
# MAGIC # Search for movies
# MAGIC results = engine.search_movies_semantic("thriller with plot twists", limit=5)
# MAGIC
# MAGIC # Get recommendations for a group
# MAGIC recs = engine.recommend_for_group(group_id, "family-friendly adventure movie", limit=3)
# MAGIC
# MAGIC # Add to watchlist
# MAGIC engine.add_to_watchlist(group_id, movie_id, user_id)
# MAGIC
# MAGIC # Rate a movie
# MAGIC engine.record_rating(user_id, movie_id, 8.5, "Great movie!")
# MAGIC
# MAGIC # Compare movies
# MAGIC comparison = engine.compare_movies([movie_id1, movie_id2, movie_id3])
# MAGIC ```
# MAGIC
# MAGIC ### Database Connection Info
# MAGIC
# MAGIC Your Lakebase Postgres database:
# MAGIC * **Project**: movie-night-planner
# MAGIC * **Branch**: production
# MAGIC * **Endpoint**: primary
# MAGIC * **Connection**: Use `DatabaseConnection` class in `src/db_connection.py`

# COMMAND ----------

