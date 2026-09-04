from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from .config import settings

def _sync_url(url: str) -> str:
    return (url or "").replace("sqlite+aiosqlite", "sqlite")

_URL = _sync_url(settings.DATABASE_URL)
_connect = {"check_same_thread": False} if _URL.startswith("sqlite") else {}
engine = create_engine(_URL, echo=False, connect_args=_connect, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)

if _URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=8000")
        cur.close()

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def _migrate_media_columns(sync_conn):
    """Additive SQLite ALTERs; tolerate multi-worker races (duplicate column)."""
    try:
        rows = sync_conn.execute(text("PRAGMA table_info(media_items)")).fetchall()
    except Exception:
        return
    cols = {r[1] for r in rows}
    alters = []
    if "extra_files" not in cols:
        alters.append("ALTER TABLE media_items ADD COLUMN extra_files TEXT DEFAULT '[]'")
    if "duration" not in cols:
        alters.append("ALTER TABLE media_items ADD COLUMN duration FLOAT DEFAULT 0")
    if "nfo_mtime" not in cols:
        alters.append("ALTER TABLE media_items ADD COLUMN nfo_mtime FLOAT")
    for sql in alters:
        try:
            sync_conn.execute(text(sql))
        except Exception as exc:
            # Another uvicorn worker may have added the column first.
            if "duplicate column" not in str(exc).lower():
                raise

def init_db():
    from ..models import User, MediaItem, MediaLibrary, PlaybackProgress, ScanJob  # noqa: F401
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as exc:
        if "already exists" not in str(exc).lower():
            raise
    with engine.begin() as conn:
        _migrate_media_columns(conn)
