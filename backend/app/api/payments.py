"""Renewal payments: USDT (external usdt-pay) and PayPal Orders API v2.

Flow (USDT, default):
  1. POST /api/payments/order {plan_id, method?}  method defaults to usdt
       -> creates remote order, stores locally, returns pay_url
  2. GET /api/payments/order/{order_id} polls remote; on paid -> _grant_access

Flow (PayPal):
  1. POST /api/payments/order {plan_id, method:"paypal"}
       -> creates PayPal CAPTURE order, stores PP-… locally + provider_order_id
  2. Buyer approves on PayPal; return URL hits /renew?paypal=return&order_id=…
  3. GET poll or POST /api/payments/paypal/capture triggers server-side Capture
       then _grant_access (idempotent)
  4. Optional webhook PAYMENT.CAPTURE.COMPLETED when PAYPAL_WEBHOOK_ID is set
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.config import settings
from ..core.database import get_db
from ..models.payment_order import PaymentOrder
from ..models.user import User
from ..services import paypal as paypal_svc
from .deps import get_current_user

router = APIRouter(prefix="/api/payments", tags=["payments"])

# Membership plans: price in USD (USDT 1:1, PayPal USD).
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


def _public_base() -> str:
    return (settings.PUBLIC_BASE_URL or "https://web.cnsz.kdns.fr").rstrip("/")


class CreateOrderRequest(BaseModel):
    plan_id: str
    method: str = Field(default="usdt", description="usdt | paypal")


class OrderStatusResponse(BaseModel):
    order_id: str
    status: str
    days: int
    amount: float
    tx_id: str = ""
    method: str = "usdt"


class CaptureRequest(BaseModel):
    order_id: str


def _usdt_enabled() -> bool:
    """Admin toggle USDT_PAY_ENABLED; default True when unset."""
    return bool(getattr(settings, "USDT_PAY_ENABLED", True))


@router.get("/plans")
async def list_plans(user: User = Depends(get_current_user)):
    methods = []
    if _usdt_enabled():
        methods.append("usdt")
    if paypal_svc.paypal_configured():
        methods.append("paypal")
    return {
        "plans": PLANS,
        "currency": "USD",  # both methods settle in USD terms; USDT is 1:1
        "methods": methods,
    }


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


def _new_paypal_local_id() -> str:
    return "PP-" + secrets.token_hex(8).upper()


@router.post("/order")
async def create_order(
    req: CreateOrderRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    plan = next((p for p in PLANS if p["id"] == req.plan_id), None)
    if not plan:
        raise HTTPException(404, "套餐不存在")
    method = (req.method or "usdt").strip().lower()
    if method not in ("usdt", "paypal"):
        raise HTTPException(400, "不支持的支付方式")

    if method == "paypal":
        return await _create_paypal_order(db, user, plan)

    if not _usdt_enabled():
        raise HTTPException(503, "USDT 收款已关闭")
    return await _create_usdt_order(db, user, plan)


async def _create_usdt_order(db: Session, user: User, plan: dict) -> dict:
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
        method="usdt",
        provider_order_id="",
        created_at=_utcnow(),
    )
    db.add(row)
    db.commit()
    return {
        "order_id": order_id,
        "pay_url": f"{base}{pay_path}",
        "days": plan["days"],
        "amount": plan["amount"],
        "method": "usdt",
    }


async def _create_paypal_order(db: Session, user: User, plan: dict) -> dict:
    if not paypal_svc.paypal_configured():
        raise HTTPException(503, "PayPal 未配置")
    local_id = _new_paypal_local_id()
    # Ensure uniqueness on rare collision
    for _ in range(3):
        exists = db.execute(
            select(PaymentOrder.id).where(PaymentOrder.order_id == local_id)
        ).scalar_one_or_none()
        if not exists:
            break
        local_id = _new_paypal_local_id()
    pub = _public_base()
    return_url = f"{pub}/renew?paypal=return&order_id={local_id}"
    cancel_url = f"{pub}/renew?paypal=cancel&order_id={local_id}"
    try:
        paypal_id, approve_url = await paypal_svc.create_checkout_order(
            amount_usd=float(plan["amount"]),
            local_order_id=local_id,
            return_url=return_url,
            cancel_url=cancel_url,
            description=f"{settings.APP_NAME} {plan['days']}d",
        )
    except RuntimeError as e:
        raise HTTPException(502, str(e) or "PayPal 下单失败")
    except httpx.HTTPError:
        raise HTTPException(502, "PayPal 暂时不可用，请稍后再试")
    row = PaymentOrder(
        order_id=local_id,
        user_id=user.id,
        amount_usd=float(plan["amount"]),
        days=int(plan["days"]),
        status="pending",
        method="paypal",
        provider_order_id=paypal_id,
        created_at=_utcnow(),
    )
    db.add(row)
    db.commit()
    return {
        "order_id": local_id,
        "pay_url": approve_url,
        "days": plan["days"],
        "amount": plan["amount"],
        "method": "paypal",
    }


async def _refresh_usdt(db: Session, row: PaymentOrder) -> None:
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


async def _refresh_paypal(db: Session, row: PaymentOrder) -> None:
    """If PayPal order is APPROVED, capture; if COMPLETED, grant. Idempotent."""
    if not row.provider_order_id or not paypal_svc.paypal_configured():
        return
    try:
        data = await paypal_svc.get_order(row.provider_order_id)
    except Exception:
        return
    status = (data.get("status") or "").upper()
    if status == "APPROVED":
        try:
            data = await paypal_svc.capture_order(row.provider_order_id)
            status = (data.get("status") or "").upper()
        except Exception:
            return
    if status == "COMPLETED":
        _grant_access(db, row, paypal_svc.extract_capture_id(data))
    elif status in ("VOIDED", "EXPIRED"):
        row.status = "expired"
        db.commit()


async def _refresh_from_remote(db: Session, row: PaymentOrder) -> None:
    """Poll provider for a pending order; grant or expire. Idempotent."""
    if row.status != "pending":
        return
    method = (row.method or "usdt").lower()
    if method == "paypal":
        await _refresh_paypal(db, row)
    else:
        await _refresh_usdt(db, row)


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
        method=row.method or "usdt",
    )


@router.post("/paypal/capture")
async def paypal_capture(
    req: CaptureRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Frontend return-URL hook: actively capture a pending PayPal order."""
    if not paypal_svc.paypal_configured():
        raise HTTPException(503, "PayPal 未配置")
    row = db.execute(
        select(PaymentOrder).where(
            PaymentOrder.order_id == req.order_id,
            PaymentOrder.user_id == user.id,
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "订单不存在")
    if (row.method or "") != "paypal":
        raise HTTPException(400, "非 PayPal 订单")
    if row.status == "paid":
        return {"order_id": row.order_id, "status": "paid", "days": row.days, "amount": row.amount_usd}
    await _refresh_paypal(db, row)
    db.refresh(row)
    return {
        "order_id": row.order_id,
        "status": row.status,
        "days": row.days,
        "amount": row.amount_usd,
        "tx_id": row.tx_id or "",
        "method": "paypal",
    }


@router.post("/paypal/webhook")
async def paypal_webhook(request: Request, db: Session = Depends(get_db)):
    """Optional: handle PAYMENT.CAPTURE.COMPLETED when PAYPAL_WEBHOOK_ID is set."""
    if not settings.PAYPAL_WEBHOOK_ID:
        # Not configured — accept but no-op so PayPal retries don't spam logs
        return {"ok": True, "ignored": True}
    raw = await request.json()
    headers = request.headers
    ok = await paypal_svc.verify_webhook_signature(
        transmission_id=headers.get("paypal-transmission-id", ""),
        timestamp=headers.get("paypal-transmission-time", ""),
        transmission_sig=headers.get("paypal-transmission-sig", ""),
        cert_url=headers.get("paypal-cert-url", ""),
        auth_algo=headers.get("paypal-auth-algo", ""),
        webhook_event=raw,
    )
    if not ok:
        raise HTTPException(400, "webhook 校验失败")
    event_type = (raw.get("event_type") or "").upper()
    resource = raw.get("resource") or {}
    if event_type == "PAYMENT.CAPTURE.COMPLETED":
        # Prefer custom_id / supplementary_data → related order id
        local_id = ""
        supplementary = resource.get("supplementary_data") or {}
        related = supplementary.get("related_ids") or {}
        paypal_order_id = related.get("order_id") or ""
        custom_id = resource.get("custom_id") or ""
        capture_id = resource.get("id") or ""
        row = None
        if custom_id:
            row = db.execute(
                select(PaymentOrder).where(PaymentOrder.order_id == custom_id)
            ).scalar_one_or_none()
        if row is None and paypal_order_id:
            row = db.execute(
                select(PaymentOrder).where(PaymentOrder.provider_order_id == paypal_order_id)
            ).scalar_one_or_none()
        if row and row.status == "pending":
            _grant_access(db, row, capture_id or paypal_order_id)
    elif event_type == "CHECKOUT.ORDER.APPROVED":
        paypal_order_id = resource.get("id") or ""
        if paypal_order_id:
            row = db.execute(
                select(PaymentOrder).where(PaymentOrder.provider_order_id == paypal_order_id)
            ).scalar_one_or_none()
            if row and row.status == "pending":
                await _refresh_paypal(db, row)
    return {"ok": True}


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
                "method": r.method or "usdt",
                "created_at": r.created_at.isoformat() if r.created_at else "",
                "paid_at": r.paid_at.isoformat() if r.paid_at else None,
            }
            for r in rows
        ]
    }
