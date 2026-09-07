"""Cache of actor profile photos (online only; never invent placeholders)."""
from sqlalchemy import Column, Integer, String, DateTime, Text
from datetime import datetime
from ..core.database import Base


class ActorPhoto(Base):
    __tablename__ = "actor_photos"

    id = Column(Integer, primary_key=True, index=True)
    # normalized lower-case name key for lookup
    name_key = Column(String(300), unique=True, index=True, nullable=False)
    # display name as first seen
    name = Column(String(300), nullable=False, default="")
    # ok | miss
    status = Column(String(16), nullable=False, default="miss")
    # remote image URL when status=ok (TMDB/Douban CDN)
    remote_url = Column(String(1000), default="")
    source = Column(String(32), default="")  # tmdb / douban
    external_id = Column(String(64), default="")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    note = Column(Text, default="")
