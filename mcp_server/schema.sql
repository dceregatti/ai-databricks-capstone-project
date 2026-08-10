-- Movie Night Planner Database Schema
-- Lakebase Postgres with pgvector for semantic search

-- Enable pgvector extension for embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- ========================================
-- Users Table
-- ========================================
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);

-- ========================================
-- Groups Table
-- ========================================
CREATE TABLE IF NOT EXISTS groups (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_by INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_groups_created_by ON groups(created_by);

-- ========================================
-- Group Members Table
-- ========================================
CREATE TABLE IF NOT EXISTS group_members (
    id SERIAL PRIMARY KEY,
    group_id INTEGER REFERENCES groups(id) ON DELETE CASCADE,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    role VARCHAR(50) DEFAULT 'member', -- 'admin', 'member'
    joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(group_id, user_id)
);

CREATE INDEX idx_group_members_group ON group_members(group_id);
CREATE INDEX idx_group_members_user ON group_members(user_id);

-- ========================================
-- Movies Table (TMDB data)
-- ========================================
CREATE TABLE IF NOT EXISTS movies (
    id SERIAL PRIMARY KEY,
    tmdb_id INTEGER UNIQUE NOT NULL,
    title VARCHAR(500) NOT NULL,
    original_title VARCHAR(500),
    overview TEXT,
    tagline TEXT,
    release_date DATE,
    runtime INTEGER, -- minutes
    genres JSONB DEFAULT '[]', -- array of genre names
    vote_average DECIMAL(3,1),
    vote_count INTEGER,
    popularity DECIMAL(10,3),
    poster_path VARCHAR(255),
    backdrop_path VARCHAR(255),
    original_language VARCHAR(10),
    status VARCHAR(50),
    budget BIGINT,
    revenue BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_movies_tmdb_id ON movies(tmdb_id);
CREATE INDEX idx_movies_title ON movies(title);
CREATE INDEX idx_movies_release_date ON movies(release_date);
CREATE INDEX idx_movies_vote_average ON movies(vote_average);

-- ========================================
-- Movie Embeddings Table (for semantic search)
-- ========================================
CREATE TABLE IF NOT EXISTS movie_embeddings (
    id SERIAL PRIMARY KEY,
    movie_id INTEGER REFERENCES movies(tmdb_id) ON DELETE CASCADE,
    embedding vector(384), -- all-MiniLM-L6-v2 dimension
    embedding_model VARCHAR(100) DEFAULT 'all-MiniLM-L6-v2',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(movie_id)
);

-- Index for fast similarity search
CREATE INDEX idx_movie_embeddings_vector ON movie_embeddings 
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

CREATE INDEX idx_movie_embeddings_movie ON movie_embeddings(movie_id);

-- ========================================
-- Ratings Table
-- ========================================
CREATE TABLE IF NOT EXISTS ratings (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    movie_id INTEGER REFERENCES movies(tmdb_id) ON DELETE CASCADE,
    rating DECIMAL(2,1) CHECK (rating >= 0 AND rating <= 5),
    review TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, movie_id)
);

CREATE INDEX idx_ratings_user ON ratings(user_id);
CREATE INDEX idx_ratings_movie ON ratings(movie_id);
CREATE INDEX idx_ratings_rating ON ratings(rating);

-- ========================================
-- Watchlist Items Table
-- ========================================
CREATE TABLE IF NOT EXISTS watchlist (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    movie_id INTEGER REFERENCES movies(tmdb_id) ON DELETE CASCADE,
    notes TEXT,
    priority INTEGER DEFAULT 0, -- user priority (higher = more important)
    watched BOOLEAN DEFAULT FALSE,
    watched_at TIMESTAMP,
    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, movie_id)
);

CREATE INDEX idx_watchlist_user ON watchlist(user_id);
CREATE INDEX idx_watchlist_movie ON watchlist(movie_id);
CREATE INDEX idx_watchlist_watched ON watchlist(watched);

-- ========================================
-- Recommendations Table
-- ========================================
CREATE TABLE IF NOT EXISTS recommendations (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    movie_id INTEGER REFERENCES movies(tmdb_id) ON DELETE CASCADE,
    score DECIMAL(5,4), -- recommendation confidence score
    reason TEXT, -- explanation of why recommended
    source VARCHAR(50), -- 'collaborative', 'content_based', 'hybrid', 'semantic'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP, -- recommendations can expire and be refreshed
    shown BOOLEAN DEFAULT FALSE,
    clicked BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_recommendations_user ON recommendations(user_id);
CREATE INDEX idx_recommendations_movie ON recommendations(movie_id);
CREATE INDEX idx_recommendations_score ON recommendations(score DESC);
CREATE INDEX idx_recommendations_created ON recommendations(created_at);

-- ========================================
-- Helper Functions
-- ========================================

-- Update updated_at timestamp automatically
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$ language 'plpgsql';

-- Trigger for movies table
CREATE TRIGGER update_movies_updated_at BEFORE UPDATE ON movies
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Trigger for ratings table
CREATE TRIGGER update_ratings_updated_at BEFORE UPDATE ON ratings
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ========================================
-- Sample Data (Optional)
-- ========================================

-- Insert a test user
INSERT INTO users (email, name, preferences) 
VALUES 
    ('test@example.com', 'Test User', '{"favorite_genres": ["Action", "Sci-Fi"]}'),
    ('alice@example.com', 'Alice Smith', '{"favorite_genres": ["Comedy", "Drama"]}'),
    ('bob@example.com', 'Bob Johnson', '{"favorite_genres": ["Horror", "Thriller"]}')
ON CONFLICT (email) DO NOTHING;

-- Insert a test group
INSERT INTO groups (name, description, created_by)
VALUES 
    ('Friday Night Movies', 'Weekly movie night with friends', 1)
ON CONFLICT DO NOTHING;

-- Add members to the group
INSERT INTO group_members (group_id, user_id, role)
VALUES 
    (1, 1, 'admin'),
    (1, 2, 'member'),
    (1, 3, 'member')
ON CONFLICT (group_id, user_id) DO NOTHING;

-- ========================================
-- Additional Test Users
-- ========================================

-- Add more users for testing group management
INSERT INTO users (email, name, preferences) 
VALUES 
    ('charlie@example.com', 'Charlie Brown', '{"favorite_genres": ["Animation", "Comedy"]}'),
    ('diana@example.com', 'Diana Prince', '{"favorite_genres": ["Action", "Adventure"]}'),
    ('eve@example.com', 'Eve Anderson', '{"favorite_genres": ["Romance", "Drama"]}'),
    ('frank@example.com', 'Frank Miller', '{"favorite_genres": ["Thriller", "Mystery"]}'),
    ('grace@example.com', 'Grace Lee', '{"favorite_genres": ["Documentary", "Biography"]}'),
    ('henry@example.com', 'Henry Wilson', '{"favorite_genres": ["Western", "War"]}'),
    ('iris@example.com', 'Iris Chen', '{"favorite_genres": ["Fantasy", "Adventure"]}'),
    ('jack@example.com', 'Jack Martinez', '{"favorite_genres": ["Crime", "Drama"]}'),
    ('kate@example.com', 'Kate Thompson', '{"favorite_genres": ["Musical", "Romance"]}'),
    ('leo@example.com', 'Leo Rodriguez', '{"favorite_genres": ["Science Fiction", "Action"]}'),
    ('mia@example.com', 'Mia Davis', '{"favorite_genres": ["Horror", "Thriller"]}'),
    ('noah@example.com', 'Noah Kim', '{"favorite_genres": ["Comedy", "Family"]}'),
    ('olivia@example.com', 'Olivia Brown', '{"favorite_genres": ["Drama", "Biography"]}'),
    ('paul@example.com', 'Paul Anderson', '{"favorite_genres": ["Mystery", "Thriller"]}'),
    ('quinn@example.com', 'Quinn Taylor', '{"favorite_genres": ["Animation", "Adventure"]}'),
    ('rachel@example.com', 'Rachel White', '{"favorite_genres": ["Romance", "Comedy"]}'),
    ('sam@example.com', 'Sam Harris', '{"favorite_genres": ["Action", "War"]}'),
    ('tina@example.com', 'Tina Lewis', '{"favorite_genres": ["Documentary", "History"]}'),
    ('uma@example.com', 'Uma Patel', '{"favorite_genres": ["Drama", "Foreign"]}'),
    ('victor@example.com', 'Victor Garcia', '{"favorite_genres": ["Crime", "Mystery"]}'),
    ('wendy@example.com', 'Wendy Clark', '{"favorite_genres": ["Family", "Fantasy"]}'),
    ('xavier@example.com', 'Xavier Lopez', '{"favorite_genres": ["Science Fiction", "Thriller"]}'),
    ('yara@example.com', 'Yara Ahmed', '{"favorite_genres": ["Romance", "Drama"]}'),
    ('zoe@example.com', 'Zoe Mitchell', '{"favorite_genres": ["Comedy", "Animation"]}'),
    ('aaron@example.com', 'Aaron Scott', '{"favorite_genres": ["Action", "Adventure"]}'),
    ('bella@example.com', 'Bella Turner', '{"favorite_genres": ["Horror", "Mystery"]}'),
    ('carlos@example.com', 'Carlos Rivera', '{"favorite_genres": ["War", "History"]}'),
    ('dana@example.com', 'Dana Foster', '{"favorite_genres": ["Drama", "Romance"]}'),
    ('ethan@example.com', 'Ethan Brooks', '{"favorite_genres": ["Thriller", "Crime"]}'),
    ('fiona@example.com', 'Fiona Green', '{"favorite_genres": ["Fantasy", "Family"]}')
ON CONFLICT (email) DO NOTHING;

-- ========================================
-- Sample Movies Data
-- ========================================

-- Insert popular movies with realistic TMDB-style data
INSERT INTO movies (tmdb_id, title, original_title, overview, tagline, release_date, runtime, genres, vote_average, vote_count, popularity, poster_path, backdrop_path, original_language, status, budget, revenue)
VALUES
    (550, 'Fight Club', 'Fight Club', 'A ticking-time-bomb insomniac and a slippery soap salesman channel primal male aggression into a shocking new form of therapy.', 'Mischief. Mayhem. Soap.', '1999-10-15', 139, '["Drama", "Thriller", "Comedy"]', 8.4, 26280, 68.345, '/pB8BM7pdSp6B6Ih7QZ4DrQ3PmJK.jpg', '/fCayJrkfRaCRCTh8GqN30f8oyQF.jpg', 'en', 'Released', 63000000, 100853753),
    (238, 'The Godfather', 'The Godfather', 'Spanning the years 1945 to 1955, a chronicle of the fictional Italian-American Corleone crime family.', 'An offer you can''t refuse.', '1972-03-14', 175, '["Drama", "Crime"]', 8.7, 18500, 82.912, '/3bhkrj58Vtu7enYsRolD1fZdja1.jpg', '/rSPw7tgCH9c6NqICZef0kZjFOQ5.jpg', 'en', 'Released', 6000000, 245066411),
    (680, 'Pulp Fiction', 'Pulp Fiction', 'A burger-loving hit man, his philosophical partner, and a drug-addled gangster''s moll.', 'Just because you are a character doesn''t mean you have character.', '1994-09-10', 154, '["Thriller", "Crime"]', 8.5, 25900, 71.234, '/d5iIlFn5s0ImszYzBPb8JPIfbXD.jpg', '/suaEOtk1N1sgg2MTM7oZd2cfVp3.jpg', 'en', 'Released', 8000000, 213928762),
    (13, 'Forrest Gump', 'Forrest Gump', 'A man with a low IQ has accomplished great things and been present during significant historic events.', 'Life is like a box of chocolates.', '1994-07-06', 142, '["Comedy", "Drama", "Romance"]', 8.5, 24800, 73.456, '/arw2vcBveWOVZr6pxd9XTd1TdQa.jpg', '/7c9UVPPiTPltouxRVY6N9uUaR5e.jpg', 'en', 'Released', 55000000, 677387716),
    (603, 'The Matrix', 'The Matrix', 'A computer hacker learns about the true nature of his reality and his role in the war against its controllers.', 'Welcome to the Real World.', '1999-03-30', 136, '["Action", "Science Fiction"]', 8.2, 23100, 77.890, '/f89U3ADr1oiB1s9GkdPOEpXUk5H.jpg', '/icmmSD4vTTDKOq2vvdulafOGw93.jpg', 'en', 'Released', 63000000, 463517383),
    (155, 'The Dark Knight', 'The Dark Knight', 'Batman must accept one of the greatest psychological and physical tests to fight injustice.', 'Why So Serious?', '2008-07-16', 152, '["Drama", "Action", "Crime", "Thriller"]', 8.5, 30200, 89.567, '/qJ2tW6WMUDux911r6m7haRef0WH.jpg', '/hkBaDkMWbLaf8B1lsWsKX7Ew3Xq.jpg', 'en', 'Released', 185000000, 1004558444),
    (27205, 'Inception', 'Inception', 'A thief who steals corporate secrets through dream-sharing technology is given the inverse task.', 'Your mind is the scene of the crime.', '2010-07-15', 148, '["Action", "Science Fiction", "Adventure"]', 8.4, 32400, 84.123, '/qmDpIHrmpJINaRKAfWQfftjCdyi.jpg', '/s3TBrRGB1iav7gFOCNx3H31MoES.jpg', 'en', 'Released', 160000000, 836836967),
    (497, 'The Green Mile', 'The Green Mile', 'The lives of guards on Death Row are affected by one of their charges: a man with a mysterious gift.', 'Miracles do happen.', '1999-12-10', 189, '["Fantasy", "Drama", "Crime"]', 8.5, 15200, 65.789, '/velWPhVMQeQKcxggNEU8YmIo52R.jpg', '/l6hQWH9eDksNJNiXWYRkWqikOdu.jpg', 'en', 'Released', 60000000, 286801374),
    (424, 'Schindler''s List', 'Schindler''s List', 'In German-occupied Poland, industrialist Oskar Schindler becomes concerned for his Jewish workforce.', 'Whoever saves one life, saves the world entire.', '1993-12-15', 195, '["Drama", "History", "War"]', 8.6, 14100, 59.234, '/sF1U4EUQS8YHUYjNl3pMGNIQyr0.jpg', '/loRmRzQXZeqG78TqZuyvSlEQfZb.jpg', 'en', 'Released', 22000000, 322161245),
    (122, 'The Lord of the Rings: The Return of the King', 'The Lord of the Rings: The Return of the King', 'Gandalf and Aragorn lead the World of Men against Sauron''s army to draw his gaze from Frodo and Sam.', 'There can be no triumph without loss.', '2003-12-01', 201, '["Adventure", "Fantasy", "Action"]', 8.5, 21900, 91.456, '/rCzpDGLbOoPwLjy3OAm5NUPOTrC.jpg', '/2u7zbn8EudG6kLlBzUYqP8RyFU4.jpg', 'en', 'Released', 94000000, 1118888979),
    (19995, 'Avatar', 'Avatar', 'A paraplegic Marine dispatched to the moon Pandora on a unique mission becomes torn between following his orders and protecting the world he feels is his home.', 'Enter the World of Pandora.', '2009-12-10', 162, '["Action", "Adventure", "Fantasy", "Science Fiction"]', 7.5, 27800, 95.678, '/jRXYjXNq0Cs2TcJjLkki24MLp7u.jpg', '/Yc9q6QuWrMp9nuDm5R8ExNqbEq.jpg', 'en', 'Released', 237000000, 2787965087),
    (278, 'The Shawshank Redemption', 'The Shawshank Redemption', 'Two imprisoned men bond over a number of years, finding solace and eventual redemption.', 'Fear can hold you prisoner. Hope can set you free.', '1994-09-23', 142, '["Drama", "Crime"]', 8.7, 24300, 88.234, '/q6y0Go1tsGEsmtFryDOJo3dEmqu.jpg', '/kXfqcdQKsToO0OUXHcrrNCHDBzO.jpg', 'en', 'Released', 25000000, 28341469),
    (98, 'Gladiator', 'Gladiator', 'A former Roman General sets out to exact vengeance against the corrupt emperor who murdered his family.', 'A hero will rise.', '2000-05-01', 155, '["Action", "Drama", "Adventure"]', 8.2, 14700, 76.543, '/ty8TGRuvJLPUmAR1H1nRIsgwvim.jpg', '/ehGIJif7fHZLEevjUTV7FH8pyYz.jpg', 'en', 'Released', 103000000, 460583960),
    (120, 'The Lord of the Rings: The Fellowship of the Ring', 'The Lord of the Rings: The Fellowship of the Ring', 'A young hobbit and his friends embark on a quest to destroy a powerful ring.', 'One ring to rule them all.', '2001-12-18', 178, '["Adventure", "Fantasy", "Action"]', 8.4, 22500, 87.890, '/6oom5QYQ2yQTMJIbnvbkBL9cHo6.jpg', '/pIUvQ9Ed35wlWhY2oU6OmwEsmzG.jpg', 'en', 'Released', 93000000, 871368364),
    (129, 'Spirited Away', 'Spirited Away', 'A young girl enters a world of spirits and must work to save her parents from being turned into pigs.', 'Enter a world beyond your imagination.', '2001-07-20', 125, '["Animation", "Family", "Fantasy"]', 8.5, 14200, 69.234, '/39wmItIWsg5sZMyRUHLkWBcuVCM.jpg', '/djgM2d3e42p9GFQobAQ7gfGQS8y.jpg', 'ja', 'Released', 19000000, 347705184)
ON CONFLICT (tmdb_id) DO NOTHING;

-- ========================================
-- Sample Ratings Data
-- ========================================

-- Insert sample ratings from various users
INSERT INTO ratings (user_id, movie_id, rating, review)
VALUES
    -- Test user ratings
    (1, 550, 5.0, 'Mind-blowing film! The twist ending completely changed how I see the movie.'),
    (1, 603, 4.5, 'Revolutionary special effects and an incredible story.'),
    (1, 155, 5.0, 'Heath Ledger''s Joker is unforgettable. Best superhero movie ever.'),
    (1, 27205, 4.5, 'Complex and beautifully crafted. Had to watch it twice!'),
    -- Alice ratings
    (2, 13, 5.0, 'Beautiful story that always makes me cry. Tom Hanks at his best.'),
    (2, 238, 4.5, 'Epic crime saga. Brando''s performance is legendary.'),
    (2, 680, 4.0, 'Tarantino''s masterpiece. Witty dialogue and great performances.'),
    (2, 129, 5.0, 'Stunning animation and a touching story. Miyazaki is a genius.'),
    -- Bob ratings
    (3, 550, 5.0, 'Dark, intense, and thought-provoking. A must-watch.'),
    (3, 155, 5.0, 'The perfect Batman movie. Dark, gritty, and realistic.'),
    (3, 497, 4.5, 'Emotionally powerful. Michael Clarke Duncan was amazing.'),
    (3, 680, 4.5, 'Coolest movie ever made. Every scene is iconic.'),
    -- Charlie ratings
    (4, 129, 5.0, 'Absolute masterpiece of animation. The creativity is unmatched.'),
    (4, 13, 4.5, 'Heartwarming and funny. Great for the whole family.'),
    (4, 120, 5.0, 'Epic adventure that set the standard for fantasy films.'),
    -- Diana ratings
    (5, 603, 5.0, 'Mind-bending action. The lobby scene is legendary.'),
    (5, 155, 5.0, 'Action-packed with deep themes. Nolan''s best work.'),
    (5, 27205, 5.0, 'Brilliant concept executed perfectly. Love the dream layers.'),
    (5, 98, 4.5, 'Russell Crowe delivers an amazing performance.'),
    -- More ratings from other users
    (6, 238, 5.0, 'The greatest film ever made. Perfect in every way.'),
    (6, 278, 5.0, 'Inspiring story about hope and friendship.'),
    (7, 424, 5.0, 'Powerful and important. Liam Neeson was phenomenal.'),
    (8, 122, 5.0, 'Perfect conclusion to the trilogy. Epic in every sense.'),
    (9, 19995, 4.0, 'Visually stunning. The world-building is incredible.'),
    (10, 27205, 4.5, 'Complex plot but worth multiple viewings.'),
    (11, 550, 5.0, 'Brad Pitt and Edward Norton are phenomenal together.'),
    (12, 13, 5.0, 'One of the most touching movies I''ve ever seen.'),
    (13, 680, 5.0, 'Every line is quotable. Tarantino''s best film.'),
    (14, 155, 5.0, 'Heath Ledger deserved that Oscar. Unforgettable.'),
    (15, 120, 4.5, 'Amazing start to an incredible trilogy.')
ON CONFLICT (user_id, movie_id) DO NOTHING;

-- ========================================
-- Sample Recommendations Data
-- ========================================

-- Generate recommendations for users based on their preferences
INSERT INTO recommendations (user_id, movie_id, score, reason, source, expires_at, shown, clicked)
VALUES
    -- Recommendations for Test User (likes Action/Sci-Fi)
    (1, 19995, 0.8923, 'Based on your love of sci-fi movies like The Matrix', 'content_based', NOW() + INTERVAL '30 days', false, false),
    (1, 98, 0.8654, 'Fans of action-packed films like The Dark Knight also enjoyed this', 'collaborative', NOW() + INTERVAL '30 days', false, false),
    (1, 120, 0.8234, 'Epic adventure similar to your highly-rated movies', 'hybrid', NOW() + INTERVAL '30 days', false, false),
    -- Recommendations for Alice (likes Comedy/Drama)
    (2, 497, 0.9012, 'Emotional drama similar to Forrest Gump', 'content_based', NOW() + INTERVAL '30 days', false, false),
    (2, 424, 0.8756, 'Powerful drama that users with similar taste loved', 'collaborative', NOW() + INTERVAL '30 days', false, false),
    (2, 278, 0.8901, 'Highly rated drama film you haven''t seen yet', 'hybrid', NOW() + INTERVAL '30 days', false, false),
    -- Recommendations for Bob (likes Horror/Thriller)
    (3, 27205, 0.8845, 'Psychological thriller with mind-bending plot', 'content_based', NOW() + INTERVAL '30 days', false, false),
    (3, 238, 0.8567, 'Dark crime drama similar to your preferences', 'collaborative', NOW() + INTERVAL '30 days', false, false),
    -- Recommendations for Charlie (likes Animation/Comedy)
    (4, 19995, 0.7834, 'Fantasy adventure with stunning visuals', 'content_based', NOW() + INTERVAL '30 days', false, false),
    (4, 122, 0.8123, 'Epic fantasy adventure you might enjoy', 'hybrid', NOW() + INTERVAL '30 days', false, false),
    -- Recommendations for Diana (likes Action/Adventure)
    (5, 120, 0.9234, 'Epic action-adventure similar to your favorites', 'content_based', NOW() + INTERVAL '30 days', false, false),
    (5, 122, 0.9156, 'Continuation of the epic trilogy', 'collaborative', NOW() + INTERVAL '30 days', false, false),
    (5, 550, 0.8734, 'Intense thriller with action elements', 'hybrid', NOW() + INTERVAL '30 days', false, false),
    -- Additional recommendations for other users
    (6, 680, 0.8912, 'Crime drama fans also loved this Tarantino classic', 'collaborative', NOW() + INTERVAL '30 days', false, false),
    (7, 278, 0.9123, 'Another powerful drama about hope and redemption', 'content_based', NOW() + INTERVAL '30 days', false, false),
    (8, 120, 0.8867, 'Start of the trilogy you loved', 'collaborative', NOW() + INTERVAL '30 days', false, false),
    (9, 603, 0.8456, 'Groundbreaking sci-fi like Avatar', 'content_based', NOW() + INTERVAL '30 days', false, false),
    (10, 603, 0.8678, 'Another mind-bending film you''ll love', 'collaborative', NOW() + INTERVAL '30 days', false, false)
ON CONFLICT DO NOTHING;

-- ========================================
-- Sample Watchlist Data
-- ========================================

-- Add movies to users' watchlists
INSERT INTO watchlist (user_id, movie_id, notes, priority, watched, watched_at)
VALUES
    -- Test user watchlist
    (1, 238, 'Classic mafia film - need to watch this!', 5, false, NULL),
    (1, 424, 'Important historical drama', 4, false, NULL),
    (1, 19995, 'Want to see the visuals on a big screen', 5, false, NULL),
    (1, 278, 'Top rated movie on many lists', 5, false, NULL),
    -- Alice watchlist
    (2, 550, 'Heard amazing things about the twist', 3, false, NULL),
    (2, 497, 'Looks like an emotional journey', 4, false, NULL),
    (2, 155, 'Finally need to watch this Batman movie', 4, false, NULL),
    (2, 278, 'Everyone says this is a must-watch', 5, false, NULL),
    -- Bob watchlist
    (3, 238, 'The godfather of crime movies', 5, false, NULL),
    (3, 424, 'Important film to watch', 3, false, NULL),
    (3, 278, 'Highly recommended by friends', 5, false, NULL),
    -- Charlie watchlist  
    (4, 603, 'Want to see what the hype is about', 4, false, NULL),
    (4, 27205, 'Complex plot - need to be focused for this one', 3, false, NULL),
    (4, 98, 'Heard the action scenes are incredible', 3, false, NULL),
    -- Diana watchlist
    (5, 238, 'Classic I need to finally watch', 4, false, NULL),
    (5, 13, 'Comfort movie everyone loves', 2, false, NULL),
    (5, 680, 'Want to catch all the Tarantino references', 3, false, NULL),
    -- More watchlist entries with some watched movies
    (6, 550, 'Planning to watch this weekend', 5, false, NULL),
    (6, 603, 'Rewatching this classic', 3, true, NOW() - INTERVAL '5 days'),
    (7, 238, 'Adding to my classic films list', 5, false, NULL),
    (7, 680, 'Crime film marathon coming up', 4, false, NULL),
    (8, 603, 'Matrix marathon planned', 4, true, NOW() - INTERVAL '10 days'),
    (8, 27205, 'Need to understand the ending better', 5, false, NULL),
    (9, 550, 'Friend recommended this highly', 5, false, NULL),
    (9, 155, 'Best superhero movie allegedly', 5, false, NULL),
    (10, 238, 'Starting my Coppola watchlist', 5, false, NULL),
    (10, 278, 'Top of my must-watch list', 5, false, NULL),
    (11, 13, 'Comfort watch for rainy days', 2, true, NOW() - INTERVAL '2 days'),
    (11, 129, 'Miyazaki marathon', 4, false, NULL),
    (12, 680, 'Tarantino complete works', 3, false, NULL),
    (12, 550, 'Mind-bending movies list', 4, false, NULL),
    (13, 27205, 'Complex films to analyze', 5, false, NULL),
    (13, 603, 'Rewatching before new Matrix', 3, true, NOW() - INTERVAL '7 days'),
    (14, 120, 'LOTR extended edition marathon', 5, false, NULL),
    (14, 122, 'Finishing the trilogy', 5, false, NULL),
    (15, 19995, 'Waiting for the sequel', 4, false, NULL),
    (15, 98, 'Historical epics to watch', 4, false, NULL)
ON CONFLICT (user_id, movie_id) DO NOTHING;
