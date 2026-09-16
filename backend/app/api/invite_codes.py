"""Admin invite / activation codes for registration and renew."""
from __future__ import annotations

import secrets
import string
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..models.invite_code import InviteCode
from ..models.user import User
from .deps import get_current_admin

router = APIRouter(prefix="/api/admin/invite-codes", tags=["invite-codes"])

_ALPHABET = string.ascii_uppercase + string.digits


def _gen_code() -> str:
    """Format: XXXX-XXXX-XXXX (readable, URL-safe-ish)."""
    raw = "".join(secrets.choice(_ALPHABET) for _ in range(12))
    return f"{raw[0:4]}-{raw[4:8]}-{raw[8:12]}"


class GenerateRequest(BaseModel):
    count: int = Field(1, ge=1, le=100)
    note: Optional[str] = Field(None, max_length=200)
    expires_days: Optional[int] = Field(None, ge=1, le=3650)  # unused-code shelf life
    # membership days when redeemed; null/omit = permanent; prefer positive int
    duration_days: Optional[int] = Field(None, ge=1, le=36500)


class InviteCodeResponse(BaseModel):
    id: int
    code: str
    created_by: Optional[int] = None
    created_at: str
    used_by: Optional[int] = None
    used_at: Optional[str] = None
    note: str = ""
    batch_id: str = ""
    expires_at: Optional[str] = None
    revoked: bool = False
    duration_days: Optional[int] = None
    status: str  # unused | used | revoked | expired

    class Config:
        from_attributes = True


class ListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[InviteCodeResponse]


def _status(row: InviteCode, now: datetime) -> str:
    if row.revoked:
        return "revoked"
    if row.used_by is not None:
        return "used"
    if row.expires_at is not None:
        exp = row.expires_at
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        if exp < now:
            return "expired"
    return "unused"


def _iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _to_resp(row: InviteCode, now: Optional[datetime] = None) -> InviteCodeResponse:
    now = now or datetime.now(timezone.utc)
    return InviteCodeResponse(
        id=row.id,
        code=row.code,
        created_by=row.created_by,
        created_at=_iso(row.created_at) or "",
        used_by=row.used_by,
        used_at=_iso(row.used_at),
        note=row.note or "",
        batch_id=row.batch_id or "",
        expires_at=_iso(row.expires_at),
        revoked=bool(row.revoked),
        duration_days=row.duration_days,
        status=_status(row, now),
    )


@router.post("", response_model=List[InviteCodeResponse])
async def generate_invite_codes(
    req: GenerateRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    now = datetime.now(timezone.utc)
    expires_at = None
    if req.expires_days:
        expires_at = now + timedelta(days=req.expires_days)
    duration_days = req.duration_days  # None = permanent membership
    batch_id = str(uuid.uuid4())
    note = (req.note or "").strip()
    created: List[InviteCode] = []
    for _ in range(req.count):
        code = None
        for _attempt in range(8):
            candidate = _gen_code()
            exists = db.execute(
                select(InviteCode.id).where(InviteCode.code == candidate)
            ).scalar_one_or_none()
            if not exists:
                code = candidate
                break
        if not code:
            raise HTTPException(500, "生成授权码失败，请重试")
        row = InviteCode(
            code=code,
            created_by=admin.id,
            created_at=now,
            note=note,
            batch_id=batch_id,
            expires_at=expires_at,
            revoked=False,
            duration_days=duration_days,
        )
        db.add(row)
        created.append(row)
    db.commit()
    for row in created:
        db.refresh(row)
    return [_to_resp(r, now) for r in created]


@router.get("", response_model=ListResponse)
async def list_invite_codes(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str = Query("all"),
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    now = datetime.now(timezone.utc)
    status = (status or "all").strip().lower()
    if status not in ("unused", "used", "all", "revoked", "expired"):
        raise HTTPException(400, "status 须为 unused|used|revoked|expired|all")
    q = select(InviteCode)
    count_q = select(func.count(InviteCode.id))

    if status == "unused":
        cond = and_(
            InviteCode.used_by.is_(None),
            InviteCode.revoked.is_(False),
            or_(InviteCode.expires_at.is_(None), InviteCode.expires_at >= now),
        )
        q = q.where(cond)
        count_q = count_q.where(cond)
    elif status == "used":
        q = q.where(InviteCode.used_by.is_not(None))
        count_q = count_q.where(InviteCode.used_by.is_not(None))
    elif status == "revoked":
        q = q.where(InviteCode.revoked.is_(True))
        count_q = count_q.where(InviteCode.revoked.is_(True))
    elif status == "expired":
        cond = and_(
            InviteCode.used_by.is_(None),
            InviteCode.revoked.is_(False),
            InviteCode.expires_at.is_not(None),
            InviteCode.expires_at < now,
        )
        q = q.where(cond)
        count_q = count_q.where(cond)

    total = db.execute(count_q).scalar() or 0
    rows = db.execute(
        q.order_by(InviteCode.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).scalars().all()
    return ListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[_to_resp(r, now) for r in rows],
    )


@router.post("/{code_id}/revoke", response_model=InviteCodeResponse)
async def revoke_invite_code(
    code_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
):
    row = db.execute(select(InviteCode).where(InviteCode.id == code_id)).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "授权码不存在")
    if row.used_by is not None:
        raise HTTPException(400, "已使用的授权码无法撤销")
    if row.revoked:
        return _to_resp(row)
    row.revoked = True
    db.commit()
    db.refresh(row)
    return _to_resp(row)
