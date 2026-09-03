from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import BaseModel
from typing import Optional, List
from ..core.database import get_db
from ..core.security import get_password_hash, verify_password
from ..models.user import User
from .deps import get_current_user, get_current_admin

router = APIRouter(prefix="/api/users", tags=["users"])

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    is_admin: bool
    avatar: str
    created_at: str
    
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

def _to_resp(u: User) -> UserResponse:
    return UserResponse(
        id=u.id, username=u.username, email=u.email,
        is_admin=u.is_admin, avatar=u.avatar or "",
        created_at=u.created_at.isoformat() if u.created_at else ""
    )

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
    # Check duplicate
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
        is_admin=req.is_admin
    )
    db.add(user)
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
