# Movie Ingestion Jobs

This directory contains production-ready jobs for the Movie Night Planner project.

## Available Jobs

### `ingest_and_embed_movies.py`

Ingests movies from TMDB API and generates semantic search embeddings.

**What it does:**
1. Fetches popular movies from TMDB API
2. Stores/updates movies in the `movies` table (idempotent with UPSERT)
3. Generates embeddings using sentence-transformers
4. Stores embeddings in `movie_embeddings` table (idempotent)

**Features:**
- ✅ Idempotent: Safe to run multiple times
- ✅ Error handling: Continues on failures, logs errors
- ✅ Batch processing: Efficient memory usage
- ✅ Statistics: Detailed execution summary
- ✅ Logging: Comprehensive progress tracking

## Running Locally

```bash
cd /Workspace/Users/dceregatti@gmail.com/ai-databricks-capstone-project
python jobs/ingest_and_embed_movies.py
```

**Prerequisites:**
- Databricks secrets configured:
  - `movie-planner/tmdb-access-token`
  - `database/mcp-movie-lakebase-url`
- Database schema initialized (see `mcp_server/schema.sql`)

## Running as a Databricks Job

### Option 1: Via Databricks CLI

```bash
databricks jobs create --json @job_config.json
```

### Option 2: Via Databricks Workspace UI

1. Go to **Workflows** → **Jobs** → **Create Job**
2. Configure:
   - **Name**: `Movie Ingestion and Embedding Generation`
   - **Task type**: Python script
   - **Source**: Workspace
   - **Script path**: `/Users/<your-email>/ai-databricks-capstone-project/jobs/ingest_and_embed_movies.py`
   - **Cluster**: New or existing cluster (recommend serverless)
   - **Libraries**: Install `sentence-transformers`, `psycopg2-binary`, `databricks-sdk`
3. Set schedule (optional):
   - Daily at 2 AM UTC (recommended for fresh movie data)
   - Weekly on Sundays

## Job Configuration

Edit constants in `ingest_and_embed_movies.py`:

```python
NUM_PAGES = 5          # Number of TMDB pages to fetch (20 movies per page)
BATCH_SIZE = 50        # Embedding batch size
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
```

## Monitoring

The job outputs:
- Detailed logs at INFO level
- Progress updates every 10 movies
- Final statistics:
  - Movies fetched, inserted, updated, skipped
  - Embeddings created
  - Errors encountered
  - Total execution time

## Troubleshooting

### "Failed to connect to database"
- Check that `database/mcp-movie-lakebase-url` secret is properly configured
- Verify the DSN format: `postgresql://user:pass@host:port/dbname`

### "TMDB API rate limit"
- The job includes automatic retry with exponential backoff
- Reduce `NUM_PAGES` if hitting rate limits frequently

### "Embedding model download failed"
- First run downloads the model (~80MB)
- Ensure cluster has internet access
- Model is cached for subsequent runs

## Future Enhancements

- [ ] Incremental updates (only new/changed movies)
- [ ] Support for other TMDB endpoints (top rated, upcoming, etc.)
- [ ] Parallel processing for faster execution
- [ ] Delta Lake integration for audit trail
- [ ] Alerting on job failures
