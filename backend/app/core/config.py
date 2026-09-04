from pydantic_settings import BaseSettings
from typing import List
from pathlib import Path

_CANDIDATES = [
    Path("/etc/mediavault/mediavault.env"),
    Path(__file__).resolve().parents[2] / ".env",
]
_ENV_PATH = next((p for p in _CANDIDATES if p.exists()), _CANDIDATES[-1])

class Settings(BaseSettings):
    APP_NAME: str = "PornWeb"
    SECRET_KEY: str = "change-me-in-env"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours
    DATABASE_URL: str = "sqlite:///./data/mediavault.db"
    CORS_ORIGINS: List[str] = ["*"]
    MEDIA_ROOT: str = "/var/lib/mediavault/media"
    HTTP_PORT: int = 8099
    BIND_HOST: str = "127.0.0.1"
    PUBLIC_PORT: int = 5588
    # Emby-style auto library scan (watchdog + periodic safety net for rclone FUSE)
    AUTO_SCAN_ENABLED: bool = True
    AUTO_SCAN_INTERVAL_MINUTES: int = 15

    class Config:
        env_file = str(_ENV_PATH)
        env_file_encoding = "utf-8"

settings = Settings()
