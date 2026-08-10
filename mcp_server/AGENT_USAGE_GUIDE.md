# MCP Movie Planner - Agent Usage Guide

## Typical Workflow

### 1. Search for Movies
```
Agent: "Find action movies from 2023"
Tool: search_movies(query="action", year=2023)
```

### 2. Compare Options
```
Agent: "Compare The Matrix, Inception, and Interstellar"
Tool: compare_movies(movie_ids=[603, 27205, 157336])
→ Shows side-by-side comparison with ratings, runtime, genres
```

### 3. Get Smart Recommendations (Auto-filtered)
```
Agent: "Recommend movies for group 1 that we haven't watched"
Tool: get_smart_recommendations(group_id=1, limit=10)
→ Automatically excludes:
  • Movies already watched by group members
  • Movies rated < 2.0 by any member
```

### 4. Add to Watchlist
```
Agent: "Add Inception to my watchlist"
Tool: add_to_watchlist(user_id=1, movie_id=27205, notes="Recommended by Alice")
```

### 5. After Watching - Record Rating
```
Agent: "I watched Inception, it was great - 4.5/5"
Tool: record_rating(user_id=1, movie_id=27205, rating=4.5, review="Mind-bending!")
→ Automatically marks as watched
→ Updates if rating already exists
```

### 6. Track Group History
```
Agent: "What movies has our group already watched?"
Tool: get_group_watched_movies(group_id=1)
→ Returns all movies watched by any member

Agent: "What movies did the group dislike?"
Tool: get_group_disliked_movies(group_id=1, threshold=2.0)
→ Returns movies rated below 2.0
```

## Key Features

✅ **Automatic Deduplication**: `get_smart_recommendations` filters out watched/disliked movies
✅ **Standardized Responses**: All tools return consistent JSON format
✅ **Group-Aware**: Track movies watched/rated by group members
✅ **Flexible Search**: Keyword search + semantic search + filtered recommendations
✅ **Side-by-Side Comparison**: Compare up to 5 movies at once

## Database Tables

* **users** - User accounts and preferences
* **groups** - Movie night groups
* **group_members** - Group membership
* **movies** - TMDB movie data
* **watchlist** - Personal watchlists with watched flag
* **ratings** - User ratings (0-5) with reviews
* **recommendations** - Personalized recommendations

## Sample Users (for testing)

1. Test User (test@example.com)
2. Alice Smith (alice@example.com)  
3. Bob Johnson (bob@example.com)

## Sample Group

* Group 1: "Friday Night Movies" (all 3 users)
