"""Background reconciliation for USDT payment orders.

Why: a buyer may close the pay page right after sending the transfer —
the frontend then stops polling and a paid order would never be noticed,
leaving a paying customer without access. This task re-checks every
recent pending order once a minute so access is granted even when
nobody is watching the pay page.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from sqlalchemy import select

from ..core.database import SessionLocal
from ..models.payment_order import PaymentOrder
from ..api.payments import _refresh_from_remote, _aware, _utcnow

log = logging.getLogger("payment_recon")

# Vultr-side order TTL is 30 min; keep checking a bit beyond that so the
# "expired" verdict propagates even if the buyer never reopens the page.
_RECON_WINDOW = timedelta(minutes=45)
_INTERVAL_SECONDS = 60

_task: asyncio.Task | None = None


async def _reconcile_once() -> int:
    """One reconciliation pass. Returns the number of rows checked."""
    checked = 0
    with SessionLocal() as db:
        rows = db.execute(
            select(PaymentOrder).where(PaymentOrder.status == "pending").limit(100)
        ).scalars().all()
        cutoff = _utcnow() - _RECON_WINDOW
        for row in rows:
            created = _aware(row.created_at) or _utcnow()
            if created < cutoff:
                continue  # too old; Vultr has expired it, next pass skips fewer rows
            await _refresh_from_remote(db, row)
            checked += 1
    if checked:
        log.info("reconciled %d pending order(s)", checked)
    return checked


async def _loop() -> None:
    while True:
        try:
            await _reconcile_once()
        except Exception:
            log.exception("reconciliation pass failed")
        await asyncio.sleep(_INTERVAL_SECONDS)


def start_payment_recon() -> None:
    global _task
    if _task is None or _task.done():
        _task = asyncio.get_running_loop().create_task(_loop())
        log.info("payment reconciliation started (every %ss)", _INTERVAL_SECONDS)


def stop_payment_recon() -> None:
    global _task
    if _task is not None and not _task.done():
        _task.cancel()
    _task = None
