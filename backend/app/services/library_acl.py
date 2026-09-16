"""Per-user media library access control helpers."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, List, Optional, Set

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..models.library import MediaLibrary
from ..models.media import MediaItem
from ..models.user import User
from ..models.user_library_access import UserLibraryAccess

LIBRARY_DENIED_DETAIL = "无权访问该媒体所在媒体库"


def norm_path(p: str) -> str:
    if not p:
        return ""
    return str(Path(p)).replace("/", os.sep).rstrip("\\/")


def path_in_library(folder: str, lib_path: str) -> bool:
    npath = norm_path(lib_path).lower()
    folder_n = norm_path(folder or "").lower()
    if not npath:
        return False
    sep = os.sep.lower()
    return (
        folder_n == npath
        or folder_n.startswith(npath + sep)
        or folder_n.startswith(npath + "/")
    )


def allowed_library_ids(db: Session, user: User) -> Optional[Set[int]]:
    """None = unrestricted (admin). Empty set = no libraries."""
    if getattr(user, "is_admin", False):
        return None
    rows = db.execute(
        select(UserLibraryAccess.library_id).where(UserLibraryAccess.user_id == user.id)
    ).scalars().all()
    return set(int(x) for x in rows)


def list_allowed_libraries(db: Session, user: User) -> List[MediaLibrary]:
    ids = allowed_library_ids(db, user)
    q = select(MediaLibrary).order_by(MediaLibrary.id)
    if ids is None:
        return list(db.execute(q).scalars().all())
    if not ids:
        return []
    return list(db.execute(q.where(MediaLibrary.id.in_(ids))).scalars().all())


def grant_libraries(db: Session, user_id: int, library_ids: Iterable[int]) -> None:
    """Replace ACL rows for user with the given library id set (deduped)."""
    wanted = sorted({int(x) for x in library_ids})
    existing = list(
        db.execute(
            select(UserLibraryAccess).where(UserLibraryAccess.user_id == user_id)
        ).scalars().all()
    )
    have = {r.library_id: r for r in existing}
    for lid, row in list(have.items()):
        if lid not in wanted:
            db.delete(row)
    for lid in wanted:
        if lid not in have:
            db.add(UserLibraryAccess(user_id=user_id, library_id=lid))


def grant_all_libraries(db: Session, user_id: int) -> int:
    """Grant every current media library to user. Returns count granted."""
    lids = list(db.execute(select(MediaLibrary.id)).scalars().all())
    grant_libraries(db, user_id, lids)
    return len(lids)


def library_id_for_media(db: Session, item: MediaItem) -> Optional[int]:
    """Best-effort map media folder → library id (longest matching path wins)."""
    libs = list(db.execute(select(MediaLibrary)).scalars().all())
    best = None
    best_len = -1
    folder = item.folder or ""
    for lib in libs:
        if path_in_library(folder, lib.path):
            n = len(norm_path(lib.path))
            if n > best_len:
                best_len = n
                best = lib.id
    return best


def media_allowed(db: Session, user: User, item: MediaItem) -> bool:
    ids = allowed_library_ids(db, user)
    if ids is None:
        return True
    if not ids:
        return False
    lid = library_id_for_media(db, item)
    if lid is None:
        return False
    return lid in ids


def assert_media_library_access(db: Session, user: User, item: MediaItem) -> None:
    if not media_allowed(db, user, item):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=LIBRARY_DENIED_DETAIL
        )


def apply_media_acl_filter(query, db: Session, user: User):
    """Restrict a MediaItem select/count query to allowed library path prefixes."""
    ids = allowed_library_ids(db, user)
    if ids is None:
        return query
    if not ids:
        return query.where(MediaItem.id == -1)
    libs = list(
        db.execute(select(MediaLibrary).where(MediaLibrary.id.in_(ids))).scalars().all()
    )
    clauses = []
    for lib in libs:
        npath = norm_path(lib.path)
        if not npath:
            continue
        folder_fwd = npath.replace("\\", "/")
        folder_bwd = npath.replace("/", "\\")
        clauses.append(MediaItem.folder.startswith(npath))
        if folder_fwd != npath:
            clauses.append(MediaItem.folder.startswith(folder_fwd))
        if folder_bwd != npath:
            clauses.append(MediaItem.folder.startswith(folder_bwd))
    if not clauses:
        return query.where(MediaItem.id == -1)
    return query.where(or_(*clauses))
