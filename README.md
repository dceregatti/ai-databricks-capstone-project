# AI Movie Night Planner

An AI-powered movie recommendation system that helps groups find the perfect movie to watch together. Built on Databricks with Lakebase Postgres, TMDB API, and semantic search using OpenAI embeddings.

## Overview

Users create groups, rate movies, describe what they want to watch, and ask an AI agent to recommend something everyone will enjoy. The system uses semantic search with vector embeddings to understand natural language queries like "a funny sci-fi movie that isn't too violent and is under two hours."

## Architecture

### Database: Lakebase Postgres
* **Project**: `movie-night-planner`
* **Tables**: users, groups, group_members, movies, ratings, watchlist_items, recommendations
* **Vector Search**: pgvector extension for semantic similarity

### Data Sources
* **TMDB API**: Movies, actors, genres, posters, plot summaries, reviews, trailers, streaming availability
* Free for non-commercial educational use with attribution
* Each user needs a free API key from https://www.themoviedb.org/settings/api

### AI Components
1. **Embeddings**: OpenAI text-embedding-ada-002 (1536 dimensions)
2. **Context Engineering**: Combines plot summaries, keywords, cast, genres for rich semantic search
3. **Vector Search**: Cosine similarity on movie embeddings

## Features

### Core Capabilities
* ✓ **Semantic Movie Search**: Natural language queries with vector similarity
* ✓ **Group Recommendations**: AI suggests movies based on group preferences
* ✓ **Preference Learning**: Analyzes past ratings to understand group tastes
* ✓ **Smart Filtering**: Avoids already-watched or disliked movies
* ✓ **Watchlist Management**: Add, track, and mark movies as watched
* ✓ **Rating System**: Record ratings and reviews
* ✓ **Movie Comparison**: Side-by-side comparison of multiple movies

## Project Structure

```
ai-databricks-capstone-project/
├── database/
│   └── schema.sql              # Database schema with pgvector support
├── src/
│   ├── db_connection.py        # Lakebase Postgres connection manager
│   ├── tmdb_client.py          # TMDB API client
│   ├── embeddings.py           # OpenAI embedding generator
│   └── recommendation_engine.py # AI recommendation engine
├── setup_and_test.py        # Setup and testing notebook
├── .env                     # Environment variables (not committed)
├── .gitignore
└── README.md
```

## Setup Instructions

### 1. Prerequisites

* Databricks workspace with serverless compute
* TMDB API key (free): https://www.themoviedb.org/settings/api
* OpenAI API key: https://platform.openai.com/api-keys

### 2. Environment Configuration

Create a `.env` file in the project root:

```bash
TMDB_API_KEY=your_tmdb_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
```

### 3. Database Setup

The Lakebase Postgres project is already created:
* Project: `movie-night-planner`
* Branch: `production`
* Endpoint: `primary`
* Database: `databricks_postgres`

### 4. Run Setup Notebook

Open and run `setup_and_test.py` notebook to:
1. Install dependencies
2. Initialize database schema
3. Create test users and groups
4. Fetch sample movies from TMDB
5. Generate embeddings
6. Test recommendations

## Usage Examples

### Basic Search

```python
from recommendation_engine import MovieRecommendationEngine

engine = MovieRecommendationEngine()

# Semantic search
results = engine.search_movies_semantic(
    "a funny sci-fi movie under 2 hours",
    limit=5
)

for movie in results:
    print(f"{movie['title']} - Similarity: {movie['similarity_score']:.3f}")
```

### Group Recommendations

```python
# Get recommendations for a group
recommendations = engine.recommend_for_group(
    group_id=1,
    query="fun action-comedy for Friday night",
    limit=5
)

for rec in recommendations:
    print(f"{rec['title']}")
    print(f"Explanation: {rec['explanation']}\n")
```

### Manage Watchlist

```python
# Add to watchlist
engine.add_to_watchlist(
    group_id=1,
    movie_id=123456,
    user_id=1
)

# Mark as watched
engine.mark_as_watched(group_id=1, movie_id=123456)
```

### Rate Movies

```python
# Record a rating
engine.record_rating(
    user_id=1,
    movie_id=123456,
    rating=8.5,
    review="Great movie! Perfect for movie night."
)
```

### Compare Movies

```python
# Compare multiple movies
comparison = engine.compare_movies([123456, 789012, 345678])

for movie in comparison:
    print(f"{movie['title']}: {movie['runtime']}min, {movie['vote_average']}/10")
```

## Database Schema

### Core Tables

* **users**: User accounts
* **groups**: Movie night groups
* **group_members**: Group membership (many-to-many)
* **movies**: Movie data from TMDB with embeddings
* **ratings**: User ratings and reviews
* **watchlist_items**: Group watchlists
* **recommendations**: AI-generated recommendations

### Key Features

* **pgvector**: Vector similarity search on 1536-dim embeddings
* **JSONB**: Flexible storage for genres, cast, keywords, streaming providers
* **Foreign Keys**: Referential integrity with cascade deletes
* **Indexes**: Optimized for common queries

## API Reference

### MovieRecommendationEngine

Main class for movie recommendations and group management.

#### Methods

* `search_movies_semantic(query, limit, group_id)` - Semantic search with vector similarity
* `recommend_for_group(group_id, query, limit)` - Get personalized group recommendations
* `get_group_preferences(group_id)` - Analyze group rating patterns
* `add_to_watchlist(group_id, movie_id, user_id)` - Add movie to watchlist
* `record_rating(user_id, movie_id, rating, review)` - Record user rating
* `mark_as_watched(group_id, movie_id)` - Mark movie as watched
* `compare_movies(movie_ids)` - Compare multiple movies

### TMDBClient

Client for interacting with The Movie Database API.

#### Methods

* `search_movies(query, page)` - Search movies by title
* `get_movie_details(movie_id)` - Get detailed movie information
* `get_movie_credits(movie_id)` - Get cast and crew
* `get_movie_keywords(movie_id)` - Get movie keywords
* `get_movie_videos(movie_id)` - Get trailers and videos
* `get_movie_watch_providers(movie_id)` - Get streaming availability
* `get_complete_movie_data(movie_id)` - Get all data in one call
* `format_for_database(movie_data)` - Format for DB insertion

### EmbeddingGenerator

Generates vector embeddings using OpenAI.

#### Methods

* `generate_movie_embedding(movie_data)` - Create embedding for a movie
* `generate_query_embedding(query)` - Create embedding for search query
* `create_movie_text(movie_data)` - Format movie data for embedding

### DatabaseConnection

Manages Lakebase Postgres connections.

#### Methods

* `get_connection()` - Get fresh connection with OAuth token
* `execute_query(query, params, fetch)` - Execute SQL query
* `execute_many(query, params_list)` - Execute batch operations
* `initialize_schema(schema_file)` - Initialize database from SQL file

## Technical Details

### Context Engineering

Movie embeddings combine:
* Title
* Plot summary/overview
* Genres
* Keywords (top 15)
* Cast (top 5)
* Runtime

Format: `"Title: {title} | Plot: {overview} | Genres: {genres} | Keywords: {keywords} | Cast: {cast} | Runtime: {runtime} minutes"`

### Semantic Search Algorithm

1. Generate embedding for user query
2. Compute cosine similarity with all movie embeddings
3. Filter out already-watched movies (if group_id provided)
4. Filter out movies with low ratings from group members
5. Return top-k matches with similarity scores

### Recommendation Logic

1. Get semantic matches (query embedding)
2. Analyze group preferences (past ratings by genre)
3. Filter disliked movies (rating < 5)
4. Rank by relevance score
5. Generate explanations
6. Store recommendations for tracking

## Performance Considerations

* **Embedding Cache**: Movies are embedded once and stored
* **Index**: IVFFlat index on embeddings for fast similarity search
* **Connection Pooling**: OAuth token refresh with connection reuse
* **Batch Operations**: Use `execute_many` for bulk inserts

## Future Enhancements

* Chatbot interface for natural conversations
* Real-time group voting on recommendations
* Schedule movie nights with calendar integration
* Watch history and trending analysis
* Multi-modal search (upload poster, search by image)
* Integration with streaming services for direct playback

## Troubleshooting

### TMDB API Issues
* Check API key is valid and set in `.env`
* Verify you haven't exceeded rate limits (40 requests/10 seconds)
* Ensure movie IDs exist in TMDB database

### Database Connection Issues
* Verify Lakebase project exists: `movie-night-planner`
* Check OAuth token is valid (auto-refreshed by SDK)
* Ensure pgvector extension is enabled

### Embedding Issues
* Check OpenAI API key is valid
* Verify you have API credits available
* Ensure text input is not empty
* Check embedding dimensions match database (1536)

## License

Educational project for Databricks AI Capstone. TMDB data used under TMDB API terms of service with attribution.

## Attribution

This product uses the TMDB API but is not endorsed or certified by TMDB.

![TMDB Logo](https://www.themoviedb.org/assets/2/v4/logos/v2/blue_short-8e7b30f73a4020692ccca9c88bafe5dcb6f8a62a4c6bc55cd9ba82bb2cd95f6c.svg)

## Contact

For questions or issues, please refer to the Databricks documentation or TMDB API documentation.