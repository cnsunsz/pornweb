from sqlalchemy import Column, Integer, Float, DateTime, ForeignKey, UniqueConstraint
from datetime import datetime, timezone
from ..core.database import Base


class PlaybackProgress(Base):
    __tablename__ = "playback_progress"
    __table_args__ = (UniqueConstraint("user_id", "media_id", name="uq_progress_user_media"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    media_id = Column(Integer, ForeignKey("media_items.id", ondelete="CASCADE"), nullable=False, index=True)
    position = Column(Float, default=0)
    duration = Column(Float, default=0)
    part = Column(Integer, default=0)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))
