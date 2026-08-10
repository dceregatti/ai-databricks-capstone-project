"""Minimal diagnostic server to test basic app startup."""
import os
from fastapi import FastAPI
import uvicorn

app = FastAPI()

@app.get("/")
def root():
    return {"status": "ok", "message": "Minimal server is running"}

@app.get("/health")
def health():
    return {"healthy": True}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"Starting minimal server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
