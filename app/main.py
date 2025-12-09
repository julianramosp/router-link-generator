from fastapi import FastAPI
from app.api.routes import router

app = FastAPI(title="Route Link Generator API")

# Register API routes
app.include_router(router, prefix="/api")
