"""Minimal test app to verify Databricks Apps infrastructure."""
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()

@app.get("/")
def read_root():
    return HTMLResponse("""
    <html>
        <body>
            <h1>🎬 Movie Planner App - Test Mode</h1>
            <p>App is running successfully!</p>
        </body>
    </html>
    """)

@app.get("/health")
def health():
    return {"status": "healthy"}
