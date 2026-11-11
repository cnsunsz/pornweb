"""Huangguo / HGhub edge-envelope client, for admin testing only.

The official client folds every logical `/api/**` call into one real request:

    POST {origin}/api/edge/request
    {"method","path","body"(Base64 JSON),"content_type"}

Success payload is `{"status": 1, "data": ...}`. This module does not write
to the PornWeb media library and does not follow unofficial mirror hosts.
"""

from __future__ import annotations

import base64
import json
from typing import Any
from urllib.parse import urlparse

import httpx

DEFAULT_BASE = "https://huangguoai.com"
FIXED_LINES = (
    {"name": "固定线路 1", "url": "https://huangguoai.com"},
    {"name": "固定线路 2", "url": "https://huangguoai.ai"},
)
_ALLOWED = frozenset(item["url"] for item in FIXED_LINES)
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def normalize_base(url: str | None) -> str:
    raw = (url or DEFAULT_BASE).strip().rstrip("/")
    parsed = urlparse(raw)
    if parsed.scheme != "https" or not parsed.netloc or parsed.path not in ("", "/") or parsed.query or parsed.fragment or parsed.username:
        raise ValueError("线路地址无效，仅允许官方 HTTPS 固定线路")
    origin = f"https://{parsed.netloc.lower()}"
    if origin not in _ALLOWED:
        raise ValueError("仅允许官方固定线路 huangguoai.com / huangguoai.ai")
    return origin


def _encode_body(body: Any | None) -> tuple[str, str]:
    if body is None:
        return "", ""
    raw = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(raw).decode("ascii"), "application/json"


async def edge_request(
    method: str,
    path: str,
    *,
    body: Any | None = None,
    token: str | None = None,
    base: str | None = None,
    timeout: float = 20.0,
) -> Any:
    origin = normalize_base(base)
    method = (method or "GET").upper().strip()
    if method not in {"GET", "POST", "PUT", "DELETE", "PATCH"}:
        raise ValueError("请求方法无效")
    path = (path or "").strip()
    if not path.startswith("/api/"):
        raise ValueError("逻辑路径必须以 /api/ 开头")
    if "\r" in path or "\n" in path:
        raise ValueError("逻辑路径无效")

    encoded, ctype = _encode_body(body)
    envelope = {
        "method": method,
        "path": path,
        "body": encoded,
        "content_type": ctype,
    }
    headers = {
        "User-Agent": _UA,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Referer": f"{origin}/",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = f"{origin}/api/edge/request"
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            resp = await client.post(url, json=envelope, headers=headers)
    except httpx.TimeoutException as exc:
        raise RuntimeError("黄果接口请求超时") from exc
    except httpx.HTTPError as exc:
        raise RuntimeError("无法连接黄果接口") from exc

    if resp.status_code in (401, 403):
        raise RuntimeError("黄果接口返回未授权")
    if resp.status_code >= 400:
        text = (resp.text or "")[:160]
        raise RuntimeError(f"黄果接口 HTTP {resp.status_code}: {text}")

    text = resp.text or ""
    if not text.strip():
        return None
    try:
        value = resp.json()
    except ValueError as exc:
        raise RuntimeError(f"黄果接口返回不是 JSON: {text[:160]}") from exc

    if isinstance(value, dict) and value.get("status") == 1:
        return value.get("data")
    if isinstance(value, dict):
        msg = value.get("msg") or "接口返回失败"
        raise RuntimeError(str(msg))
    return value
