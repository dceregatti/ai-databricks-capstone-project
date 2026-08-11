# Integration Tests

End-to-end tests for the Movie Night Planner MCP Server.

## Test Suite

### `test_integration.py`

Comprehensive integration test covering:
1. **Database Connection** - Verify Lakebase Postgres connectivity
2. **TMDB API** - Verify TMDB API access
3. **Seed Movies** - Insert test movies (Inception, Shawshank Redemption)
4. **Generate Embeddings** - Create semantic search embeddings
5. **Semantic Search** - Test natural language movie search

## Running Tests

### Prerequisites

1. **Database initialized**:
   ```bash
   psql $LAKEBASE_URL < mcp_server/schema.sql
   ```

2. **Secrets configured**:
   - `movie-planner/tmdb-access-token`
   - `database/mcp-movie-lakebase-url`

3. **Dependencies installed**:
   ```bash
   pip install sentence-transformers psycopg2-binary databricks-sdk
   ```

### Run Tests

```bash
cd /Workspace/Users/dceregatti@gmail.com/ai-databricks-capstone-project
python tests/test_integration.py
```

## Expected Output

```
################################################################################
# INTEGRATION TEST SUITE - Movie Night Planner MCP Server
################################################################################

================================================================================
TEST 1: Database Connection
================================================================================
✅ Database connection successful

================================================================================
TEST 2: TMDB API Connection
================================================================================
✅ TMDB API working (found 20 results)

================================================================================
TEST 3: Seed Test Movies
================================================================================
✅ Seeded: The Shawshank Redemption
✅ Seeded: Inception

Seeded 2 new movies, 2 total test movies

================================================================================
TEST 4: Generate Embeddings
================================================================================
✅ Generated embedding for: The Shawshank Redemption
✅ Generated embedding for: Inception

Generated 2 embeddings

================================================================================
TEST 5: Semantic Search
================================================================================

Query: 'mind-bending heist movie'
Found 3 results:
  1. Inception (similarity: 0.876)
  2. The Shawshank Redemption (similarity: 0.543)
  3. ...
✅ Search successful

################################################################################
# TEST SUMMARY
################################################################################
✅ PASS - Database Connection
✅ PASS - TMDB API
✅ PASS - Seed Movies
✅ PASS - Generate Embeddings
✅ PASS - Semantic Search

================================================================================
Result: 5/5 tests passed
🎉 ALL TESTS PASSED! System is operational.
================================================================================
```

## Troubleshooting

### Test 1 Fails: Database Connection
- Check `database/mcp-movie-lakebase-url` secret
- Verify Lakebase endpoint is running
- Check network connectivity

### Test 2 Fails: TMDB API
- Check `movie-planner/tmdb-access-token` secret
- Verify TMDB access token is valid (not API key)
- Check rate limits

### Test 3 Fails: Seed Movies
- Run `mcp_server/schema.sql` to initialize tables
- Check table permissions

### Test 4 Fails: Generate Embeddings
- Ensure `pgvector` extension is installed
- Check internet access for model download
- Verify disk space for model cache

### Test 5 Fails: Semantic Search
- Re-run Test 4 to regenerate embeddings
- Check `movie_embeddings` table has data
- Verify embedding dimensions match (384 for all-MiniLM-L6-v2)

## Running After Deployment

These tests should be run:
1. **Initially** - After setting up the system
2. **After changes** - Schema, code, or configuration updates
3. **Periodically** - Weekly smoke tests
4. **Before production** - Final validation

## Future Enhancements

- [ ] Unit tests for individual functions
- [ ] Performance benchmarks
- [ ] Load testing (concurrent searches)
- [ ] MCP protocol compliance tests
- [ ] Automated CI/CD integration
