from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select
from pathlib import Path
import os
from ..core.database import get_db
from ..models.library import MediaLibrary
from ..models.media import MediaItem
from ..models.user import User
from .deps import get_current_user

router = APIRouter(prefix="/api/media", tags=["folders"])


def _norm(p: str) -> str:
    if not p:
        return ""
    return str(Path(p)).replace("/", os.sep).rstrip("\\/")


@router.get("/folders")
async def list_folders(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """List libraries from the persisted library table (Jellyfin-style names)."""
    result = db.execute(select(MediaLibrary).order_by(MediaLibrary.id))
    libs = result.scalars().all()
    media_result = db.execute(select(MediaItem))
    items = media_result.scalars().all()

    if libs:
        folders = []
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
            folders.append({
                "id": lib.id,
                "path": lib.path,
                "name": lib.name,
                "count": count,
                "poster_id": poster_id,
                "type": lib.type,
            })
        return folders

    # Fallback: no library rows yet — group by parent of each movie folder
    lib_map = {}
    for item in items:
        folder = _norm(item.folder or "")
        parent = str(Path(folder).parent) if folder else folder
        key = parent.lower()
        if key not in lib_map:
            lib_map[key] = {"path": parent, "count": 0, "poster_id": None}
        lib_map[key]["count"] += 1
        if not lib_map[key]["poster_id"] and item.poster_url:
            lib_map[key]["poster_id"] = item.id
    folders = []
    for info in lib_map.values():
        display = Path(info["path"]).name or info["path"]
        folders.append({
            "id": None,
            "path": info["path"],
            "name": display,
            "count": info["count"],
            "poster_id": info["poster_id"],
            "type": "movie",
        })
    return folders
