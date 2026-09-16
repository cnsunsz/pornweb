from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select, func as sqlfunc
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Optional
from ..core.database import get_db
from ..core.security import verify_password, get_password_hash, create_access_token
from ..models.user import User
from ..models.invite_code import InviteCode
from .deps import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str
    invite_code: Optional[str] = None  # required unless first user (bootstrap)
    # alias accepted via model_validator / extra field name activation_code
    activation_code: Optional[str] = None

class LoginRequest(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_admin: bool
    avatar: str
    created_at: str
    
    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

def _normalize_code(req: RegisterRequest) -> str:
    raw = (req.invite_code or req.activation_code or "").strip().upper()
    # Keep hyphens if present; strip spaces
    raw = raw.replace(" ", "")
    return raw

def _code_lookup_variants(code: str):
    """Match stored XXXX-XXXX-XXXX even if client omits hyphens."""
    compact = code.replace("-", "")
    variants = {code, compact}
    if len(compact) == 12 and "-" not in code:
        variants.add(f"{compact[0:4]}-{compact[4:8]}-{compact[8:12]}")
    return list(variants)

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

    # Check username
    result = db.execute(select(User).where(User.username == username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已存在")
    
    # Check email
    result = db.execute(select(User).where(User.email == email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="邮箱已被注册")
    
    count_result = db.execute(select(sqlfunc.count(User.id)))
    is_first = (count_result.scalar() or 0) == 0

    invite_row = None
    now = datetime.now(timezone.utc)
    if not is_first:
        code_str = _normalize_code(req)
        if not code_str:
            raise HTTPException(status_code=400, detail="请输入授权码")
        # Atomic claim: lock unused row
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
    
    user = User(
        username=username,
        email=email,
        hashed_password=get_password_hash(req.password),
        is_admin=is_first
    )
    db.add(user)
    db.flush()  # get user.id before commit

    if invite_row is not None:
        invite_row.used_by = user.id
        invite_row.used_at = now

    db.commit()
    db.refresh(user)
    
    token = create_access_token({"sub": str(user.id)})
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user.id, username=user.username, email=user.email,
            is_admin=user.is_admin, avatar=user.avatar or "",
            created_at=user.created_at.isoformat() if user.created_at else ""
        )
    )

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
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user.id, username=user.username, email=user.email,
            is_admin=user.is_admin, avatar=user.avatar or "",
            created_at=user.created_at.isoformat() if user.created_at else ""
        )
    )

@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(get_current_user)):
    return UserResponse(
        id=user.id, username=user.username, email=user.email,
        is_admin=user.is_admin, avatar=user.avatar or "",
        created_at=user.created_at.isoformat() if user.created_at else ""
    )
