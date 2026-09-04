from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from ..core.database import Base

class MediaItem(Base):
    __tablename__ = "media_items"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    file_path = Column(String(1000), nullable=False, index=True)
    filename = Column(String(500), nullable=False)
    file_type = Column(String(20), nullable=False)  # movie, tvshow, episode
    file_size = Column(Integer, default=0)
    
    # NFO metadata
    title = Column(String(200), default="")
    original_title = Column(String(200), default="")
    plot = Column(Text, default="")
    year = Column(Integer)
    genre = Column(String(200), default="")
    rating = Column(Float)
    director = Column(String(200), default="")
    cast_list = Column(Text, default="")  # JSON array
    poster_url = Column(String(1000), default="")
    fanart_url = Column(String(1000), default="")
    
    # Organization
    category = Column(String(50), default="movie")  # movie, tvshow
    folder = Column(String(1000), default="/")
    extra_files = Column(Text, default="[]")  # JSON [{label, path}]
    duration = Column(Float, default=0)
    # NFO file mtime when last parsed — skip re-read on rclone if unchanged
    nfo_mtime = Column(Float, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    owner = relationship("User", back_populates="media_items")
