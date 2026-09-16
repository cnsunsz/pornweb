from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from datetime import datetime, timezone
from ..core.database import Base


class InviteCode(Base):
    __tablename__ = "invite_codes"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(64), unique=True, index=True, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    used_by = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    used_at = Column(DateTime, nullable=True)
    note = Column(String(200), default="")
    batch_id = Column(String(36), default="", index=True)
    expires_at = Column(DateTime, nullable=True)  # unused-code shelf life
    revoked = Column(Boolean, default=False, nullable=False)
    # membership length granted on redeem; null = permanent access
    duration_days = Column(Integer, nullable=True)
