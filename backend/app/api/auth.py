from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from ..core.database import get_db
from ..core.security import verify_password, get_password_hash, create_access_token
from ..models.user import User
from .deps import get_current_user

router = APIRouter(prefix="/api/auth", tags=["auth"])

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str

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
    
    from sqlalchemy import func as sqlfunc
    count_result = db.execute(select(sqlfunc.count(User.id)))
    is_first = (count_result.scalar() or 0) == 0
    
    user = User(
        username=username,
        email=email,
        hashed_password=get_password_hash(req.password),
        is_admin=is_first
    )
    db.add(user)
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
