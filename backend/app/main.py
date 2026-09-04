import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .core.config import settings
from .core.database import init_db
from .models import User, MediaItem, MediaLibrary, PlaybackProgress, ScanJob  # noqa: F401
from .api import auth, media, users, media_folders, libraries, settings as settings_api, actors

@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("data", exist_ok=True)
    try:
        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
    except OSError:
        pass
    init_db()
    try:
        from .services.scan_runner import mark_stale_jobs
        mark_stale_jobs()
    except Exception:
        pass
    try:
        from .services.library_watcher import start_library_watcher
        start_library_watcher()
    except Exception:
        pass
    yield
    try:
        from .services.library_watcher import stop_library_watcher
        stop_library_watcher()
    except Exception:
        pass

app = FastAPI(
    title=settings.APP_NAME,
    version="1.3.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(media.router)
app.include_router(users.router)
app.include_router(media_folders.router)
app.include_router(libraries.router)
app.include_router(settings_api.router)
app.include_router(actors.router)

@app.get("/api/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME}
