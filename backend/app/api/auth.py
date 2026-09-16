from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func as sqlfunc, update
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
from typing import Optional
from ..core.database import get_db
from ..core.security import verify_password, get_password_hash, create_access_token
from ..models.user import User
from ..models.invite_code import InviteCode
from ..models.progress import PlaybackProgress
from ..models.scan_job import ScanJob
from .deps import get_current_user, user_access_active, access_days_left

router = APIRouter(prefix="/api/auth", tags=["auth"])

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    invite_code: Optional[str] = None  # required unless first user (bootstrap)
    activation_code: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

class ActivateRequest(BaseModel):
    invite_code: Optional[str] = None
    activation_code: Optional[str] = None

class DeleteAccountRequest(BaseModel):
    password: str

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
    
    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class ActivateResponse(BaseModel):
    ok: bool = True
    message: str
    user: UserResponse

def _normalize_code_raw(invite_code: Optional[str], activation_code: Optional[str] = None) -> str:
    raw = (invite_code or activation_code or "").strip().upper()
    raw = raw.replace(" ", "")
    return raw

def _normalize_code(req: RegisterRequest) -> str:
    return _normalize_code_raw(req.invite_code, req.activation_code)

def _code_lookup_variants(code: str):
    """Match stored XXXX-XXXX-XXXX even if client omits hyphens."""
    compact = code.replace("-", "")
    variants = {code, compact}
    if len(compact) == 12 and "-" not in code:
        variants.add(f"{compact[0:4]}-{compact[4:8]}-{compact[8:12]}")
    return list(variants)

def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()

def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        is_admin=bool(user.is_admin),
        avatar=user.avatar or "",
        created_at=user.created_at.isoformat() if user.created_at else "",
        access_expires_at=_iso(user.access_expires_at),
        access_active=user_access_active(user),
        access_days_left=access_days_left(user),
    )

def _claim_invite(db: Session, code_str: str, now: datetime) -> InviteCode:
    if not code_str:
        raise HTTPException(status_code=400, detail="请输入授权码")
    invite_row = db.execute(
        select(InviteCode)
        .where(InviteCode.code.in_(_code_lookup_variants(code_str)))
        .with_for_update()
    ).scalar_one_or_none()
    if not invite_row:
        raise HTTPException(status_code=400, detail="授权码无效")
    if invite_row.revoked:
        raise HTTPException(status_code=400, detail="授权码已撤销")
    if invite_row.used_by is not None:
        raise HTTPException(status_code=400, detail="授权码已被使用")
    if invite_row.expires_at is not None:
        exp = invite_row.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < now:
            raise HTTPException(status_code=400, detail="授权码已过期")
    return invite_row

def _apply_duration(user: User, duration_days: Optional[int], now: datetime, *, extend: bool) -> None:
    """Set or extend access_expires_at from invite duration_days.
    null/<=0 duration => permanent (access_expires_at=None).
    extend: from max(now, current_expiry)+days; else set now+days (register).
    """
    if duration_days is None or int(duration_days) <= 0:
        user.access_expires_at = None
        return
    days = int(duration_days)
    if extend:
        cur = user.access_expires_at
        if cur is not None and cur.tzinfo is None:
            cur = cur.replace(tzinfo=timezone.utc)
        base = now
        if cur is not None and cur > now:
            base = cur
        user.access_expires_at = base + timedelta(days=days)
    else:
        user.access_expires_at = now + timedelta(days=days)

@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest, db: Session = Depends(get_db)):
    username = (req.username or "").strip()
    email = (req.email or "").strip()
    if len(username) < 2:
        raise HTTPException(status_code=400, detail="用户名至少2个字符")
    if len(req.password or "") < 6:
        raise HTTPException(status_code=400, detail="密码至少6位")
    if len(req.password.encode("utf-8")) > 72:
        raise HTTPException(status_code=400, detail="密码过长")

    result = db.execute(select(User).where(User.username == username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已存在")
    
    result = db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="邮箱已被注册")
    
    count_result = db.execute(select(sqlfunc.count(User.id)))
    is_first = (count_result.scalar() or 0) == 0

    invite_row = None
    now = datetime.now(timezone.utc)
    if not is_first:
        invite_row = _claim_invite(db, _normalize_code(req), now)
    
    user = User(
        username=username,
        email=email,
        hashed_password=get_password_hash(req.password),
        is_admin=is_first,
        access_expires_at=None,  # first user / permanent until duration applied
    )
    if invite_row is not None:
        _apply_duration(user, invite_row.duration_days, now, extend=False)

    db.add(user)
    db.flush()

    if invite_row is not None:
        invite_row.used_by = user.id
        invite_row.used_at = now

    db.commit()
    db.refresh(user)
    
    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(access_token=token, user=_user_response(user))

@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: Session = Depends(get_db)):
    username = (req.username or "").strip()
    result = db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=401, detail="账户不存在")
    
    if not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="密码错误")
    
    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(access_token=token, user=_user_response(user))

@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return _user_response(user)

@router.post("/activate", response_model=ActivateResponse)
async def activate(
    req: ActivateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Logged-in redeem / renew: consume unused invite code and extend membership."""
    now = datetime.now(timezone.utc)
    code_str = _normalize_code_raw(req.invite_code, req.activation_code)
    invite_row = _claim_invite(db, code_str, now)
    _apply_duration(user, invite_row.duration_days, now, extend=True)
    invite_row.used_by = user.id
    invite_row.used_at = now
    db.commit()
    db.refresh(user)
    return ActivateResponse(
        ok=True,
        message="授权已续期" if user.access_expires_at else "已激活永久授权",
        user=_user_response(user),
    )


@router.post("/delete-account")
async def delete_account(
    req: DeleteAccountRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Self-service account deletion for ordinary (non-admin) users.
    Hard-deletes the user row after clearing invite_code FKs and related rows.
    Client must clear token / logout on 200.
    """
    if user.is_admin:
        raise HTTPException(status_code=400, detail="管理员账户不可自行注销")
    if not (req.password or "").strip():
        raise HTTPException(status_code=400, detail="请输入当前密码以确认注销")
    if not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="密码错误")

    uid = user.id
    # Prefer safe FK handling even when SQLite foreign_keys pragma is off
    db.execute(
        update(InviteCode).where(InviteCode.used_by == uid).values(used_by=None)
    )
    db.execute(
        update(InviteCode).where(InviteCode.created_by == uid).values(created_by=None)
    )
    for row in db.execute(select(PlaybackProgress).where(PlaybackProgress.user_id == uid)).scalars().all():
        db.delete(row)
    for row in db.execute(select(ScanJob).where(ScanJob.user_id == uid)).scalars().all():
        db.delete(row)

    # Re-load user bound to this session for ORM cascade (media_items)
    u = db.execute(select(User).where(User.id == uid)).scalar_one()
    db.delete(u)
    db.commit()
    return {"ok": True, "message": "账户已注销"}


@router.delete("/me")
async def delete_me(
    req: DeleteAccountRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Alias of POST /api/auth/delete-account (same body {password})."""
    return await delete_account(req, db, user)
