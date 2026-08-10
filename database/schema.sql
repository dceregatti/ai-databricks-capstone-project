-- Movie Night Planner Database Schema
-- Enable pgvector extension for embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- Users table
CREATE TABLE IF NOT EXISTS users (
    user_id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

-- Groups table
CREATE TABLE IF NOT EXISTS groups (
    group_id SERIAL PRIMARY KEY,
    group_name VARCHAR(100) NOT NULL,
    created_by INTEGER REFERENCES users(user_id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Group members junction table
CREATE TABLE IF NOT EXISTS group_members (
    group_id INTEGER REFERENCES groups(group_id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (group_id, user_id)
);

-- Movies table (stores TMDB movie data)
CREATE TABLE IF NOT EXISTS movies (
    movie_id INTEGER PRIMARY KEY,  -- TMDB movie ID
    title VARCHAR(500) NOT NULL,
    original_title VARCHAR(500),
    overview TEXT,
    release_date DATE,
    runtime INTEGER,  -- in minutes
    genres JSONB,  -- array of genre objects [{"id": 28, "name": "Action"}]
    cast_info JSONB,  -- array of cast members
    keywords JSONB,  -- array of keywords for semantic matching
    poster_path VARCHAR(255),
    backdrop_path VARCHAR(255),
    vote_average DECIMAL(3,1),
    vote_count INTEGER,
    popularity DECIMAL(10,3),
    streaming_providers JSONB,  -- availability by region
    trailer_url VARCHAR(500),
    embeddings VECTOR(384),   -- sentence-transformers/all-MiniLM-L6-v2 embeddings for semantic search
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Ratings table
CREATE TABLE IF NOT EXISTS ratings (
    rating_id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
    movie_id INTEGER REFERENCES movies(movie_id) ON DELETE CASCADE,
    rating DECIMAL(2,1) CHECK (rating >= 0 AND rating <= 10),
    review TEXT,
    rated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, movie_id)
);

-- Watchlist items
CREATE TABLE IF NOT EXISTS watchlist_items (
    watchlist_id SERIAL PRIMARY KEY,
    group_id INTEGER REFERENCES groups(group_id) ON DELETE CASCADE,
    movie_id INTEGER REFERENCES movies(movie_id) ON DELETE CASCADE,
    added_by INTEGER REFERENCES users(user_id),
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    watched BOOLEAN DEFAULT FALSE,
    watched_at TIMESTAMP,
    UNIQUE(group_id, movie_id)
);

-- Recommendations table (AI-generated recommendations)
CREATE TABLE IF NOT EXISTS recommendations (
    recommendation_id SERIAL PRIMARY KEY,
    group_id INTEGER REFERENCES groups(group_id) ON DELETE CASCADE,
    movie_id INTEGER REFERENCES movies(movie_id) ON DELETE CASCADE,
    query_text TEXT,  -- what the group asked for
    relevance_score DECIMAL(4,3),
    explanation TEXT,  -- why this movie was recommended
    recommended_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_ratings_user ON ratings(user_id);
CREATE INDEX IF NOT EXISTS idx_ratings_movie ON ratings(movie_id);
CREATE INDEX IF NOT EXISTS idx_watchlist_group ON watchlist_items(group_id);
CREATE INDEX IF NOT EXISTS idx_watchlist_movie ON watchlist_items(movie_id);
CREATE INDEX IF NOT EXISTS idx_recommendations_group ON recommendations(group_id);
CREATE INDEX IF NOT EXISTS idx_group_members_group ON group_members(group_id);
CREATE INDEX IF NOT EXISTS idx_group_members_user ON group_members(user_id);
CREATE INDEX IF NOT EXISTS idx_movies_release_date ON movies(release_date);
CREATE INDEX IF NOT EXISTS idx_movies_runtime ON movies(runtime);

-- Create vector similarity search index for movie embeddings
CREATE INDEX IF NOT EXISTS idx_movies_embeddings ON movies 
USING ivfflat (embeddings vector_cosine_ops) WITH (lists = 100);