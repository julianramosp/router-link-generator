from fastapi import FastAPI
from fastapi.responses import FileResponse
from pathlib import Path

from app.api.routes import router

app = FastAPI(title="Route Link Generator API")

# Register API routes
app.include_router(router, prefix="/api")

# ---- Serve Web UI ----
WEB_DIR = Path(__file__).resolve().parent / "web"
INDEX_FILE = WEB_DIR / "index.html"

@app.get("/", include_in_schema=False)
def home():
    return FileResponse(INDEX_FILE)