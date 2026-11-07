"""PayPal Orders API v2 helpers (sandbox / live via PAYPAL_MODE).

Credentials come from env (PAYPAL_CLIENT_ID / PAYPAL_CLIENT_SECRET). When
either is missing, callers should treat PayPal as unavailable — never hardcode
secrets here.
"""
from __future__ import annotations

import logging
from typing import Tuple

import httpx

from ..core.config import settings

log = logging.getLogger("paypal")


def paypal_configured() -> bool:
    return bool(settings.PAYPAL_CLIENT_ID and settings.PAYPAL_CLIENT_SECRET)


def _api_base() -> str:
    mode = (settings.PAYPAL_MODE or "sandbox").strip().lower()
    if mode == "live":
        return "https://api-m.paypal.com"
    return "https://api-m.sandbox.paypal.com"


async def _access_token(client: httpx.AsyncClient) -> str:
    r = await client.post(
        f"{_api_base()}/v1/oauth2/token",
        data={"grant_type": "client_credentials"},
        auth=(settings.PAYPAL_CLIENT_ID, settings.PAYPAL_CLIENT_SECRET),
        headers={"Accept": "application/json", "Accept-Language": "en_US"},
    )
    if r.status_code != 200:
        log.warning("paypal oauth failed: %s %s", r.status_code, r.text[:200])
        raise RuntimeError("PayPal 鉴权失败")
    return r.json()["access_token"]


def _auth_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


async def create_checkout_order(
    *,
    amount_usd: float,
    local_order_id: str,
    return_url: str,
    cancel_url: str,
    description: str = "MediaVault membership",
) -> Tuple[str, str]:
    """Create a PayPal order (intent=CAPTURE). Returns (paypal_order_id, approve_url)."""
    async with httpx.AsyncClient(timeout=20) as client:
        token = await _access_token(client)
        body = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "reference_id": local_order_id,
                    "description": description[:127],
                    "custom_id": local_order_id,
                    "amount": {
                        "currency_code": "USD",
                        "value": f"{amount_usd:.2f}",
                    },
                }
            ],
            "application_context": {
                "brand_name": settings.APP_NAME or "MediaVault",
                "landing_page": "NO_PREFERENCE",
                "user_action": "PAY_NOW",
                "return_url": return_url,
                "cancel_url": cancel_url,
            },
        }
        r = await client.post(
            f"{_api_base()}/v2/checkout/orders",
            json=body,
            headers=_auth_headers(token),
        )
        if r.status_code not in (200, 201):
            log.warning("paypal create order failed: %s %s", r.status_code, r.text[:300])
            raise RuntimeError("PayPal 下单失败")
        data = r.json()
        paypal_id = data.get("id") or ""
        approve = ""
        for link in data.get("links") or []:
            if link.get("rel") == "approve":
                approve = link.get("href") or ""
                break
        if not paypal_id or not approve:
            raise RuntimeError("PayPal 返回异常")
        return paypal_id, approve


async def get_order(paypal_order_id: str) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        token = await _access_token(client)
        r = await client.get(
            f"{_api_base()}/v2/checkout/orders/{paypal_order_id}",
            headers=_auth_headers(token),
        )
        if r.status_code != 200:
            log.warning("paypal get order failed: %s %s", r.status_code, r.text[:200])
            raise RuntimeError("PayPal 查询失败")
        return r.json()


async def capture_order(paypal_order_id: str) -> dict:
    """Server-side capture. Safe to retry when already captured (PayPal returns 422)."""
    async with httpx.AsyncClient(timeout=30) as client:
        token = await _access_token(client)
        r = await client.post(
            f"{_api_base()}/v2/checkout/orders/{paypal_order_id}/capture",
            headers=_auth_headers(token),
            json={},
        )
        if r.status_code in (200, 201):
            return r.json()
        # Already captured / unprocessable — re-fetch current state
        if r.status_code == 422:
            return await get_order(paypal_order_id)
        log.warning("paypal capture failed: %s %s", r.status_code, r.text[:300])
        raise RuntimeError("PayPal 收款失败")


def extract_capture_id(payload: dict) -> str:
    """Best-effort capture / transaction id from order or capture response."""
    try:
        units = payload.get("purchase_units") or []
        for u in units:
            payments = (u.get("payments") or {}).get("captures") or []
            for c in payments:
                cid = c.get("id")
                if cid:
                    return str(cid)
    except Exception:
        pass
    return str(payload.get("id") or "")


async def verify_webhook_signature(
    *,
    transmission_id: str,
    timestamp: str,
    transmission_sig: str,
    cert_url: str,
    auth_algo: str,
    webhook_event: dict,
) -> bool:
    """Verify PayPal webhook via API. Requires PAYPAL_WEBHOOK_ID."""
    wid = (settings.PAYPAL_WEBHOOK_ID or "").strip()
    if not wid:
        return False
    async with httpx.AsyncClient(timeout=20) as client:
        token = await _access_token(client)
        body = {
            "auth_algo": auth_algo,
            "cert_url": cert_url,
            "transmission_id": transmission_id,
            "transmission_sig": transmission_sig,
            "transmission_time": timestamp,
            "webhook_id": wid,
            "webhook_event": webhook_event,
        }
        r = await client.post(
            f"{_api_base()}/v1/notifications/verify-webhook-signature",
            json=body,
            headers=_auth_headers(token),
        )
        if r.status_code != 200:
            log.warning("paypal webhook verify http %s", r.status_code)
            return False
        return (r.json().get("verification_status") or "").upper() == "SUCCESS"
