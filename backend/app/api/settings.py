from pathlib import Path
from typing import Optional
import re
import subprocess
import threading
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from ..core.config import settings, _ENV_PATH
from ..models.user import User
from .deps import get_current_user, get_current_admin

router = APIRouter(prefix="/api/settings", tags=["settings"])

KEYS = ("HTTP_PORT", "BIND_HOST", "PUBLIC_PORT", "MEDIA_ROOT", "APP_NAME")
_BACKEND_ENV = Path("/www/mediavault/backend/.env")
_NGINX_VHOST = Path("/www/server/panel/vhost/nginx/mediavault.conf")
_NGINX_BIN = Path("/www/server/nginx/sbin/nginx")
_UNIT = Path("/etc/systemd/system/mediavault.service")
_RESERVED = {22, 25, 888}


class ServerSettings(BaseModel):
    app_name: str = "PornWeb"
    http_port: int = Field(8099, ge=1, le=65535)
    bind_host: str = "127.0.0.1"
    public_port: int = Field(5588, ge=1, le=65535)
    media_root: str = ""
    env_file: str = ""
    restart_required: bool = False


class ServerSettingsUpdate(BaseModel):
    app_name: Optional[str] = None
    http_port: Optional[int] = Field(None, ge=1, le=65535)
    bind_host: Optional[str] = None
    public_port: Optional[int] = Field(None, ge=1, le=65535)
    media_root: Optional[str] = None


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
    if not _NGINX_VHOST.exists():
        raise HTTPException(500, "未找到 Nginx 站点配置")
    text = _NGINX_VHOST.read_text(encoding="utf-8")
    text = re.sub(r"^\s*listen\s+[^;]+;\s*\n", "", text, flags=re.M)
    if "server {" not in text:
        raise HTTPException(500, "Nginx 站点配置格式异常")
    text = text.replace("server {", f"server {{\n    listen {port};", 1)
    _NGINX_VHOST.write_text(text, encoding="utf-8")
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


def _current() -> ServerSettings:
    env = _read_env(_ENV_PATH)
    return ServerSettings(
        app_name=env.get("APP_NAME") or settings.APP_NAME,
        http_port=int(env.get("HTTP_PORT") or settings.HTTP_PORT),
        bind_host=env.get("BIND_HOST") or settings.BIND_HOST,
        public_port=int(env.get("PUBLIC_PORT") or settings.PUBLIC_PORT),
        media_root=env.get("MEDIA_ROOT") or settings.MEDIA_ROOT,
        env_file=str(_ENV_PATH),
        restart_required=False,
    )


@router.get("/", response_model=ServerSettings)
async def get_settings(user: User = Depends(get_current_user)):
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
    if updates:
        _write_env_all(updates)
    if restart:
        _apply_bind(cur.bind_host, cur.http_port)
        _schedule_backend_restart()
    cur.env_file = str(_ENV_PATH)
    cur.restart_required = restart and not _UNIT.exists()
    return cur
