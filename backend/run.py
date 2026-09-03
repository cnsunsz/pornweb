"""Launch MediaVault using host/port from .env / environment."""
import os
import uvicorn
from app.core.config import settings

if __name__ == "__main__":
    reload = os.environ.get("MV_RELOAD") == "1"
    workers = 1 if reload else int(os.environ.get("UVICORN_WORKERS", "2"))
    uvicorn.run(
        "app.main:app",
        host=settings.BIND_HOST,
        port=int(settings.HTTP_PORT),
        reload=reload,
        workers=workers,
    )
