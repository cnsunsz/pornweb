"""Background library scan jobs persisted in SQLite (visible to all uvicorn workers)."""
import threading
from datetime import datetime, timezone
from typing import Dict, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..core.database import SessionLocal
from ..core.config import settings
from ..models.scan_job import ScanJob
from .scanner import scan_directory

_lock = threading.Lock()


def job_to_dict(job: Optional[ScanJob]) -> Dict:
    if not job:
        return {
            "status": "idle",
            "added": 0,
            "updated": 0,
            "total": 0,
            "removed": 0,
            "found": 0,
            "processed": 0,
            "message": "",
            "error": None,
        }
    err = (job.error or "").strip() or None
    return {
        "job_id": job.id,
        "library_id": job.library_id,
        "status": job.status or "idle",
        "phase": job.phase or "",
        "current": job.current or "",
        "found": job.found or 0,
        "added": job.added or 0,
        "updated": job.updated or 0,
        "removed": job.removed or 0,
        "total": (job.added or 0) + (job.updated or 0),
        "processed": job.processed or 0,
        "error": err,
        "message": job.message or "",
    }


def get_latest_job(db: Session, library_id: Optional[int] = None, path: Optional[str] = None) -> Optional[ScanJob]:
    q = select(ScanJob)
    if library_id is not None:
        q = q.where(ScanJob.library_id == library_id)
    elif path:
        q = q.where(ScanJob.path == path)
    else:
        return None
    q = q.order_by(ScanJob.id.desc())
    return db.execute(q).scalars().first()


def running_jobs_by_library(db: Session) -> Dict[int, ScanJob]:
    rows = db.execute(select(ScanJob).where(ScanJob.status == "running")).scalars().all()
    out: Dict[int, ScanJob] = {}
    for job in rows:
        if job.library_id is not None:
            out[job.library_id] = job
    return out


def start_scan(user_id: int, path: str, library_id: Optional[int] = None, category_hint: str = "") -> Dict:
    path = (path or "").strip()
    with _lock:
        db = SessionLocal()
        try:
            existing = db.execute(
                select(ScanJob).where(ScanJob.status == "running", ScanJob.path == path)
            ).scalars().first()
            if existing:
                return job_to_dict(existing)
            job = ScanJob(
                library_id=library_id,
                path=path,
                user_id=user_id,
                status="running",
                phase="discover",
                message="扫描已在后台开始",
                started_at=datetime.now(timezone.utc),
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            job_id = job.id
            payload = job_to_dict(job)
        finally:
            db.close()

    t = threading.Thread(
        target=_run_job,
        args=(job_id, user_id, path, category_hint),
        daemon=True,
        name=f"scan-{job_id}",
    )
    t.start()
    return payload


def _run_job(job_id: int, user_id: int, path: str, category_hint: str) -> None:
    scan_db = SessionLocal()
    job_db = SessionLocal()
    try:
        def progress_cb(info: Dict):
            job = job_db.get(ScanJob, job_id)
            if not job:
                return
            for key in (
                "phase", "current", "found", "added", "updated",
                "removed", "processed", "message", "error",
            ):
                if key in info and info[key] is not None:
                    setattr(job, key, info[key])
            try:
                job_db.commit()
            except Exception:
                try:
                    job_db.rollback()
                except Exception:
                    pass

        result = scan_directory(
            settings.MEDIA_ROOT,
            user_id,
            scan_db,
            path,
            category_hint=category_hint,
            progress_cb=progress_cb,
        )
        job = job_db.get(ScanJob, job_id)
        if job:
            err = result.get("error") or ""
            job.status = "error" if err else "done"
            job.phase = "done"
            job.added = result.get("added", 0)
            job.updated = result.get("updated", 0)
            job.removed = result.get("removed", 0)
            job.found = result.get("found", result.get("total", 0))
            job.processed = result.get("total", job.found)
            job.error = err
            job.message = err or (
                f"扫描完成：新增 {job.added}，更新 {job.updated}，清理 {job.removed}"
            )
            job.finished_at = datetime.now(timezone.utc)
            job_db.commit()
    except Exception as exc:
        try:
            job = job_db.get(ScanJob, job_id)
            if job:
                job.status = "error"
                job.error = str(exc)
                job.message = f"扫描失败: {exc}"
                job.finished_at = datetime.now(timezone.utc)
                job_db.commit()
        except Exception:
            pass
    finally:
        scan_db.close()
        job_db.close()


def mark_stale_jobs() -> None:
    db = SessionLocal()
    try:
        rows = db.execute(select(ScanJob).where(ScanJob.status == "running")).scalars().all()
        now = datetime.now(timezone.utc)
        for job in rows:
            job.status = "error"
            job.error = "interrupted"
            job.message = "服务重启，扫描已中断，请重新扫描"
            job.finished_at = now
        if rows:
            db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()
