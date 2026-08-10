"""Minimal diagnostic MCP server to test deployment."""

import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("diagnostic-server")

logger.info("=" * 60)
logger.info("DIAGNOSTIC: Starting minimal server")
logger.info(f"PORT env: {os.environ.get('PORT', 'NOT SET')}")
logger.info(f"LAKEBASE_SECRET_SCOPE: {os.environ.get('LAKEBASE_SECRET_SCOPE', 'NOT SET')}")
logger.info(f"TMDB_SECRET_SCOPE: {os.environ.get('TMDB_SECRET_SCOPE', 'NOT SET')}")
logger.info("=" * 60)

if __name__ == "__main__":
    try:
        import uvicorn
        from fastmcp import FastMCP
        
        logger.info("FastMCP and uvicorn imported successfully")
        
        mcp = FastMCP("diagnostic-server")
        
        @mcp.tool
        def test_tool() -> dict:
            return {"status": "ok", "message": "Server is running"}
        
        port = int(os.environ.get("PORT", 8000))
        logger.info(f"Starting uvicorn on port {port}...")
        
        uvicorn.run(
            mcp.get_asgi_app(),
            host="0.0.0.0",
            port=port,
            log_level="info"
        )
    except Exception as e:
        logger.exception(f"FATAL ERROR: {e}")
        raise
