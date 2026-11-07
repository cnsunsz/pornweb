from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime, timezone
from ..core.database import Base

class PaymentOrder(Base):
    """Renewal payment order (USDT via external usdt-pay, or PayPal Orders v2)."""
    __tablename__ = "payment_orders"

    id = Column(Integer, primary_key=True, index=True)
    # Local order id: USDT uses remote ORD-…; PayPal uses PP-…
    order_id = Column(String(64), unique=True, index=True, nullable=False)
    user_id = Column(Integer, nullable=False, index=True)
    amount_usd = Column(Float, nullable=False)
    days = Column(Integer, nullable=False)
    # pending | paid | expired
    status = Column(String(20), default="pending")
    tx_id = Column(String(128), default="")
    # usdt | paypal  (default usdt for rows created before this column existed)
    method = Column(String(16), default="usdt", nullable=False)
    # PayPal order id (or other provider reference); empty for USDT
    provider_order_id = Column(String(64), default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    paid_at = Column(DateTime, nullable=True)
