#!/usr/bin/env python
"""
Setup script to initialize the Lakebase database schema.

This script:
1. Enables pgvector extension
2. Creates all necessary tables
3. Sets up indexes for performance
4. Inserts sample test data

Usage:
    python setup_database.py
    
Or in a notebook:
    %run ./setup_database.py
"""

import os
import lakebase

print("=" * 60)
print("Movie Night Planner - Database Setup")
print("=" * 60)
print()

# Read the schema SQL file
schema_file = os.path.join(os.path.dirname(__file__), 'schema.sql')
print(f"Reading schema from: {schema_file}")

with open(schema_file, 'r') as f:
    schema_sql = f.read()

print("\nExecuting database schema...")
print("-" * 60)

try:
    # Execute the schema using lakebase connection
    with lakebase.get_connection() as conn:
        with conn.cursor() as cur:
            # Execute the entire schema
            cur.execute(schema_sql)
            conn.commit()
            print("✓ Schema executed successfully")
    
    print("\n" + "=" * 60)
    print("Database setup complete!")
    print("=" * 60)
    
    # Verify tables were created
    print("\nVerifying tables...")
    tables = lakebase.run_query("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    
    print(f"\n✓ Created {len(tables)} tables:")
    for table in tables:
        print(f"  • {table['table_name']}")
    
    # Verify pgvector extension
    print("\nVerifying pgvector extension...")
    extensions = lakebase.run_query("""
        SELECT extname, extversion 
        FROM pg_extension 
        WHERE extname = 'vector'
    """)
    
    if extensions:
        ext = extensions[0]
        print(f"✓ pgvector extension enabled (version {ext['extversion']})")
    else:
        print("⚠ pgvector extension not found")
    
    # Show sample users
    print("\nSample users created:")
    users = lakebase.run_query("SELECT id, email, name FROM users ORDER BY id")
    for user in users:
        print(f"  • [{user['id']}] {user['name']} ({user['email']})")
    
    print("\n🎉 Ready to use! You can now:")
    print("  1. Populate movies from TMDB")
    print("  2. Generate embeddings for semantic search")
    print("  3. Start using the MCP server")
    print()
    
except Exception as e:
    print(f"\n✗ Error setting up database: {e}")
    print("\nPlease check:")
    print("  • Lakebase connection is working")
    print("  • Database credentials are correct")
    print("  • pgvector extension is available")
    raise
