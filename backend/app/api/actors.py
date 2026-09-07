"""演员表 API：从 media_items.cast_list（NFO JSON）聚合演员列表与作品。

Android / Web 共用稳定契约（Bearer JWT，与 /api/media 相同）：
  GET /api/actors
    → { items: [{ name, count, poster_url, poster_media_id }], total }
      poster_url: 有在线头像缓存时为 `/api/actors/photo?name=…`，否则空串。
      禁止用作品 `/api/media/poster/{id}` 冒充演员头像。
  GET /api/actors/photo?name=…&token=…
    → 在线头像图（TMDB person）；没有则 404（客户端留空，勿用占位乱图）
  GET /api/actors/{name}/media   （推荐；name 须 URL 编码，含 CJK）
    → MediaListResponse 同 /api/media/list
  兼容别名：GET /api/actors/{name} 、 GET /api/actors/by-name?name=
"""
import json
from typing import List, Optional
from urllib.parse import unquote

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models.media import MediaItem
from ..models.user import User
from ..models.progress import PlaybackProgress
from .deps import get_current_user
from .media import MediaListResponse, _to_response, _auth_user

router = APIRouter(prefix="/api/actors", tags=["actors"])

# 跳过无意义占位；保留「佚名」等真实写入的名字
_SKIP_NAMES = {
    "",
    "-",
    "--",
    "n/a",
    "na",
    "unknown",
    "none",
    "null",
    "undefined",
    "演员",
    "出演",
    "cast",
}


def _parse_cast(raw: Optional[str]) -> List[str]:
    """稳健解析 cast_list JSON；trim；过滤空/占位。"""
    if not raw:
        return []
    text = raw.strip()
    if not text:
        return []
    names: List[str] = []
    try:
        data = json.loads(text)
        if isinstance(data, list):
            for x in data:
                if x is None:
                    continue
                if isinstance(x, dict):
                    n = (x.get("name") or x.get("Name") or "").strip()
                    if n:
                        names.append(n)
                    continue
                names.append(str(x).strip())
        elif isinstance(data, str):
            names.append(data.strip())
    except Exception:
        # 非 JSON：按常见分隔符拆
        for part in text.replace("、", ",").replace("，", ",").replace("/", ",").split(","):
            names.append(part.strip())
    out: List[str] = []
    seen = set()
    for n in names:
        if not n:
            continue
        key = n.lower()
        if key in _SKIP_NAMES:
            continue
        if n in seen:
            continue
        seen.add(n)
        out.append(n)
    return out


class ActorItem(BaseModel):
    """稳定字段供 Android / Web 共用；poster_url 为相对路径，需带 Authorization 或 ?token=。"""
    name: str
    count: int
    poster_url: str = ""  # `/api/actors/photo?name=…` 或空；禁止作品海报
    poster_media_id: Optional[int] = Field(
        default=None,
        description="已废弃：不再用作品 id 冒充演员头像，恒为 null",
    )


class ActorListResponse(BaseModel):
    items: List[ActorItem]
    total: int


def _decode_name(name: str) -> str:
    # 路径/查询里可能双重编码；尽量还原 CJK
    n = name.strip()
    for _ in range(2):
        try:
            decoded = unquote(n)
        except Exception:
            break
        if decoded == n:
            break
        n = decoded
    return n.strip()


@router.get("", response_model=ActorListResponse)
async def list_actors(
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """列出库中所有可见媒体的演员（登录用户共享库，同 /api/media/list）。"""
    rows = db.execute(
        select(MediaItem.cast_list).order_by(desc(MediaItem.created_at))
    ).all()

    # name -> count（不再用作品海报冒充演员头像）
    agg: dict = {}
    for (cast_raw,) in rows:
        for name in _parse_cast(cast_raw):
            agg[name] = agg.get(name, 0) + 1

    from ..services.actor_photos import get_cached, public_photo_path

    q = (search or "").strip().lower()
    items: List[ActorItem] = []
    for name, count in agg.items():
        if q and q not in name.lower():
            continue
        # 仅当缓存已确认有在线头像时返回 URL；未查过/没有 → 空串
        # 客户端可用 GET /api/actors/photo?name= 主动拉取（404 则留空）
        cached = get_cached(db, name)
        poster = ""
        if cached and cached.status == "ok" and (cached.remote_url or "").strip():
            poster = public_photo_path(name)
        items.append(
            ActorItem(
                name=name,
                count=count,
                poster_media_id=None,
                poster_url=poster,
            )
        )

    items.sort(key=lambda a: (-a.count, a.name))
    return ActorListResponse(items=items, total=len(items))


@router.get("/photo")
async def actor_photo(
    request: Request,
    name: str = Query(..., min_length=1),
    token: str = Query(None),
    force: bool = Query(False),
    db: Session = Depends(get_db),
):
    """在线演员头像。没有真实头像时 404 — 客户端必须留空，禁止用作品图/占位乱图。"""
    user = await _auth_user(request, token, db)
    if not user:
        raise HTTPException(status_code=401, detail="未授权")
    n = _decode_name(name)
    if not n:
        raise HTTPException(status_code=404, detail="无演员头像")

    from ..services.actor_photos import resolve_remote_url

    remote, _source = await resolve_remote_url(db, n, force=force)
    if not remote:
        raise HTTPException(status_code=404, detail="无演员头像")

    import httpx

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Referer": "https://www.themoviedb.org/",
    }
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            r = await client.get(remote, headers=headers)
            if r.status_code != 200 or not r.content:
                raise HTTPException(status_code=404, detail="无演员头像")
            ctype = (r.headers.get("content-type") or "image/jpeg").split(";")[0].strip()
            if not ctype.startswith("image/"):
                ctype = "image/jpeg"
            return StreamingResponse(
                iter([r.content]),
                media_type=ctype,
                headers={"Cache-Control": "public, max-age=86400"},
            )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=404, detail="无演员头像")


@router.get("/by-name", response_model=MediaListResponse)
async def actor_media_by_query(
    name: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(40, ge=1, le=100),
    sort: str = Query("newest"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """查询参数取演员作品（CJK 友好备选，无需路径编码）。"""
    return await _actor_media(_decode_name(name), page, page_size, sort, db, user)


@router.get("/{name}/media", response_model=MediaListResponse)
async def actor_media_preferred(
    name: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(40, ge=1, le=100),
    sort: str = Query("newest"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """推荐：演员作品列表（Android / Web）。name 须 URL 编码。"""
    return await _actor_media(_decode_name(name), page, page_size, sort, db, user)


@router.get("/{name}", response_model=MediaListResponse)
async def actor_media_alias(
    name: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(40, ge=1, le=100),
    sort: str = Query("newest"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """兼容别名，等同 GET /api/actors/{name}/media。"""
    return await _actor_media(_decode_name(name), page, page_size, sort, db, user)


async def _actor_media(
    name: str,
    page: int,
    page_size: int,
    sort: str,
    db: Session,
    user: User,
) -> MediaListResponse:
    if not name:
        raise HTTPException(status_code=400, detail="演员名不能为空")

    query = select(MediaItem)
    if sort == "newest":
        query = query.order_by(desc(MediaItem.created_at))
    elif sort == "title":
        query = query.order_by(MediaItem.title)
    elif sort == "rating":
        query = query.order_by(desc(MediaItem.rating))
    elif sort == "year":
        query = query.order_by(desc(MediaItem.year))
    else:
        query = query.order_by(desc(MediaItem.created_at))

    all_items = db.execute(query).scalars().all()
    matched = []
    for item in all_items:
        names = _parse_cast(item.cast_list)
        if name in names:
            matched.append(item)

    total = len(matched)
    start = (page - 1) * page_size
    page_items = matched[start : start + page_size]

    # progress map
    ids = [i.id for i in page_items]
    prog_map = {}
    if ids:
        rows = db.execute(
            select(PlaybackProgress).where(
                PlaybackProgress.user_id == user.id,
                PlaybackProgress.media_id.in_(ids),
            )
        ).scalars().all()
        prog_map = {p.media_id: p for p in rows}

    return MediaListResponse(
        items=[_to_response(i, prog_map.get(i.id)) for i in page_items],
        total=total,
        page=page,
        page_size=page_size,
    )
