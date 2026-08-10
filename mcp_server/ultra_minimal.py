"""Ultra minimal test server."""
import os

try:
    from fastapi import FastAPI
    import uvicorn
    
    app = FastAPI()
    
    @app.get("/")
    def root():
        return {"status": "running", "message": "Ultra minimal server works"}
    
    if __name__ == "__main__":
        port = int(os.environ.get("DATABRICKS_APP_PORT", 8000))
        print(f"Starting on port {port}")
        uvicorn.run(app, host="0.0.0.0", port=port)
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    raise
