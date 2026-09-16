from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import BaseModel, Field
from typing import Optional, List
from ..core.database import get_db
from ..core.security import get_password_hash, verify_password
from ..models.user import User
from ..models.library import MediaLibrary
from .deps import get_current_user, get_current_admin, user_access_active, access_days_left, _aware
from ..services.library_acl import grant_libraries, grant_all_libraries, allowed_library_ids

router = APIRouter(prefix="/api/users", tags=["users"])
admin_router = APIRouter(prefix="/api/admin/users", tags=["admin-users"])


def _iso(dt) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _access_status(u: User) -> str:
    if u.is_admin:
        return "admin"
    exp = getattr(u, "access_expires_at", None)
    if exp is None:
        return "permanent"
    if not user_access_active(u):
        return "expired"
    return "active"


class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_admin: bool
    avatar: str
    created_at: str
    access_expires_at: Optional[str] = None
    access_active: bool = True
    access_days_left: Optional[int] = None
    access_status: str = "permanent"  # active|expired|permanent|admin

    class Config:
        from_attributes = True


class CreateUserRequest(BaseModel):
    username: str
    email: str
    password: str
    is_admin: bool = False


class UpdateUserRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    is_admin: Optional[bool] = None


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class RenewRequest(BaseModel):
    duration_days: Optional[int] = Field(None, description="Extend from max(now, current_expiry)")
    expires_at: Optional[str] = Field(None, description="Absolute ISO8601 expiry")
    permanent: Optional[bool] = Field(None, description="True → null expiry (permanent)")


class LibrariesPutRequest(BaseModel):
    library_ids: List[int] = Field(default_factory=list)


class LibrariesResponse(BaseModel):
    user_id: int
    library_ids: List[int]
    all_libraries: bool = False  # True for admin targets (unrestricted)


def _to_resp(u: User) -> UserResponse:
    return UserResponse(
        id=u.id,
        username=u.username,
        email=u.email,
        is_admin=u.is_admin,
        avatar=u.avatar or "",
        created_at=u.created_at.isoformat() if u.created_at else "",
        access_expires_at=_iso(u.access_expires_at),
        access_active=user_access_active(u),
        access_days_left=access_days_left(u),
        access_status=_access_status(u),
    )


def _apply_renew(user: User, req: RenewRequest, now: datetime) -> None:
    """Admin renew without invite code. permanent > expires_at > duration_days."""
    if req.permanent is True:
        user.access_expires_at = None
        return
    if req.expires_at:
        raw = (req.expires_at or "").strip()
        try:
            if raw.endswith("Z"):
                raw = raw[:-1] + "+00:00"
            dt = datetime.fromisoformat(raw)
        except ValueError:
            raise HTTPException(400, "expires_at 格式无效")
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        user.access_expires_at = dt
        return
    if req.duration_days is not None:
        days = int(req.duration_days)
        if days <= 0:
            user.access_expires_at = None
            return
        cur = _aware(user.access_expires_at)
        base = now
        if cur is not None and cur > now:
            base = cur
        user.access_expires_at = base + timedelta(days=days)
        return
    raise HTTPException(400, "请提供 duration_days、expires_at 或 permanent")


@router.put("/me/password")
async def change_my_password(
    req: ChangePasswordRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if not verify_password(req.old_password, user.hashed_password):
        raise HTTPException(400, "原密码错误")
    user.hashed_password = get_password_hash(req.new_password)
    db.commit()
    return {"message": "密码已修改"}


@router.get("/", response_model=List[UserResponse])
async def list_users(
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    result = db.execute(select(User).order_by(User.id))
    return [_to_resp(u) for u in result.scalars()]


@router.post("/", response_model=UserResponse)
async def create_user(
    req: CreateUserRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    exists = db.execute(select(User).where(User.username == req.username))
    if exists.scalar_one_or_none():
        raise HTTPException(400, "用户名已存在")
    exists = db.execute(select(User).where(User.email == req.email))
    if exists.scalar_one_or_none():
        raise HTTPException(400, "邮箱已被注册")

    user = User(
        username=req.username,
        email=req.email,
        hashed_password=get_password_hash(req.password),
        is_admin=req.is_admin,
        access_expires_at=None,
    )
    db.add(user)
    db.flush()
    if not user.is_admin:
        grant_all_libraries(db, user.id)
    db.commit()
    db.refresh(user)
    return _to_resp(user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    req: UpdateUserRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    result = db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "用户不存在")

    if req.username is not None:
        dup = db.execute(select(User).where(User.username == req.username, User.id != user_id))
        if dup.scalar_one_or_none():
            raise HTTPException(400, "用户名已存在")
        user.username = req.username
    if req.email is not None:
        dup = db.execute(select(User).where(User.email == req.email, User.id != user_id))
        if dup.scalar_one_or_none():
            raise HTTPException(400, "邮箱已被注册")
        user.email = req.email
    if req.password is not None:
        user.hashed_password = get_password_hash(req.password)
    if req.is_admin is not None:
        user.is_admin = req.is_admin

    db.commit()
    db.refresh(user)
    return _to_resp(user)


@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin)
):
    if user_id == admin.id:
        raise HTTPException(400, "不能删除自己")
    result = db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "用户不存在")
    db.delete(user)
    db.commit()
    return {"message": "已删除"}


@admin_router.post("/{user_id}/renew", response_model=UserResponse)
async def renew_user(
    user_id: int,
    req: RenewRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    """Admin renew/extend membership without consuming an invite code."""
    result = db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "用户不存在")

    # Admins: allow set permanent / explicit expiry; duration no-op if already admin permanent
    if user.is_admin and req.permanent is not True and req.expires_at is None and req.duration_days is None:
        return _to_resp(user)
    if user.is_admin and req.duration_days is not None and req.permanent is not True and not req.expires_at:
        # Don't lock admins via duration; treat as set permanent (no-op on access gate)
        user.access_expires_at = None
        db.commit()
        db.refresh(user)
        return _to_resp(user)

    now = datetime.now(timezone.utc)
    _apply_renew(user, req, now)
    db.commit()
    db.refresh(user)
    return _to_resp(user)


@admin_router.get("/{user_id}/libraries", response_model=LibrariesResponse)
async def get_user_libraries(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    result = db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "用户不存在")
    if user.is_admin:
        all_ids = list(db.execute(select(MediaLibrary.id).order_by(MediaLibrary.id)).scalars().all())
        return LibrariesResponse(user_id=user_id, library_ids=all_ids, all_libraries=True)
    ids = allowed_library_ids(db, user)
    return LibrariesResponse(user_id=user_id, library_ids=sorted(ids or []), all_libraries=False)


@admin_router.put("/{user_id}/libraries", response_model=LibrariesResponse)
async def put_user_libraries(
    user_id: int,
    req: LibrariesPutRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    result = db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "用户不存在")
    if user.is_admin:
        all_ids = list(db.execute(select(MediaLibrary.id).order_by(MediaLibrary.id)).scalars().all())
        return LibrariesResponse(user_id=user_id, library_ids=all_ids, all_libraries=True)

    wanted = list({int(x) for x in (req.library_ids or [])})
    if wanted:
        valid = set(db.execute(select(MediaLibrary.id).where(MediaLibrary.id.in_(wanted))).scalars().all())
        missing = [i for i in wanted if i not in valid]
        if missing:
            raise HTTPException(400, f"媒体库不存在: {missing}")
        wanted = sorted(valid)
    grant_libraries(db, user_id, wanted)
    db.commit()
    return LibrariesResponse(user_id=user_id, library_ids=wanted, all_libraries=False)
