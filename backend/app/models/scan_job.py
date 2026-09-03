from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime, timezone
from ..core.database import Base


class ScanJob(Base):
    __tablename__ = "scan_jobs"

    id = Column(Integer, primary_key=True, index=True)
    library_id = Column(Integer, nullable=True, index=True)
    path = Column(String(1000), nullable=False, index=True)
    user_id = Column(Integer, nullable=False)
    status = Column(String(20), default="running", index=True)  # running, done, error
    phase = Column(String(40), default="discover")
    current = Column(String(1000), default="")
    found = Column(Integer, default=0)
    added = Column(Integer, default=0)
    updated = Column(Integer, default=0)
    removed = Column(Integer, default=0)
    processed = Column(Integer, default=0)
    error = Column(Text, default="")
    message = Column(String(500), default="")
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    finished_at = Column(DateTime)
