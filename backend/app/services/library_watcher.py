"""Emby/Jellyfin-style library auto-scan.

Prefer watchdog for local FS events; rclone/FUSE often lacks reliable inotify,
so a periodic full rescan always runs as a safety net.
"""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Dict, Optional, Set

from sqlalchemy import select

from ..core.config import settings
from ..core.database import SessionLocal
from ..models.library import MediaLibrary
from ..models.user import User
from .scan_runner import start_scan

logger = logging.getLogger(__name__)

# Mutable runtime config (settings API can update without full process restart).
_runtime = {
    "enabled": True,
    "interval_minutes": 15,
    "debounce_seconds": 45,
}

_watcher_instance: Optional["LibraryWatcherService"] = None
_lock = threading.Lock()


def configure(
    enabled: Optional[bool] = None,
    interval_minutes: Optional[int] = None,
    debounce_seconds: Optional[int] = None,
) -> None:
    if enabled is not None:
        _runtime["enabled"] = bool(enabled)
    if interval_minutes is not None:
        _runtime["interval_minutes"] = max(1, int(interval_minutes))
    if debounce_seconds is not None:
        _runtime["debounce_seconds"] = max(5, int(debounce_seconds))


def get_runtime() -> Dict:
    return dict(_runtime)


def _admin_user_id(db) -> Optional[int]:
    row = db.execute(select(User).where(User.is_admin == True).order_by(User.id)).scalars().first()  # noqa: E712
    if row:
        return row.id
    row = db.execute(select(User).order_by(User.id)).scalars().first()
    return row.id if row else None


def _list_libraries(db):
    return list(db.execute(select(MediaLibrary).order_by(MediaLibrary.id)).scalars().all())


class LibraryWatcherService:
    def __init__(self):
        self._stop = threading.Event()
        self._pending: Dict[str, float] = {}  # path -> last event monotonic
        self._pending_meta: Dict[str, Dict] = {}  # path -> {library_id, user_id, type}
        self._observer = None
        self._threads: list = []
        self._watched_paths: Set[str] = set()

    def start(self) -> None:
        configure(
            enabled=bool(getattr(settings, "AUTO_SCAN_ENABLED", True)),
            interval_minutes=int(getattr(settings, "AUTO_SCAN_INTERVAL_MINUTES", 15) or 15),
        )
        if not _runtime["enabled"]:
            logger.info("library auto-scan disabled by config")
            return
        t_debounce = threading.Thread(target=self._debounce_loop, name="lib-debounce", daemon=True)
        t_periodic = threading.Thread(target=self._periodic_loop, name="lib-periodic", daemon=True)
        t_debounce.start()
        t_periodic.start()
        self._threads = [t_debounce, t_periodic]
        self._start_watchdog()
        logger.info(
            "library auto-scan started (interval=%sm debounce=%ss)",
            _runtime["interval_minutes"],
            _runtime["debounce_seconds"],
        )

    def stop(self) -> None:
        self._stop.set()
        if self._observer is not None:
            try:
                self._observer.stop()
                self._observer.join(timeout=5)
            except Exception:
                pass
            self._observer = None

    def _start_watchdog(self) -> None:
        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler
        except ImportError:
            logger.warning("watchdog not installed; relying on periodic rescan only")
            return

        service = self

        class _Handler(FileSystemEventHandler):
            def on_any_event(self, event):
                if getattr(event, "is_directory", False) and event.event_type in ("modified",):
                    return
                src = getattr(event, "src_path", None) or ""
                if not src:
                    return
                # Ignore noise from temp/partial downloads
                name = Path(src).name.lower()
                if name.endswith((".tmp", ".part", ".partial", ".download", ".crdownload")):
                    return
                service._note_event(src)

        try:
            observer = Observer()
            db = SessionLocal()
            try:
                libs = _list_libraries(db)
            finally:
                db.close()
            handler = _Handler()
            for lib in libs:
                path = (lib.path or "").strip()
                if not path or path in self._watched_paths:
                    continue
                if not Path(path).is_dir():
                    continue
                try:
                    observer.schedule(handler, path, recursive=True)
                    self._watched_paths.add(path)
                except Exception as exc:
                    # FUSE / permission — periodic scan still covers this library.
                    logger.warning("watchdog skip %s: %s", path, exc)
            if self._watched_paths:
                observer.start()
                self._observer = observer
            else:
                logger.info("no local paths scheduled for watchdog; periodic only")
        except Exception as exc:
            logger.warning("watchdog failed to start: %s", exc)

    def _resolve_library_for_path(self, src: str) -> Optional[Dict]:
        db = SessionLocal()
        try:
            libs = _list_libraries(db)
            uid = _admin_user_id(db)
            if uid is None:
                return None
            src_n = str(Path(src))
            best = None
            best_len = -1
            for lib in libs:
                lp = (lib.path or "").rstrip("/\\")
                if not lp:
                    continue
                if src_n == lp or src_n.startswith(lp + "/") or src_n.startswith(lp + "\\"):
                    if len(lp) > best_len:
                        best = {
                            "path": lib.path,
                            "library_id": lib.id,
                            "user_id": uid,
                            "type": lib.type or "",
                        }
                        best_len = len(lp)
            return best
        finally:
            db.close()

    def _note_event(self, src: str) -> None:
        if not _runtime["enabled"]:
            return
        meta = self._resolve_library_for_path(src)
        if not meta:
            return
        path = meta["path"]
        with _lock:
            self._pending[path] = time.monotonic()
            self._pending_meta[path] = meta

    def _debounce_loop(self) -> None:
        while not self._stop.wait(2.0):
            if not _runtime["enabled"]:
                continue
            due_metas = []
            now = time.monotonic()
            quiet = float(_runtime["debounce_seconds"])
            with _lock:
                due_paths = [
                    path for path, ts in list(self._pending.items())
                    if (now - ts) >= quiet
                ]
                for path in due_paths:
                    self._pending.pop(path, None)
                    meta = self._pending_meta.pop(path, None)
                    if meta:
                        due_metas.append(meta)
            for meta in due_metas:
                self._trigger(meta)

    def _trigger(self, meta: Dict) -> None:
        try:
            start_scan(
                meta["user_id"],
                meta["path"],
                library_id=meta.get("library_id"),
                category_hint=meta.get("type") or "",
            )
            logger.info("auto-scan triggered for %s", meta.get("path"))
        except Exception as exc:
            logger.warning("auto-scan start failed: %s", exc)

    def _periodic_loop(self) -> None:
        # Initial delay so startup / mark_stale_jobs settle first.
        if self._stop.wait(60):
            return
        while not self._stop.is_set():
            if _runtime["enabled"]:
                self._scan_all_libraries()
            # Sleep in chunks so stop/config changes apply sooner.
            interval = max(1, int(_runtime["interval_minutes"])) * 60
            elapsed = 0
            while elapsed < interval and not self._stop.is_set():
                step = min(15, interval - elapsed)
                if self._stop.wait(step):
                    return
                elapsed += step
                # Re-check enabled / interval mid-sleep
                if not _runtime["enabled"]:
                    break
                interval = max(1, int(_runtime["interval_minutes"])) * 60

    def _scan_all_libraries(self) -> None:
        db = SessionLocal()
        try:
            uid = _admin_user_id(db)
            if uid is None:
                return
            libs = _list_libraries(db)
            for lib in libs:
                try:
                    start_scan(
                        uid, lib.path, library_id=lib.id, category_hint=lib.type or ""
                    )
                except Exception as exc:
                    logger.warning("periodic scan %s failed: %s", lib.path, exc)
        finally:
            db.close()


def start_library_watcher() -> None:
    global _watcher_instance
    with _lock:
        if _watcher_instance is not None:
            return
        svc = LibraryWatcherService()
        _watcher_instance = svc
    svc.start()


def stop_library_watcher() -> None:
    global _watcher_instance
    with _lock:
        svc = _watcher_instance
        _watcher_instance = None
    if svc:
        svc.stop()
