import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.config import settings
from .core.database import init_db
from .models import User, MediaItem, MediaLibrary, PlaybackProgress  # noqa: F401
from .api import auth, media, users, media_folders, libraries, settings as settings_api

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    os.makedirs("data", exist_ok=True)
    try:
        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
    except OSError:
        pass
    init_db()
    yield

app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(auth.router)
app.include_router(media.router)
app.include_router(users.router)
app.include_router(media_folders.router)
app.include_router(libraries.router)
app.include_router(settings_api.router)

@app.get("/api/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME}
