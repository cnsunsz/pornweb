"""USDT renewal payments, backed by the external usdt-pay service.

Flow:
  1. POST /api/payments/order {plan_id}
       -> backend creates an order on the usdt-pay server (server-to-server,
          no CORS issues), stores it locally and returns the hosted pay URL.
  2. Buyer opens the pay URL and sends USDT (TRC20).
  3. GET /api/payments/order/{order_id} (frontend polls)
       -> backend asks the usdt-pay server whether the order is paid;
          on first "paid" it extends the buyer's access_expires_at and
          marks the local order as paid (grant happens exactly once).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.database import get_db
from ..models.payment_order import PaymentOrder
from ..models.user import User
from .deps import get_current_user

router = APIRouter(prefix="/api/payments", tags=["payments"])

# Membership plans: price in USD, paid 1:1 in USDT.
# INTRO PRICING: 30-day plan is $4.9 during the early launch period.
# When the promo ends, change 4.9 back to 9.9 below — nothing else needed.
PLANS: List[dict] = [
    {"id": "p30", "days": 30, "amount": 4.9},   # 前期促销价；后期恢复 9.9
    {"id": "p90", "days": 90, "amount": 19.9},
    {"id": "p365", "days": 365, "amount": 49.9},
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    """SQLite returns naive datetimes (stored as UTC)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class CreateOrderRequest(BaseModel):
    plan_id: str


class OrderStatusResponse(BaseModel):
    order_id: str
    status: str
    days: int
    amount: float
    tx_id: str = ""


@router.get("/plans")
async def list_plans(user: User = Depends(get_current_user)):
    return {"plans": PLANS, "currency": "USDT"}


def _grant_access(db: Session, order: PaymentOrder, tx_id: str) -> None:
    """Extend the buyer's access window; idempotent (status flips to paid once)."""
    if order.status == "paid":
        return
    buyer = db.get(User, order.user_id)
    if not buyer:
        order.status = "expired"
        db.commit()
        return
    now = _utcnow()
    base = _aware(buyer.access_expires_at)
    new_exp = (base + timedelta(days=order.days)) if (base and base > now) else (now + timedelta(days=order.days))
    # store naive UTC, consistent with the rest of the app
    buyer.access_expires_at = new_exp.replace(tzinfo=None)
    order.status = "paid"
    order.paid_at = now
    order.tx_id = (tx_id or "")[:128]
    db.commit()


@router.post("/order")
async def create_order(
    req: CreateOrderRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    plan = next((p for p in PLANS if p["id"] == req.plan_id), None)
    if not plan:
        raise HTTPException(404, "套餐不存在")
    base = settings.USDT_PAY_SERVER.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"{base}/api/order/create",
                data={"amount": plan["amount"]},
                follow_redirects=False,
            )
    except httpx.HTTPError:
        raise HTTPException(502, "收款服务暂时不可用，请稍后再试")
    if r.status_code not in (302, 303, 307, 308):
        raise HTTPException(502, "收款服务返回异常，请稍后再试")
    pay_path = r.headers.get("location", "")
    order_id = pay_path.rstrip("/").split("/")[-1]
    if not order_id.startswith("ORD-"):
        raise HTTPException(502, "订单创建失败，请稍后再试")
    row = PaymentOrder(
        order_id=order_id,
        user_id=user.id,
        amount_usd=float(plan["amount"]),
        days=int(plan["days"]),
        status="pending",
        created_at=_utcnow(),
    )
    db.add(row)
    db.commit()
    return {
        "order_id": order_id,
        "pay_url": f"{base}{pay_path}",
        "days": plan["days"],
        "amount": plan["amount"],
    }


async def _refresh_from_remote(db: Session, row: PaymentOrder) -> None:
    """Poll the usdt-pay server once for a pending order; grant access or
    mark it expired. Shared by the polling endpoint and the background
    reconciliation task. Safe to call repeatedly (idempotent)."""
    if row.status != "pending":
        return
    base = settings.USDT_PAY_SERVER.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(f"{base}/api/order/{row.order_id}")
            remote = r.json()
        if remote.get("status") == "paid":
            _grant_access(db, row, remote.get("txId") or "")
        elif remote.get("status") == "expired":
            row.status = "expired"
            db.commit()
    except Exception:
        # network hiccup: keep pending, next poll retries
        pass


@router.get("/order/{order_id}", response_model=OrderStatusResponse)
async def get_order_status(
    order_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = db.execute(
        select(PaymentOrder).where(
            PaymentOrder.order_id == order_id,
            PaymentOrder.user_id == user.id,
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "订单不存在")
    await _refresh_from_remote(db, row)
    db.refresh(row)
    return OrderStatusResponse(
        order_id=row.order_id,
        status=row.status,
        days=row.days,
        amount=row.amount_usd,
        tx_id=row.tx_id or "",
    )


@router.get("/my")
async def my_orders(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = db.execute(
        select(PaymentOrder)
        .where(PaymentOrder.user_id == user.id)
        .order_by(PaymentOrder.id.desc())
        .limit(50)
    ).scalars().all()
    return {
        "items": [
            {
                "order_id": r.order_id,
                "status": r.status,
                "days": r.days,
                "amount": r.amount_usd,
                "tx_id": r.tx_id or "",
                "created_at": r.created_at.isoformat() if r.created_at else "",
                "paid_at": r.paid_at.isoformat() if r.paid_at else None,
            }
            for r in rows
        ]
    }
