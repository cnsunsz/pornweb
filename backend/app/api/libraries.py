import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, List
from ..core.database import get_db
from ..models.library import MediaLibrary
from ..models.media import MediaItem
from ..models.user import User
from .deps import get_current_user, get_current_admin
from ..services.scanner import scan_directory, delete_media_by_folder
from ..core.config import settings

router = APIRouter(prefix="/api/libraries", tags=["libraries"])


class LibraryIn(BaseModel):
    name: str
    path: str
    type: str = "movie"


class LibraryOut(BaseModel):
    id: int
    name: str
    path: str
    type: str
    count: int = 0
    poster_id: Optional[int] = None


def _norm(p: str) -> str:
    if not p:
        return ""
    return str(Path(p)).replace("/", os.sep).rstrip("\\/")


def _to_out(lib: MediaLibrary, count: int = 0, poster_id: Optional[int] = None) -> LibraryOut:
    return LibraryOut(
        id=lib.id, name=lib.name, path=lib.path, type=lib.type,
        count=count, poster_id=poster_id
    )


@router.get("/", response_model=List[LibraryOut])
async def list_libraries(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    result = db.execute(select(MediaLibrary).order_by(MediaLibrary.id))
    libs = result.scalars().all()
    media_result = db.execute(select(MediaItem))
    items = media_result.scalars().all()

    out = []
    for lib in libs:
        npath = _norm(lib.path).lower()
        count = 0
        poster_id = None
        for item in items:
            folder = _norm(item.folder or "").lower()
            if folder == npath or folder.startswith(npath + os.sep.lower()) or folder.startswith(npath + "/"):
                count += 1
                if poster_id is None and item.poster_url:
                    poster_id = item.id
        out.append(_to_out(lib, count, poster_id))
    return out


@router.post("/", response_model=LibraryOut)
async def create_library(
    req: LibraryIn,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    name = (req.name or "").strip()
    path = _norm(req.path.strip())
    if not path:
        raise HTTPException(400, "路径不能为空")
    if not name:
        name = Path(path).name or path
    if not Path(path).exists():
        raise HTTPException(400, f"路径不存在: {path}")
    if req.type not in ("movie", "tvshow", "mixed"):
        raise HTTPException(400, "类型无效")

    exists = db.execute(select(MediaLibrary))
    for lib in exists.scalars():
        if _norm(lib.path).lower() == path.lower():
            raise HTTPException(400, "该路径已添加过媒体库")

    lib = MediaLibrary(name=name, path=path, type=req.type)
    db.add(lib)
    db.commit()
    db.refresh(lib)
    return _to_out(lib)


@router.delete("/{lib_id}")
async def delete_library(
    lib_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    result = db.execute(select(MediaLibrary).where(MediaLibrary.id == lib_id))
    lib = result.scalar_one_or_none()
    if not lib:
        raise HTTPException(404, "媒体库不存在")
    removed = delete_media_by_folder(lib.path, db)
    db.delete(lib)
    db.commit()
    return {"message": f"已删除媒体库，清理 {removed} 个条目", "removed": removed}


@router.post("/{lib_id}/scan")
async def scan_library(
    lib_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    result = db.execute(select(MediaLibrary).where(MediaLibrary.id == lib_id))
    lib = result.scalar_one_or_none()
    if not lib:
        raise HTTPException(404, "媒体库不存在")
    scan_result = scan_directory(
        settings.MEDIA_ROOT, admin.id, db, lib.path, category_hint=lib.type or ""
    )
    return scan_result


class LibraryPatch(BaseModel):
    name: Optional[str] = None
    type: Optional[str] = None


@router.put("/{lib_id}", response_model=LibraryOut)
async def update_library(
    lib_id: int,
    req: LibraryPatch,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    result = db.execute(select(MediaLibrary).where(MediaLibrary.id == lib_id))
    lib = result.scalar_one_or_none()
    if not lib:
        raise HTTPException(404, "媒体库不存在")
    if req.name is not None:
        name = req.name.strip()
        if not name:
            raise HTTPException(400, "名称不能为空")
        lib.name = name
    if req.type is not None:
        if req.type not in ("movie", "tvshow", "mixed"):
            raise HTTPException(400, "类型无效")
        lib.type = req.type
    db.commit()
    db.refresh(lib)
    return _to_out(lib)
