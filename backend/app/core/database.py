from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from .config import settings

def _sync_url(url: str) -> str:
    return (url or "").replace("sqlite+aiosqlite", "sqlite")

_URL = _sync_url(settings.DATABASE_URL)
_connect = {"check_same_thread": False} if _URL.startswith("sqlite") else {}
engine = create_engine(_URL, echo=False, connect_args=_connect)
SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def _migrate_media_columns(sync_conn):
    try:
        rows = sync_conn.execute(text("PRAGMA table_info(media_items)")).fetchall()
    except Exception:
        return
    cols = {r[1] for r in rows}
    if "extra_files" not in cols:
        sync_conn.execute(text("ALTER TABLE media_items ADD COLUMN extra_files TEXT DEFAULT '[]'"))
    if "duration" not in cols:
        sync_conn.execute(text("ALTER TABLE media_items ADD COLUMN duration FLOAT DEFAULT 0"))

def init_db():
    from ..models import User, MediaItem, MediaLibrary, PlaybackProgress  # noqa: F401
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        _migrate_media_columns(conn)
