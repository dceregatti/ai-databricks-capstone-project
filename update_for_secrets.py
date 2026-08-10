#!/usr/bin/env python
"""
Helper script to update embeddings.py to use Databricks secrets.
Run this once to patch the existing file.
"""

update_code = '''
# Update embeddings.py
with open("src/embeddings.py", "r") as f:
    content = f.read()

# Add Optional to imports if not present
if "from typing import List, Dict" in content and "Optional" not in content.split("from typing import List, Dict")[1].split("\\n")[0]:
    content = content.replace(
        "from typing import List, Dict",
        "from typing import List, Dict, Optional"
    )

# Update __init__ method
old_init = '''        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key not provided. Set OPENAI_API_KEY environment variable.")
        
        openai.api_key = self.api_key'''

new_init = '''        if api_key:
            self.api_key = api_key
        else:
            # Try Databricks secrets first
            try:
                from databricks.sdk import WorkspaceClient
                w = WorkspaceClient()
                self.api_key = w.secrets.get_secret(scope="movie-planner", key="openai-api-key").value
            except Exception:
                # Fallback to environment variable for local development
                self.api_key = os.getenv("OPENAI_API_KEY")
        
        if not self.api_key:
            raise ValueError(
                "OpenAI API key not provided. Either:\\n"
                "  1. Run setup_secrets.py to store in Databricks secrets, or\\n"
                "  2. Set OPENAI_API_KEY environment variable for local development"
            )
        
        openai.api_key = self.api_key'''

content = content.replace(old_init, new_init)

with open("src/embeddings.py", "w") as f:
    f.write(content)

print("✓ embeddings.py updated to use Databricks secrets")
'''

print("To update embeddings.py to use Databricks secrets:")
print()
print(update_code)
print()
print("Copy and run the code above in a notebook cell.")