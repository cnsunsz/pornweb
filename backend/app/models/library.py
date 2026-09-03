from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime, timezone
from ..core.database import Base


class MediaLibrary(Base):
    __tablename__ = "media_libraries"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    path = Column(String(1000), nullable=False, unique=True)
    type = Column(String(20), default="movie")  # movie, tvshow, mixed
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
