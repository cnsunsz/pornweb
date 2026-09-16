from datetime import datetime, timezone
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import select
from ..core.database import get_db
from ..core.security import decode_token
from ..models.user import User

security = HTTPBearer(auto_error=False)

# Stable Chinese detail for Android / web to map to renew banner
ACCESS_EXPIRED_DETAIL = "授权已过期，请使用新的授权码续期"


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def user_access_active(user: User) -> bool:
    """Admins and null access_expires_at (permanent) are always active."""
    if getattr(user, "is_admin", False):
        return True
    exp = _aware(getattr(user, "access_expires_at", None))
    if exp is None:
        return True
    return exp >= datetime.now(timezone.utc)


def access_days_left(user: User) -> int | None:
    """Whole days remaining; None = permanent or admin; 0 if expired."""
    if getattr(user, "is_admin", False):
        return None
    exp = _aware(getattr(user, "access_expires_at", None))
    if exp is None:
        return None
    delta = exp - datetime.now(timezone.utc)
    secs = delta.total_seconds()
    if secs <= 0:
        return 0
    return max(1, int(secs // 86400)) if secs < 86400 else int(secs // 86400)


def assert_media_access(user: User) -> None:
    if not user_access_active(user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=ACCESS_EXPIRED_DETAIL)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录")
    token = credentials.credentials
    payload = decode_token(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已过期，请重新登录")
    
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="无效的认证凭据")
    
    result = db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    return user


async def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return user


async def require_media_access(user: User = Depends(get_current_user)) -> User:
    """Logged-in user with active membership (admins always pass)."""
    assert_media_access(user)
    return user
