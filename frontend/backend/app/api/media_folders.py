from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from ..core.database import get_db
from ..models.media import MediaItem
from ..models.user import User
from .deps import get_current_user

router = APIRouter(prefix="/api/media", tags=["folders"])

@router.get("/folders")
async def list_folders(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """List unique folders (library categories) with item counts."""
    result = await db.execute(
        select(MediaItem.folder, func.count(MediaItem.id))
        .where(MediaItem.user_id == user.id)
        .group_by(MediaItem.folder)
        .order_by(func.count(MediaItem.id).desc())
    )
    folders = []
    for folder, count in result:
        if folder:
            name = folder.replace("\\", "/").rstrip("/").split("/")[-1] or folder
            folders.append({"path": folder, "name": name, "count": count})
    return folders

@router.get("/continue")
async def continue_watching(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Return all items for continue watching (position is stored client-side)."""
    result = await db.execute(
        select(MediaItem)
        .where(MediaItem.user_id == user.id)
        .order_by(MediaItem.updated_at.desc())
        .limit(20)
    )
    from .media import _to_response
    return [_to_response(i) for i in result.scalars()]
