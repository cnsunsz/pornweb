"""Test API that calls the Huangguo edge envelope.

These routes never write to PornWeb libraries. They exist so the official
HGhub wire protocol can be exercised from this project.
"""

from __future__ import annotations

from time import perf_counter
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..models.user import User
from ..services.hghub_edge import DEFAULT_BASE, FIXED_LINES, edge_request, normalize_base
from .deps import require_media_access

router = APIRouter(prefix="/api/hghub-test", tags=["transfer"])


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=502, detail=str(exc))


async def _call(method: str, path: str, **kwargs) -> dict[str, Any]:
    started = perf_counter()
    try:
        base = normalize_base(kwargs.get("base"))
        data = await edge_request(method, path, **kwargs)
    except Exception as exc:
        raise _http_error(exc) from exc
    return {
        "ok": True,
        "test_only": True,
        "base": base,
        "method": method,
        "path": path,
        "elapsed_ms": int((perf_counter() - started) * 1000),
        "data": data,
    }


@router.get("/lines")
async def list_lines(_admin: User = Depends(require_media_access)):
    return {
        "default": DEFAULT_BASE,
        "fixed": list(FIXED_LINES),
        "test_only": True,
        "note": "仅供管理员测试，不会写入 PornWeb 媒体库",
    }


@router.get("/feed")
async def feed(
    page: int = Query(1, ge=1, le=100),
    size: int = Query(10, ge=1, le=50),
    base: str | None = None,
    _admin: User = Depends(require_media_access),
):
    return await _call("GET", f"/api/videos?page={page}&size={size}", base=base)


@router.get("/search")
async def search(
    q: str = Query(..., min_length=1, max_length=80),
    page: int = Query(1, ge=1, le=100),
    size: int = Query(10, ge=1, le=50),
    base: str | None = None,
    _admin: User = Depends(require_media_access),
):
    from urllib.parse import quote
    return await _call("GET", f"/api/search?q={quote(q)}&page={page}&size={size}", base=base)


@router.get("/video/{video_id}")
async def video_detail(
    video_id: int,
    base: str | None = None,
    _admin: User = Depends(require_media_access),
):
    if video_id <= 0:
        raise HTTPException(status_code=400, detail="视频 ID 无效")
    return await _call("GET", f"/api/videos/{video_id}", base=base)


class EdgeIn(BaseModel):
    method: str = "GET"
    path: str = Field(..., min_length=5, max_length=300)
    body: Any | None = None
    base: str | None = None
    token: str | None = Field(default=None, max_length=4096)


@router.post("/edge")
async def raw_edge(payload: EdgeIn, _admin: User = Depends(require_media_access)):
    return await _call(
        payload.method,
        payload.path,
        body=payload.body,
        token=payload.token or None,
        base=payload.base,
    )
