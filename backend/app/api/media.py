import os
import json
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, func, or_, desc
from pydantic import BaseModel
from typing import Optional, List
from ..core.database import get_db
from ..core.config import settings
from ..models.media import MediaItem
from ..models.user import User
from ..models.progress import PlaybackProgress
from .deps import get_current_user, get_current_admin
from ..services.scanner import scan_directory

router = APIRouter(prefix="/api/media", tags=["media"])

class MediaResponse(BaseModel):
    id: int
    title: str
    original_title: str
    plot: str
    year: Optional[int]
    genre: str
    rating: Optional[float]
    director: str
    cast_list: str
    poster_url: str
    fanart_url: str
    category: str
    filename: str
    file_size: int
    folder: str
    created_at: str
    extra_files: list = []
    duration: float = 0
    progress: float = 0
    progress_part: int = 0
    
    class Config:
        from_attributes = True

class MediaListResponse(BaseModel):
    items: List[MediaResponse]
    total: int
    page: int
    page_size: int

class ScanRequest(BaseModel):
    folder: str = ""

class ScanResponse(BaseModel):
    added: int = 0
    updated: int = 0
    total: int = 0
    removed: int = 0
    error: Optional[str] = None
    status: Optional[str] = None
    job_id: Optional[int] = None
    library_id: Optional[int] = None
    found: int = 0
    processed: int = 0
    message: Optional[str] = None
    phase: Optional[str] = None
    current: Optional[str] = None

def _parts(item: MediaItem) -> list:
    try:
        data = json.loads(item.extra_files or "[]")
        return data if isinstance(data, list) else []
    except Exception:
        return []

def _to_response(item: MediaItem, progress=None) -> MediaResponse:
    return MediaResponse(
        id=item.id, title=item.title or item.filename,
        original_title=item.original_title or "", plot=item.plot or "",
        year=item.year, genre=item.genre or "", rating=item.rating,
        director=item.director or "", cast_list=item.cast_list or "[]",
        poster_url=item.poster_url or "", fanart_url=item.fanart_url or "",
        category=item.category or "movie", filename=item.filename,
        file_size=item.file_size or 0, folder=item.folder or "/",
        created_at=item.created_at.isoformat() if item.created_at else "",
        extra_files=_parts(item),
        duration=float(item.duration or 0),
        progress=float(progress.position) if progress else 0,
        progress_part=int(progress.part) if progress else 0,
    )

@router.get("/list", response_model=MediaListResponse)
async def list_media(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
    search: Optional[str] = None,
    genre: Optional[str] = None,
    folder: Optional[str] = None,
    sort: str = Query("newest"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    # 媒体库对所有登录用户共享（Jellyfin/Emby 逻辑）
    query = select(MediaItem)
    count_query = select(func.count(MediaItem.id))
    
    if category:
        query = query.where(MediaItem.category == category)
        count_query = count_query.where(MediaItem.category == category)
    
    if search:
        search_filter = or_(
            MediaItem.title.ilike(f"%{search}%"),
            MediaItem.filename.ilike(f"%{search}%"),
            MediaItem.director.ilike(f"%{search}%")
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)
    
    if genre:
        query = query.where(MediaItem.genre.ilike(f"%{genre}%"))
        count_query = count_query.where(MediaItem.genre.ilike(f"%{genre}%"))
    
    if folder:
        # 兼容 D:\foo 与 D:/foo
        folder_fwd = folder.replace("\\", "/")
        folder_bwd = folder.replace("/", "\\")
        query = query.where(or_(
            MediaItem.folder.startswith(folder),
            MediaItem.folder.startswith(folder_fwd),
            MediaItem.folder.startswith(folder_bwd),
        ))
        count_query = count_query.where(or_(
            MediaItem.folder.startswith(folder),
            MediaItem.folder.startswith(folder_fwd),
            MediaItem.folder.startswith(folder_bwd),
        ))
    
    if sort == "newest":
        query = query.order_by(desc(MediaItem.created_at))
    elif sort == "title":
        query = query.order_by(MediaItem.title)
    elif sort == "rating":
        query = query.order_by(desc(MediaItem.rating))
    elif sort == "year":
        query = query.order_by(desc(MediaItem.year))
    
    total_result = db.execute(count_query)
    total = total_result.scalar()
    
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = db.execute(query)
    items = result.scalars().all()
    prog_rows = db.execute(select(PlaybackProgress).where(PlaybackProgress.user_id == user.id))
    pmap = {p.media_id: p for p in prog_rows.scalars()}
    return MediaListResponse(
        items=[_to_response(i, pmap.get(i.id)) for i in items],
        total=total, page=page, page_size=page_size
    )

@router.get("/detail/{media_id}", response_model=MediaResponse)
async def get_detail(
    media_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    result = db.execute(
        select(MediaItem).where(MediaItem.id == media_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="媒体不存在")
    prow = db.execute(select(PlaybackProgress).where(
        PlaybackProgress.user_id == user.id, PlaybackProgress.media_id == media_id))
    return _to_response(item, prow.scalar_one_or_none())

async def _auth_user(request: Request, token: Optional[str], db: Session) -> Optional[User]:
    from ..core.security import decode_token
    user = None
    auth_header = request.headers.get("authorization", "")
    raw = None
    if auth_header.startswith("Bearer "):
        raw = auth_header[7:]
    elif token:
        raw = token
    if not raw:
        return None
    payload = decode_token(raw)
    if not payload:
        return None
    uid = payload.get("sub")
    if not uid:
        return None
    result = db.execute(select(User).where(User.id == int(uid)))
    return result.scalar_one_or_none()

@router.get("/poster/{media_id}")
async def get_poster(
    media_id: int,
    request: Request,
    token: str = Query(None),
    db: Session = Depends(get_db),
):
    user = await _auth_user(request, token, db)
    if not user:
        raise HTTPException(status_code=401, detail="未授权")
    result = db.execute(
        select(MediaItem).where(MediaItem.id == media_id)
    )
    item = result.scalar_one_or_none()
    if not item or not item.poster_url:
        raise HTTPException(status_code=404, detail="海报不存在")
    
    poster = item.poster_url
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
                ".webp": "image/webp", ".bmp": "image/bmp", ".gif": "image/gif"}

    def _image_response(path: str):
        mt = mime_map.get(Path(path).suffix.lower(), "image/jpeg")
        return FileResponse(path, media_type=mt,
                          headers={"Cache-Control": "no-cache, must-revalidate"})

    # If it's a local file path
    if os.path.isabs(poster) and Path(poster).exists():
        return _image_response(poster)
    
    # If it's a relative path
    if not poster.startswith("http"):
        full_path = Path(settings.MEDIA_ROOT) / poster
        if full_path.exists():
            return _image_response(str(full_path))
    
    # If it's a URL, redirect
    if poster.startswith("http"):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=poster)
    
    raise HTTPException(status_code=404, detail="海报文件不存在")

@router.get("/fanart/{media_id}")
async def get_fanart(
    media_id: int,
    request: Request,
    token: str = Query(None),
    db: Session = Depends(get_db),
):
    user = await _auth_user(request, token, db)
    if not user:
        raise HTTPException(status_code=401, detail="未授权")
    result = db.execute(
        select(MediaItem).where(MediaItem.id == media_id)
    )
    item = result.scalar_one_or_none()
    if not item or not item.fanart_url:
        raise HTTPException(status_code=404, detail="背景图不存在")
    
    fanart = item.fanart_url
    
    if os.path.isabs(fanart) and Path(fanart).exists():
        return FileResponse(fanart, media_type="image/jpeg")
    
    if not fanart.startswith("http"):
        full_path = Path(settings.MEDIA_ROOT) / fanart
        if full_path.exists():
            return FileResponse(str(full_path), media_type="image/jpeg")
    
    if fanart.startswith("http"):
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=fanart)
    
    raise HTTPException(status_code=404, detail="背景图不存在")

@router.get("/stream/{media_id}")
async def stream_media(
    media_id: int,
    request: Request,
    token: str = Query(None),
    part: int = Query(0),
    db: Session = Depends(get_db),
):
    user = await _auth_user(request, token, db)
    if not user:
        raise HTTPException(status_code=401, detail="未授权")
    
    result = db.execute(
        select(MediaItem).where(MediaItem.id == media_id)
    )
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="媒体不存在")

    chosen = item.file_path
    parts = _parts(item)
    if parts:
        idx = part if 0 <= part < len(parts) else 0
        chosen = parts[idx].get("path") or item.file_path

    if os.path.isabs(chosen):
        file_path = Path(chosen)
    else:
        file_path = Path(settings.MEDIA_ROOT) / chosen
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="文件不存在")
    
    file_size = file_path.stat().st_size
    ext = file_path.suffix.lower()
    content_type_map = {
        ".mp4": "video/mp4", ".mkv": "video/x-matroska", ".avi": "video/x-msvideo",
        ".mov": "video/quicktime", ".wmv": "video/x-ms-wmv", ".flv": "video/x-flv",
        ".ts": "video/mp2t", ".m4v": "video/mp4", ".webm": "video/webm",
    }
    content_type = content_type_map.get(ext, "video/mp4")
    
    range_header = request.headers.get("range")
    if range_header and range_header.startswith("bytes="):
        range_spec = range_header.replace("bytes=", "").split(",")[0]
        parts = range_spec.split("-")
        try:
            start = int(parts[0]) if parts[0] else 0
            end = int(parts[1]) if len(parts) > 1 and parts[1] else file_size - 1
        except ValueError:
            start, end = 0, file_size - 1
        start = max(0, start)
        end = min(end, file_size - 1)
        if start > end:
            start, end = 0, file_size - 1
        content_length = end - start + 1
        
        def iter_file():
            with open(file_path, "rb") as f:
                f.seek(start)
                remaining = content_length
                while remaining > 0:
                    chunk_size = min(65536, remaining)
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk
        
        return StreamingResponse(
            iter_file(), status_code=206, media_type=content_type,
            headers={
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(content_length),
            }
        )
    
    def iter_file():
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                yield chunk
    
    return StreamingResponse(
        iter_file(), media_type=content_type,
        headers={"Accept-Ranges": "bytes", "Content-Length": str(file_size)}
    )

@router.post("/scan", response_model=ScanResponse)
async def scan_media(
    req: ScanRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    from ..models.library import MediaLibrary
    from pathlib import Path as _P
    from ..services.scan_runner import start_scan
    folder = (req.folder or "").strip()
    lib_id = None
    hint = ""
    if folder:
        norm = str(_P(folder)).replace("/", os.sep).rstrip("\\/")
        exists = db.execute(select(MediaLibrary))
        already = None
        for lib in exists.scalars():
            if str(_P(lib.path)).replace("/", os.sep).rstrip("\\/").lower() == norm.lower():
                already = lib
                break
        if already is None:
            lib = MediaLibrary(name=_P(norm).name or norm, path=norm, type="movie")
            db.add(lib)
            db.commit()
            db.refresh(lib)
            lib_id = lib.id
            hint = "movie"
        else:
            lib_id = already.id
            hint = already.type or ""
    result = start_scan(admin.id, folder or settings.MEDIA_ROOT, library_id=lib_id, category_hint=hint)
    return ScanResponse(
        added=result.get("added") or 0,
        updated=result.get("updated") or 0,
        total=result.get("total") or 0,
        removed=result.get("removed") or 0,
        error=result.get("error"),
        status=result.get("status"),
        job_id=result.get("job_id"),
        library_id=result.get("library_id") or lib_id,
        found=result.get("found") or 0,
        processed=result.get("processed") or 0,
        message=result.get("message"),
        phase=result.get("phase"),
        current=result.get("current"),
    )

class ProgressIn(BaseModel):
    position: float
    duration: float = 0
    part: int = 0

@router.put("/progress/{media_id}")
async def save_progress(
    media_id: int,
    req: ProgressIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    item = (db.execute(select(MediaItem).where(MediaItem.id == media_id))).scalar_one_or_none()
    if not item:
        raise HTTPException(404, "媒体不存在")
    row = (db.execute(select(PlaybackProgress).where(
        PlaybackProgress.user_id == user.id, PlaybackProgress.media_id == media_id
    ))).scalar_one_or_none()
    if row:
        row.position = max(0, req.position)
        row.part = max(0, req.part)
        if req.duration > 0:
            row.duration = req.duration
            item.duration = req.duration
    else:
        db.add(PlaybackProgress(
            user_id=user.id, media_id=media_id,
            position=max(0, req.position), duration=req.duration or 0, part=max(0, req.part)
        ))
        if req.duration > 0:
            item.duration = req.duration
    db.commit()
    return {"ok": True}

@router.get("/continue", response_model=MediaListResponse)
async def continue_watching(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    rows = (db.execute(
        select(PlaybackProgress).where(
            PlaybackProgress.user_id == user.id,
            PlaybackProgress.position > 10
        ).order_by(desc(PlaybackProgress.updated_at))
    )).scalars().all()
    items = []
    for p in rows:
        if p.duration and p.position >= p.duration * 0.95:
            continue
        item = (db.execute(select(MediaItem).where(MediaItem.id == p.media_id))).scalar_one_or_none()
        if item:
            items.append(_to_response(item, p))
    return MediaListResponse(items=items, total=len(items), page=1, page_size=len(items) or 20)

@router.delete("/library")
async def delete_library(
    path: str = Query(...),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    """Delete a library and all its media items."""
    from ..services.scanner import delete_media_by_folder
    removed = delete_media_by_folder(path, db)
    return {"message": f"已删除 {removed} 个媒体条目", "removed": removed}

@router.delete("/{media_id}")
async def delete_media(
    media_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    result = db.execute(select(MediaItem).where(MediaItem.id == media_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="媒体不存在")
    db.delete(item)
    db.commit()
    return {"message": "已删除"}

@router.get("/genres")
async def list_genres(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    result = db.execute(
        select(MediaItem.genre).where(MediaItem.genre != "")
    )
    genres = set()
    for row in result.scalars():
        for g in row.split(","):
            g = g.strip()
            if g:
                genres.add(g)
    return sorted(genres)
