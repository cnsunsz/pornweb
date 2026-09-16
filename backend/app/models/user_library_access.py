from sqlalchemy import Column, Integer, ForeignKey, DateTime, UniqueConstraint
from datetime import datetime, timezone
from ..core.database import Base


class UserLibraryAccess(Base):
    """Per-user media library ACL. Admins ignore this table (always all libraries)."""

    __tablename__ = "user_library_access"
    __table_args__ = (
        UniqueConstraint("user_id", "library_id", name="uq_user_library_access"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    library_id = Column(
        Integer,
        ForeignKey("media_libraries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
