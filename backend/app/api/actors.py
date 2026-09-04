"""演员表 API：从 media_items.cast_list（NFO JSON）聚合演员列表与作品。"""
import json
from typing import List, Optional
from urllib.parse import unquote

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models.media import MediaItem
from ..models.user import User
from ..models.progress import PlaybackProgress
from .deps import get_current_user
from .media import MediaResponse, MediaListResponse, _to_response

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
    name: str
    count: int
    poster_url: str = ""  # /api/media/poster/{id}，前端再拼 token
    poster_media_id: Optional[int] = None


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
        select(MediaItem.id, MediaItem.cast_list, MediaItem.poster_url).order_by(
            desc(MediaItem.created_at)
        )
    ).all()

    # name -> {count, poster_media_id}
    agg: dict = {}
    for mid, cast_raw, poster in rows:
        for name in _parse_cast(cast_raw):
            entry = agg.get(name)
            if entry is None:
                agg[name] = {
                    "count": 1,
                    "poster_media_id": mid if poster else None,
                }
            else:
                entry["count"] += 1
                if entry["poster_media_id"] is None and poster:
                    entry["poster_media_id"] = mid

    q = (search or "").strip().lower()
    items: List[ActorItem] = []
    for name, info in agg.items():
        if q and q not in name.lower():
            continue
        pid = info["poster_media_id"]
        items.append(
            ActorItem(
                name=name,
                count=info["count"],
                poster_media_id=pid,
                poster_url=f"/api/media/poster/{pid}" if pid else "",
            )
        )

    items.sort(key=lambda a: (-a.count, a.name))
    return ActorListResponse(items=items, total=len(items))


@router.get("/by-name", response_model=MediaListResponse)
async def actor_media_by_query(
    name: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(40, ge=1, le=100),
    sort: str = Query("newest"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """按查询参数取演员作品（CJK 友好备选）。"""
    return await _actor_media(_decode_name(name), page, page_size, sort, db, user)


@router.get("/{name}", response_model=MediaListResponse)
async def actor_media(
    name: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(40, ge=1, le=100),
    sort: str = Query("newest"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """按路径参数取演员作品；name 需 URL 编码（含 CJK）。"""
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
    matched = [i for i in all_items if name in _parse_cast(i.cast_list)]
    if not matched:
        # 仍返回空列表，前端显示空态；不强制 404（方便搜索拼写）
        pass

    total = len(matched)
    start = (page - 1) * page_size
    page_items = matched[start : start + page_size]

    prog_rows = db.execute(
        select(PlaybackProgress).where(PlaybackProgress.user_id == user.id)
    )
    pmap = {p.media_id: p for p in prog_rows.scalars()}
    return MediaListResponse(
        items=[_to_response(i, pmap.get(i.id)) for i in page_items],
        total=total,
        page=page,
        page_size=page_size,
    )
