from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime, timezone
from ..core.database import Base

class PaymentOrder(Base):
    """USDT renewal order, mirrors an order on the external usdt-pay service."""
    __tablename__ = "payment_orders"

    id = Column(Integer, primary_key=True, index=True)
    # order id on the usdt-pay service, e.g. ORD-XXXXXXXXXX
    order_id = Column(String(64), unique=True, index=True, nullable=False)
    user_id = Column(Integer, nullable=False, index=True)
    amount_usd = Column(Float, nullable=False)
    days = Column(Integer, nullable=False)
    # pending | paid | expired
    status = Column(String(20), default="pending")
    tx_id = Column(String(128), default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    paid_at = Column(DateTime, nullable=True)
