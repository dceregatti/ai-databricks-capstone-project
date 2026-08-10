# Setting Up API Keys with Databricks Secrets

This guide explains how to securely store your TMDB and OpenAI API keys using Databricks secrets.

## Why Use Databricks Secrets?

* ✓ **Secure**: Keys are encrypted and never exposed in code or notebooks
* ✓ **Centralized**: One place to manage all API keys
* ✓ **Team-Friendly**: Share access without sharing actual keys
* ✓ **Production-Ready**: Best practice for deployed applications

## Quick Start

### Step 1: Get Your API Keys

**TMDB API Key** (Free)
1. Go to https://www.themoviedb.org/settings/api
2. Sign up for a free account if needed
3. Request an API key (choose "Developer" option)
4. Copy your API key

**OpenAI API Key**
1. Go to https://platform.openai.com/api-keys
2. Sign in to your OpenAI account
3. Create a new API key
4. Copy your API key immediately (you won't be able to see it again)

### Step 2: Run the Setup Script

**From a Databricks notebook:**

```python
%run ./setup_secrets.py
```

**From your local terminal (with Databricks CLI configured):**

```bash
python setup_secrets.py
```

### Step 3: Enter Your Keys

The script will prompt you to paste each key:

```
Step 1/2: TMDB API Key
------------------------------------------------------------
Paste your TMDB API key: [paste here]
✓ TMDB API key stored

Step 2/2: OpenAI API Key
------------------------------------------------------------
Paste your OpenAI API key: [paste here]
✓ OpenAI API key stored
```

### Step 4: Verify Setup

Test that your secrets are accessible:

```python
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

# This will work if secrets are set up correctly
tmdb_key = w.secrets.get_secret(scope="movie-planner", key="tmdb-api-key").value
print(f"✓ TMDB key loaded (length: {len(tmdb_key)})")

openai_key = w.secrets.get_secret(scope="movie-planner", key="openai-api-key").value
print(f"✓ OpenAI key loaded (length: {len(openai_key)})")
```

Or using dbutils in a notebook:

```python
tmdb_key = dbutils.secrets.get(scope="movie-planner", key="tmdb-api-key")
print(f"✓ TMDB key loaded (length: {len(tmdb_key)})")

openai_key = dbutils.secrets.get(scope="movie-planner", key="openai-api-key")
print(f"✓ OpenAI key loaded (length: {len(openai_key)})")
```

## How It Works

The setup script:

1. **Creates a secret scope** called `movie-planner`
2. **Stores two secrets**:
   - `tmdb-api-key`: Your TMDB API key
   - `openai-api-key`: Your OpenAI API key
3. **Sets permissions** so all workspace users can read the secrets

## Using Secrets in Your Code

The Movie Night Planner code is already configured to use Databricks secrets!

### TMDBClient

```python
from tmdb_client import TMDBClient

# Automatically reads from secrets
client = TMDBClient()  
```

### EmbeddingGenerator

```python
from embeddings import EmbeddingGenerator

# Automatically reads from secrets
embedder = EmbeddingGenerator()
```

### Fallback Behavior

If secrets are not found, the code falls back to environment variables:
1. First tries: `w.secrets.get_secret(scope="movie-planner", key="tmdb-api-key")`
2. If that fails: `os.getenv("TMDB_API_KEY")`

This allows local development with `.env` files while using secrets in production.

## Manual Secret Management

### List All Secrets

```python
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

# List all secret scopes
for scope in w.secrets.list_scopes():
    print(f"Scope: {scope.name}")
```

### Update a Secret

```python
from databricks.sdk import WorkspaceClient
import getpass

w = WorkspaceClient()

# Update TMDB key
w.secrets.put_secret(
    scope="movie-planner",
    key="tmdb-api-key",
    string_value=getpass.getpass("Enter new TMDB API key: ")
)
```

### Delete a Secret

```python
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

# Delete a specific secret
w.secrets.delete_secret(
    scope="movie-planner",
    key="tmdb-api-key"
)

# Or delete entire scope (careful!)
# w.secrets.delete_scope(scope="movie-planner")
```

## Troubleshooting

### Error: "Secret scope movie-planner already exists"

**Solution**: Secrets are already set up! You can:
* Skip to Step 4 to verify
* Re-run the script to update existing secrets

### Error: "Permission denied"

**Solution**: Make sure you have permission to create secret scopes. Contact your workspace admin if needed.

### Error: "Secret not found"

**Solution**: 
1. Check the scope name: `movie-planner`
2. Check the key names: `tmdb-api-key`, `openai-api-key`
3. Re-run setup_secrets.py

### Keys Not Working in TMDB/OpenAI APIs

**Solution**:
1. Verify your keys are valid by testing them directly in your browser or Postman
2. Make sure you didn't copy extra spaces or newlines
3. For TMDB: Check your daily API quota
4. For OpenAI: Verify you have available credits

## Security Best Practices

✓ **DO**:
* Use Databricks secrets for all production deployments
* Rotate your API keys periodically
* Set appropriate ACLs (read-only for most users)
* Use separate keys for dev/staging/production

✗ **DON'T**:
* Commit API keys to git (`.env` is in `.gitignore`)
* Share API keys via chat/email
* Print API keys in notebook output
* Hardcode keys in source files

## Alternative: Using Databricks CLI

You can also manage secrets using the Databricks CLI:

```bash
# Create scope
databricks secrets create-scope movie-planner

# Store secrets
databricks secrets put-secret movie-planner tmdb-api-key
databricks secrets put-secret movie-planner openai-api-key

# List secrets
databricks secrets list movie-planner

# Delete secret
databricks secrets delete-secret movie-planner tmdb-api-key
```

## Next Steps

Once your secrets are set up:

1. Run the [setup_and_test.py](setup_and_test.py) notebook
2. The code will automatically use your secrets
3. Start building your movie recommendation system!

## Questions?

See the main [README.md](README.md) for more information or refer to:
* [Databricks Secrets Documentation](https://docs.databricks.com/security/secrets/index.html)
* [TMDB API Documentation](https://developers.themoviedb.org/3)
* [OpenAI API Documentation](https://platform.openai.com/docs)