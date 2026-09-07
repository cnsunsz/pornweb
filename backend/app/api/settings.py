from pathlib import Path
from typing import Optional
import re
import subprocess
import threading
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from ..core.config import settings, _ENV_PATH
from ..models.user import User
from .deps import get_current_admin

router = APIRouter(prefix="/api/settings", tags=["settings"])

KEYS = ("HTTP_PORT", "BIND_HOST", "PUBLIC_PORT", "MEDIA_ROOT", "APP_NAME",
        "AUTO_SCAN_ENABLED", "AUTO_SCAN_INTERVAL_MINUTES",
        "SCRAPER_PREFER_LOCAL", "SCRAPER_INTERNET_ENABLED",
        "SCRAPER_METADATA_LANGUAGE", "SCRAPER_SAVE_ARTWORK",
        "SCRAPER_DOUBAN_ENABLED", "SCRAPER_TMDB_ENABLED", "SCRAPER_JAVDB_ENABLED",
        "TMDB_API_KEY", "SCRAPER_ORDER",
        "SCRAPER_DOUBAN_COOKIE", "SCRAPER_JAVDB_COOKIE", "SCRAPER_PROXY",
        "SCRAPER_TIMEOUT_SECONDS")
_BACKEND_ENV = Path("/www/mediavault/backend/.env")
def _nginx_vhost() -> Path:
    d = Path("/www/server/panel/vhost/nginx")
    for name in ("html_mediavault.conf", "mediavault.conf"):
        c = d / name
        if c.exists() and c.stat().st_size > 0:
            return c
    hits = sorted(d.glob("*mediavault*.conf"))
    for c in hits:
        if c.stat().st_size > 0:
            return c
    return d / "html_mediavault.conf"

_NGINX_VHOST = _nginx_vhost()
_NGINX_BIN = Path("/www/server/nginx/sbin/nginx")
_UNIT = Path("/etc/systemd/system/mediavault.service")
_RESERVED = {22, 25, 888}


class ServerSettings(BaseModel):
    app_name: str = "PornWeb"
    http_port: int = Field(8099, ge=1, le=65535)
    bind_host: str = "127.0.0.1"
    public_port: int = Field(5588, ge=1, le=65535)
    media_root: str = ""
    auto_scan_enabled: bool = True
    auto_scan_interval_minutes: int = Field(15, ge=1, le=1440)
    # Metadata (Emby/Jellyfin-style; admin-only configure)
    scraper_prefer_local: bool = True
    scraper_internet_enabled: bool = True
    scraper_metadata_language: str = "zh-CN"
    scraper_save_artwork: bool = False
    scraper_douban_enabled: bool = False
    scraper_tmdb_enabled: bool = False
    scraper_javdb_enabled: bool = False
    tmdb_api_key: str = ""
    scraper_order: str = "nfo,tmdb,douban,javdb"
    scraper_douban_cookie: str = ""
    scraper_javdb_cookie: str = ""
    scraper_proxy: str = ""
    scraper_timeout_seconds: float = Field(8.0, ge=2.0, le=30.0)
    env_file: str = ""
    restart_required: bool = False


class ServerSettingsUpdate(BaseModel):
    app_name: Optional[str] = None
    http_port: Optional[int] = Field(None, ge=1, le=65535)
    bind_host: Optional[str] = None
    public_port: Optional[int] = Field(None, ge=1, le=65535)
    media_root: Optional[str] = None
    auto_scan_enabled: Optional[bool] = None
    auto_scan_interval_minutes: Optional[int] = Field(None, ge=1, le=1440)
    scraper_prefer_local: Optional[bool] = None
    scraper_internet_enabled: Optional[bool] = None
    scraper_metadata_language: Optional[str] = None
    scraper_save_artwork: Optional[bool] = None
    scraper_douban_enabled: Optional[bool] = None
    scraper_tmdb_enabled: Optional[bool] = None
    scraper_javdb_enabled: Optional[bool] = None
    tmdb_api_key: Optional[str] = None
    scraper_order: Optional[str] = None
    scraper_douban_cookie: Optional[str] = None
    scraper_javdb_cookie: Optional[str] = None
    scraper_proxy: Optional[str] = None
    scraper_timeout_seconds: Optional[float] = Field(None, ge=2.0, le=30.0)



def _env_bool(val, default=True) -> bool:
    if val is None:
        return default
    s = str(val).strip().lower()
    if s in ("1", "true", "yes", "on"):
        return True
    if s in ("0", "false", "no", "off"):
        return False
    return default


def _read_env(path: Path) -> dict:
    data = {}
    if not path.exists():
        return data
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        data[k.strip()] = v.strip().strip('"').strip("'")
    return data


def _write_env(path: Path, updates: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _read_env(path)
    data.update(updates)
    lines = [f"{k}={v}" for k, v in data.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_env_all(updates: dict):
    seen = set()
    for path in (_ENV_PATH, _BACKEND_ENV):
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        if path == _ENV_PATH or path.exists():
            _write_env(path, updates)


def _apply_public_port(port: int):
    if port in _RESERVED:
        raise HTTPException(400, f"端口 {port} 不可用作对外 HTTP")
    vhost = _nginx_vhost()
    if not vhost.exists():
        raise HTTPException(500, "未找到 Nginx 站点配置")
    text = vhost.read_text(encoding="utf-8")
    text = re.sub(r"^\s*listen\s+[^;]+;\s*\n", "", text, flags=re.M)
    if "server {" not in text:
        raise HTTPException(500, "Nginx 站点配置格式异常")
    text = text.replace("server {", f"server {{\n    listen {port};", 1)
    vhost.write_text(text, encoding="utf-8")
    subprocess.run(["ufw", "allow", f"{port}/tcp"], check=False, capture_output=True)
    if not _NGINX_BIN.exists():
        raise HTTPException(500, "未找到 Nginx")
    test = subprocess.run([str(_NGINX_BIN), "-t"], capture_output=True, text=True)
    if test.returncode != 0:
        err = (test.stderr or test.stdout).strip()
        raise HTTPException(500, f"Nginx 配置失败: {err}")
    rel = subprocess.run([str(_NGINX_BIN), "-s", "reload"], capture_output=True, text=True)
    if rel.returncode != 0:
        err = (rel.stderr or rel.stdout).strip()
        raise HTTPException(500, f"Nginx 重载失败: {err}")


def _apply_bind(host: str, http_port: int):
    if host not in ("127.0.0.1", "0.0.0.0"):
        raise HTTPException(400, "监听地址无效")
    if shutil_which("ufw"):
        if host == "0.0.0.0":
            subprocess.run(["ufw", "allow", f"{http_port}/tcp"], check=False, capture_output=True)
        else:
            subprocess.run(["ufw", "delete", "allow", f"{http_port}/tcp"], check=False, capture_output=True)


def shutil_which(name: str) -> bool:
    from shutil import which
    return which(name) is not None


def _schedule_backend_restart():
    if not _UNIT.exists():
        return
    def _go():
        subprocess.run(["systemctl", "restart", "mediavault"], check=False, capture_output=True)
    threading.Timer(1.0, _go).start()



def _timeout_seconds(env: dict) -> float:
    raw = env.get("SCRAPER_TIMEOUT_SECONDS")
    try:
        v = float(raw) if raw not in (None, "") else float(
            getattr(settings, "SCRAPER_TIMEOUT_SECONDS", 8.0) or 8.0
        )
    except (TypeError, ValueError):
        v = 8.0
    return max(2.0, min(30.0, v))


def _current() -> ServerSettings:
    env = _read_env(_ENV_PATH)
    interval = env.get("AUTO_SCAN_INTERVAL_MINUTES")
    try:
        interval_i = int(interval) if interval not in (None, "") else int(
            getattr(settings, "AUTO_SCAN_INTERVAL_MINUTES", 15) or 15
        )
    except (TypeError, ValueError):
        interval_i = 15
    return ServerSettings(
        app_name=env.get("APP_NAME") or settings.APP_NAME,
        http_port=int(env.get("HTTP_PORT") or settings.HTTP_PORT),
        bind_host=env.get("BIND_HOST") or settings.BIND_HOST,
        public_port=int(env.get("PUBLIC_PORT") or settings.PUBLIC_PORT),
        media_root=env.get("MEDIA_ROOT") or settings.MEDIA_ROOT,
        auto_scan_enabled=_env_bool(
            env.get("AUTO_SCAN_ENABLED"),
            bool(getattr(settings, "AUTO_SCAN_ENABLED", True)),
        ),
        auto_scan_interval_minutes=max(1, min(1440, interval_i)),
        scraper_prefer_local=_env_bool(
            env.get("SCRAPER_PREFER_LOCAL"),
            bool(getattr(settings, "SCRAPER_PREFER_LOCAL", True)),
        ),
        scraper_internet_enabled=_env_bool(
            env.get("SCRAPER_INTERNET_ENABLED"),
            bool(getattr(settings, "SCRAPER_INTERNET_ENABLED", True)),
        ),
        scraper_metadata_language=(
            env.get("SCRAPER_METADATA_LANGUAGE")
            or getattr(settings, "SCRAPER_METADATA_LANGUAGE", None)
            or "zh-CN"
        ),
        scraper_save_artwork=_env_bool(
            env.get("SCRAPER_SAVE_ARTWORK"),
            bool(getattr(settings, "SCRAPER_SAVE_ARTWORK", False)),
        ),
        scraper_douban_enabled=_env_bool(
            env.get("SCRAPER_DOUBAN_ENABLED"),
            bool(getattr(settings, "SCRAPER_DOUBAN_ENABLED", False)),
        ),
        scraper_tmdb_enabled=_env_bool(
            env.get("SCRAPER_TMDB_ENABLED"),
            bool(getattr(settings, "SCRAPER_TMDB_ENABLED", False)),
        ),
        scraper_javdb_enabled=_env_bool(
            env.get("SCRAPER_JAVDB_ENABLED"),
            bool(getattr(settings, "SCRAPER_JAVDB_ENABLED", False)),
        ),
        tmdb_api_key=env.get("TMDB_API_KEY")
            if env.get("TMDB_API_KEY") is not None
            else (getattr(settings, "TMDB_API_KEY", "") or ""),
        scraper_order=(
            env.get("SCRAPER_ORDER")
            or getattr(settings, "SCRAPER_ORDER", None)
            or "nfo,tmdb,douban,javdb"
        ),
        scraper_douban_cookie=env.get("SCRAPER_DOUBAN_COOKIE")
            if env.get("SCRAPER_DOUBAN_COOKIE") is not None
            else (getattr(settings, "SCRAPER_DOUBAN_COOKIE", "") or ""),
        scraper_javdb_cookie=env.get("SCRAPER_JAVDB_COOKIE")
            if env.get("SCRAPER_JAVDB_COOKIE") is not None
            else (getattr(settings, "SCRAPER_JAVDB_COOKIE", "") or ""),
        scraper_proxy=env.get("SCRAPER_PROXY")
            if env.get("SCRAPER_PROXY") is not None
            else (getattr(settings, "SCRAPER_PROXY", "") or ""),
        scraper_timeout_seconds=_timeout_seconds(env),
        env_file=str(_ENV_PATH),
        restart_required=False,
    )


@router.get("/", response_model=ServerSettings)
async def get_settings(admin: User = Depends(get_current_admin)):
    """Server settings including metadata scrapers — admin only."""
    return _current()


@router.put("/", response_model=ServerSettings)
async def update_settings(req: ServerSettingsUpdate, admin: User = Depends(get_current_admin)):
    cur = _current()
    updates = {}
    restart = False
    if req.app_name is not None:
        name = req.app_name.strip() or "PornWeb"
        updates["APP_NAME"] = name
        cur.app_name = name
    if req.http_port is not None:
        if req.http_port in (22, 25, 80, 443, 888):
            raise HTTPException(400, "端口不可用")
        updates["HTTP_PORT"] = str(req.http_port)
        if req.http_port != cur.http_port:
            restart = True
        cur.http_port = req.http_port
    if req.bind_host is not None:
        host = req.bind_host.strip() or "127.0.0.1"
        if host not in ("127.0.0.1", "0.0.0.0"):
            raise HTTPException(400, "监听地址无效")
        updates["BIND_HOST"] = host
        if host != cur.bind_host:
            restart = True
        cur.bind_host = host
    if req.public_port is not None:
        if req.public_port == cur.http_port:
            raise HTTPException(400, "对外端口不能和后端端口相同")
        if req.public_port != cur.public_port:
            _apply_public_port(req.public_port)
        updates["PUBLIC_PORT"] = str(req.public_port)
        cur.public_port = req.public_port
    if req.media_root is not None:
        root = req.media_root.strip()
        if not root:
            raise HTTPException(400, "媒体根目录不能为空")
        updates["MEDIA_ROOT"] = root
        cur.media_root = root
    if req.auto_scan_enabled is not None:
        updates["AUTO_SCAN_ENABLED"] = "true" if req.auto_scan_enabled else "false"
        cur.auto_scan_enabled = req.auto_scan_enabled
    if req.auto_scan_interval_minutes is not None:
        updates["AUTO_SCAN_INTERVAL_MINUTES"] = str(req.auto_scan_interval_minutes)
        cur.auto_scan_interval_minutes = req.auto_scan_interval_minutes
    if req.scraper_prefer_local is not None:
        updates["SCRAPER_PREFER_LOCAL"] = "true" if req.scraper_prefer_local else "false"
        cur.scraper_prefer_local = req.scraper_prefer_local
    if req.scraper_internet_enabled is not None:
        updates["SCRAPER_INTERNET_ENABLED"] = "true" if req.scraper_internet_enabled else "false"
        cur.scraper_internet_enabled = req.scraper_internet_enabled
    if req.scraper_metadata_language is not None:
        lang = (req.scraper_metadata_language or "").strip() or "zh-CN"
        # Keep compact locale tags only
        allowed_lang = {
            "zh-CN", "zh-TW", "en-US", "en", "ja-JP", "ja", "ko-KR", "ko",
            "fr-FR", "de-DE", "es-ES", "pt-BR", "ru-RU",
        }
        if lang not in allowed_lang:
            # accept xx or xx-YY loosely
            if not (2 <= len(lang) <= 8 and lang.replace("-", "").isalnum()):
                raise HTTPException(400, "元数据语言无效")
        updates["SCRAPER_METADATA_LANGUAGE"] = lang
        cur.scraper_metadata_language = lang
    if req.scraper_save_artwork is not None:
        updates["SCRAPER_SAVE_ARTWORK"] = "true" if req.scraper_save_artwork else "false"
        cur.scraper_save_artwork = req.scraper_save_artwork
    if req.scraper_douban_enabled is not None:
        updates["SCRAPER_DOUBAN_ENABLED"] = "true" if req.scraper_douban_enabled else "false"
        cur.scraper_douban_enabled = req.scraper_douban_enabled
    if req.scraper_tmdb_enabled is not None:
        updates["SCRAPER_TMDB_ENABLED"] = "true" if req.scraper_tmdb_enabled else "false"
        cur.scraper_tmdb_enabled = req.scraper_tmdb_enabled
    if req.scraper_javdb_enabled is not None:
        updates["SCRAPER_JAVDB_ENABLED"] = "true" if req.scraper_javdb_enabled else "false"
        cur.scraper_javdb_enabled = req.scraper_javdb_enabled
    if req.tmdb_api_key is not None:
        key = req.tmdb_api_key.strip()
        updates["TMDB_API_KEY"] = key
        cur.tmdb_api_key = key
    if req.scraper_order is not None:
        order = (req.scraper_order or "").strip() or "nfo,tmdb,douban,javdb"
        # Normalize: keep known tokens only, preserve nfo + provider order
        allowed = {"nfo", "tmdb", "douban", "javdb"}
        parts = [p.strip().lower() for p in order.split(",") if p.strip()]
        parts = [p for p in parts if p in allowed]
        if "nfo" not in parts:
            parts = ["nfo"] + parts
        if not any(p != "nfo" for p in parts):
            parts = ["nfo", "tmdb", "douban", "javdb"]
        order = ",".join(parts)
        updates["SCRAPER_ORDER"] = order
        cur.scraper_order = order
    if req.scraper_douban_cookie is not None:
        updates["SCRAPER_DOUBAN_COOKIE"] = req.scraper_douban_cookie.strip()
        cur.scraper_douban_cookie = req.scraper_douban_cookie.strip()
    if req.scraper_javdb_cookie is not None:
        updates["SCRAPER_JAVDB_COOKIE"] = req.scraper_javdb_cookie.strip()
        cur.scraper_javdb_cookie = req.scraper_javdb_cookie.strip()
    if req.scraper_proxy is not None:
        updates["SCRAPER_PROXY"] = req.scraper_proxy.strip()
        cur.scraper_proxy = req.scraper_proxy.strip()
    if req.scraper_timeout_seconds is not None:
        updates["SCRAPER_TIMEOUT_SECONDS"] = str(req.scraper_timeout_seconds)
        cur.scraper_timeout_seconds = float(req.scraper_timeout_seconds)
    internet_on = bool(cur.scraper_internet_enabled)
    if internet_on and cur.scraper_tmdb_enabled and not (cur.tmdb_api_key or "").strip():
        raise HTTPException(400, "启用 TMDB 元数据下载时需要填写 TMDB API Key")
    if updates:
        _write_env_all(updates)
        # Hot-apply auto-scan runtime without requiring restart
        try:
            from ..services.library_watcher import configure as _cfg_watcher
            _cfg_watcher(
                enabled=cur.auto_scan_enabled,
                interval_minutes=cur.auto_scan_interval_minutes,
            )
        except Exception:
            pass
        try:
            from ..services.scrapers import apply_live_config
            apply_live_config(updates)
        except Exception:
            pass
    if restart:
        _apply_bind(cur.bind_host, cur.http_port)
        _schedule_backend_restart()
    cur.env_file = str(_ENV_PATH)
    cur.restart_required = restart and not _UNIT.exists()
    return cur
