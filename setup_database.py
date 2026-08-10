# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "5"
# ///
# DBTITLE 1,Database Setup
# MAGIC %md
# MAGIC # Movie Night Planner - Database Setup
# MAGIC
# MAGIC This notebook initializes the Lakebase database schema with all necessary tables.

# COMMAND ----------

# DBTITLE 1,Run Setup Script
# MAGIC %undefined
# MAGIC import sys
# MAGIC sys.path.append('/Workspace/Users/dceregatti@gmail.com/ai-databricks-capstone-project/mcp_server')
# MAGIC import lakebase
# MAGIC
# MAGIC print("=" * 60)
# MAGIC print("Movie Night Planner - Database Setup")
# MAGIC print("=" * 60)
# MAGIC print()
# MAGIC
# MAGIC # Read the schema SQL file
# MAGIC schema_file = '/Workspace/Users/dceregatti@gmail.com/ai-databricks-capstone-project/mcp_server/schema.sql'
# MAGIC print(f"Reading schema from: {schema_file}")
# MAGIC
# MAGIC with open(schema_file, 'r') as f:
# MAGIC     schema_sql = f.read()
# MAGIC
# MAGIC print("\nExecuting database schema...")
# MAGIC print("-" * 60)
# MAGIC
# MAGIC try:
# MAGIC     # Execute the schema using lakebase connection
# MAGIC     with lakebase.get_connection() as conn:
# MAGIC         with conn.cursor() as cur:
# MAGIC             # Execute the entire schema
# MAGIC             cur.execute(schema_sql)
# MAGIC             conn.commit()
# MAGIC             print("✓ Schema executed successfully")
# MAGIC     
# MAGIC     print("\n" + "=" * 60)
# MAGIC     print("Database setup complete!")
# MAGIC     print("=" * 60)
# MAGIC     
# MAGIC     # Verify tables were created
# MAGIC     print("\nVerifying tables...")
# MAGIC     tables = lakebase.run_query("""
# MAGIC         SELECT table_name 
# MAGIC         FROM information_schema.tables 
# MAGIC         WHERE table_schema = 'public' 
# MAGIC         AND table_type = 'BASE TABLE'
# MAGIC         ORDER BY table_name
# MAGIC     """)
# MAGIC     
# MAGIC     print(f"\n✓ Created {len(tables)} tables:")
# MAGIC     for table in tables:
# MAGIC         print(f"  • {table['table_name']}")
# MAGIC     
# MAGIC     # Verify pgvector extension
# MAGIC     print("\nVerifying pgvector extension...")
# MAGIC     extensions = lakebase.run_query("""
# MAGIC         SELECT extname, extversion 
# MAGIC         FROM pg_extension 
# MAGIC         WHERE extname = 'vector'
# MAGIC     """)
# MAGIC     
# MAGIC     if extensions:
# MAGIC         ext = extensions[0]
# MAGIC         print(f"✓ pgvector extension enabled (version {ext['extversion']})")
# MAGIC     else:
# MAGIC         print("⚠ pgvector extension not found")
# MAGIC     
# MAGIC     # Show sample users
# MAGIC     print("\nSample users created:")
# MAGIC     users = lakebase.run_query("SELECT id, email, name FROM users ORDER BY id")
# MAGIC     for user in users:
# MAGIC         print(f"  • [{user['id']}] {user['name']} ({user['email']})")
# MAGIC     
# MAGIC     print("\n🎉 Ready to use! You can now:")
# MAGIC     print("  1. Populate movies from TMDB")
# MAGIC     print("  2. Generate embeddings for semantic search")
# MAGIC     print("  3. Start using the MCP server")
# MAGIC     print()
# MAGIC     
# MAGIC except Exception as e:
# MAGIC     print(f"\n✗ Error setting up database: {e}")
# MAGIC     print("\nPlease check:")
# MAGIC     print("  • Lakebase connection is working")
# MAGIC     print("  • Database credentials are correct")
# MAGIC     print("  • pgvector extension is available")
# MAGIC     raise

# COMMAND ----------

# DBTITLE 1,Verify Setup
# MAGIC %md
# MAGIC ## Verify Database Setup
# MAGIC
# MAGIC Check that all tables were created successfully:

# COMMAND ----------

# DBTITLE 1,List Tables
import sys
sys.path.append('/Workspace/Users/dceregatti@gmail.com/ai-databricks-capstone-project/mcp_server')
import lakebase

# List all tables
tables = lakebase.run_query("""
    SELECT table_name, 
           (SELECT COUNT(*) 
            FROM information_schema.columns 
            WHERE table_schema = 'public' 
            AND table_name = t.table_name) as column_count
    FROM information_schema.tables t
    WHERE table_schema = 'public' 
    AND table_type = 'BASE TABLE'
    ORDER BY table_name
""")

print(f"Found {len(tables)} tables:\n")
for table in tables:
    print(f"  ✓ {table['table_name']:25s} ({table['column_count']} columns)")

# COMMAND ----------

# DBTITLE 1,Check Sample Data
# MAGIC %md
# MAGIC ## Check Sample Data
# MAGIC
# MAGIC Verify that sample users and groups were created:

# COMMAND ----------

# DBTITLE 1,Show Sample Data
# Check users
users = lakebase.run_query("SELECT * FROM users ORDER BY id")
print(f"Users ({len(users)}):")
for user in users:
    print(f"  [{user['id']}] {user['name']:20s} {user['email']:30s}")

print()

# Check groups
groups = lakebase.run_query("SELECT * FROM groups ORDER BY id")
print(f"Groups ({len(groups)}):")
for group in groups:
    print(f"  [{group['id']}] {group['name']:30s} (created by user {group['created_by']})")

print()

# Check group members
members = lakebase.run_query("""
    SELECT gm.*, u.name as user_name, g.name as group_name
    FROM group_members gm
    JOIN users u ON gm.user_id = u.id
    JOIN groups g ON gm.group_id = g.id
    ORDER BY gm.group_id, gm.user_id
""")
print(f"Group Members ({len(members)}):")
for member in members:
    print(f"  {member['group_name']:30s} - {member['user_name']:20s} ({member['role']})")