import os
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Optional, Set, List, Tuple, Any
from collections import defaultdict
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models.media import MediaItem
from ..services.nfo_parser import (
    parse_nfo, get_media_type, is_sample,
    get_base_title, IMAGE_EXTENSIONS
)

SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", "venv", ".venv",
    "dist", "build", ".vscode", ".idea", "$RECYCLE.BIN",
    "System Volume Information", ".Trash", "Thumbs",
}

POSTER_NAMES = ["poster", "folder", "cover", "default", "movie", "show"]
FANART_NAMES = ["fanart", "backdrop", "background"]

ProgressCb = Optional[Callable[[Dict], None]]

# Throttle job-progress DB writes so they don't amplify rclone latency.
_PROGRESS_MIN_INTERVAL = 0.5


def _should_skip(dirpath: str) -> bool:
    name = Path(dirpath).name
    if name.startswith("."):
        return True
    return name.lower() in {d.lower() for d in SKIP_DIRS}


def _rel_path(path: Path, media_root: str) -> str:
    try:
        return str(path.relative_to(Path(media_root)))
    except ValueError:
        return str(path)


def _safe_size(paths: List[Path]) -> int:
    """Best-effort size; never let one hung/stat-error kill the scan."""
    total = 0
    for p in paths:
        try:
            total += p.stat().st_size
        except OSError:
            pass
    return total


def _safe_mtime(path: Path) -> Optional[float]:
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def _images_from_files(root_path: Path, files: List[str], stem: str) -> Dict[str, str]:
    """Match poster/fanart from os.walk filenames (no extra rclone readdir)."""
    result = {"poster": "", "fanart": ""}
    all_images = {}
    for f in files:
        p = Path(f)
        if p.suffix.lower() in IMAGE_EXTENSIONS:
            all_images[p.stem.lower()] = str(root_path / f)

    if stem:
        stem_lower = stem.lower()
        for key in [f"{stem_lower}-poster", f"{stem_lower}.poster", stem_lower]:
            if key in all_images:
                result["poster"] = all_images[key]
                break
        if not result["poster"]:
            for name in POSTER_NAMES:
                for key in [f"{stem_lower}-{name}", f"{stem_lower}.{name}"]:
                    if key in all_images:
                        result["poster"] = all_images[key]
                        break
                if result["poster"]:
                    break
    if not result["poster"]:
        for name in POSTER_NAMES:
            if name in all_images:
                result["poster"] = all_images[name]
                break

    if stem:
        for name in FANART_NAMES:
            key = f"{stem.lower()}-{name}"
            if key in all_images:
                result["fanart"] = all_images[key]
                break
    if not result["fanart"]:
        for name in FANART_NAMES:
            if name in all_images:
                result["fanart"] = all_images[name]
                break
    return result


def _parse_nfo_safe(nfo_path: str) -> Dict:
    try:
        return parse_nfo(nfo_path) or {}
    except Exception:
        return {}


def _has_usable_meta(item: MediaItem) -> bool:
    return bool(
        (item.title or "").strip()
        and ((item.plot or "").strip() or (item.poster_url or "").strip())
    )


def _should_skip_nfo(item: MediaItem, nfo_path: Optional[Path], is_new: bool) -> bool:
    """Skip re-parse when existing row already has meta and NFO mtime is unchanged."""
    if is_new or not nfo_path:
        return False
    if not _has_usable_meta(item):
        return False
    mtime = _safe_mtime(nfo_path)
    if mtime is None:
        return False
    stored = getattr(item, "nfo_mtime", None)
    if stored is not None and float(stored) >= mtime:
        return True
    # Fallback: compare against updated_at when nfo_mtime column not yet filled.
    updated = getattr(item, "updated_at", None)
    if updated is not None and stored is None:
        try:
            ts = updated.timestamp() if updated.tzinfo else updated.replace(tzinfo=timezone.utc).timestamp()
            if ts >= mtime:
                return True
        except Exception:
            pass
    return False


class _ThrottledProgress:
    """Forward progress to CB at most every N seconds; always flush phase/done/error."""

    def __init__(self, cb: ProgressCb, min_interval: float = _PROGRESS_MIN_INTERVAL):
        self._cb = cb
        self._min_interval = min_interval
        self._last = 0.0
        self._last_phase = None

    def __call__(self, info: Dict):
        if not self._cb:
            return
        phase = info.get("phase")
        force = (
            phase in ("done", "cleanup", "error")
            or info.get("error")
            or (phase is not None and phase != self._last_phase)
        )
        now = time.monotonic()
        if not force and (now - self._last) < self._min_interval:
            return
        self._last = now
        if phase is not None:
            self._last_phase = phase
        try:
            self._cb(info)
        except Exception:
            pass


def scan_directory(
    media_root: str,
    user_id: int,
    db: Session,
    folder: str = "",
    category_hint: str = "",
    progress_cb: ProgressCb = None,
) -> Dict:
    folder = (folder or "").strip()

    if os.path.isabs(folder):
        scan_path = Path(folder)
    elif folder and folder != "/":
        scan_path = Path(media_root) / folder
    else:
        scan_path = Path(media_root)

    notify = _ThrottledProgress(progress_cb)

    try:
        path_ok = scan_path.exists()
    except OSError as exc:
        err = f"路径不可访问: {scan_path} ({exc})"
        notify({"status": "error", "phase": "error", "error": err, "message": err})
        return {"added": 0, "updated": 0, "total": 0, "removed": 0, "found": 0, "error": err}

    if not path_ok:
        err = f"路径不存在: {scan_path}"
        notify({"status": "error", "phase": "error", "error": err, "message": err})
        return {"added": 0, "updated": 0, "total": 0, "removed": 0,
                "found": 0, "error": err}

    notify({
        "phase": "discover",
        "message": f"正在扫描 {scan_path} …",
        "current": str(scan_path),
    })

    added = 0
    updated = 0
    found_paths: Set[str] = set()
    # Deferred metadata work: (item, all_parts, nfo_path, root_path, files, first_stem, base_title, category, is_new)
    pending_meta: List[Dict[str, Any]] = []

    existing_map: Dict[str, MediaItem] = {}
    try:
        rows = db.execute(select(MediaItem).where(MediaItem.user_id == user_id))
        for item in rows.scalars():
            existing_map[item.file_path] = item
    except Exception:
        existing_map = {}

    def onerror(err):
        notify({"phase": "discover", "message": f"跳过无法访问的路径: {err}"})

    # ── Phase 1: discover & upsert rows quickly ──────────────────────────
    for root, dirs, files in os.walk(scan_path, onerror=onerror):
        dirs[:] = [d for d in dirs if not _should_skip(d)]
        root_path = Path(root)
        dir_key = str(root_path)

        videos_in_dir = {}
        nfos_in_dir = {}
        files_lower = {f.lower(): f for f in files}

        for f in files:
            ftype = get_media_type(f)
            if ftype == "video" and not is_sample(f):
                videos_in_dir[Path(f).stem] = root_path / f
            elif ftype == "nfo":
                nfos_in_dir[Path(f).stem] = root_path / f

        if not videos_in_dir:
            continue

        dir_videos: Dict[str, List[Tuple[int, Path, str]]] = defaultdict(list)
        for stem, video_path in videos_in_dir.items():
            base_title, part_num = get_base_title(stem)
            dir_videos[base_title].append((part_num or 0, video_path, stem))

        for base_title, parts in dir_videos.items():
            parts.sort(key=lambda x: x[0])
            first_part = parts[0]
            all_parts = [p[1] for p in parts]
            first_stem = first_part[2]
            primary_video = first_part[1]

            rel_path = _rel_path(primary_video, media_root)
            found_paths.add(rel_path)
            for _, vp, _ in parts[1:]:
                found_paths.add(_rel_path(vp, media_root))

            extra = []
            for pnum, vp, stem in parts:
                pth = _rel_path(vp, media_root)
                label = f"CD{pnum}" if pnum else stem
                extra.append({"label": label, "path": pth})
            extra_json = json.dumps(extra, ensure_ascii=False)
            is_multipart = len(parts) > 1
            part_count = len(parts)
            display_name = primary_video.name + (f" +{part_count-1}" if is_multipart else "")

            if category_hint in ("movie", "tvshow"):
                category = category_hint
            else:
                parent_name = root_path.name.lower()
                is_tv = any(kw in parent_name for kw in ["season", "s0", "s1", "s2"])
                category = "tvshow" if is_tv else "movie"

            existing = existing_map.get(rel_path)
            is_new = existing is None
            if existing:
                existing.filename = display_name
                existing.extra_files = extra_json
                existing.folder = dir_key
                existing.category = category
                existing.file_type = category
                if not existing.title:
                    existing.title = base_title
                updated += 1
            else:
                item = MediaItem(
                    user_id=user_id,
                    file_path=rel_path,
                    filename=display_name,
                    file_type=category,
                    file_size=0,
                    folder=dir_key,
                    category=category,
                    title=base_title,
                    original_title="",
                    plot="",
                    extra_files=extra_json,
                )
                db.add(item)
                existing_map[rel_path] = item
                existing = item
                added += 1

            try:
                db.commit()
            except Exception:
                try:
                    db.rollback()
                except Exception:
                    pass

            # Resolve NFO path for later metadata phase
            nfo_path: Optional[Path] = None
            for stem_to_try in [first_stem, base_title, base_title.lower()]:
                if stem_to_try in nfos_in_dir:
                    nfo_path = nfos_in_dir[stem_to_try]
                    break
            if nfo_path is None:
                for fallback in ["tvshow.nfo", "movie.nfo"]:
                    real = files_lower.get(fallback)
                    if real:
                        nfo_path = root_path / real
                        break

            pending_meta.append({
                "item": existing,
                "all_parts": all_parts,
                "nfo_path": nfo_path,
                "root_path": root_path,
                "files": files,
                "first_stem": first_stem,
                "base_title": base_title,
                "category_hint": category_hint,
                "category": category,
                "is_new": is_new,
            })

            notify({
                "phase": "discover",
                "current": rel_path,
                "found": added + updated,
                "added": added,
                "updated": updated,
                "processed": added + updated,
                "message": f"扫描中：已入库 {added + updated} 项（新增 {added}，更新 {updated}）",
            })

    total_found = added + updated
    meta_total = len(pending_meta)

    # ── Phase 2: NFO / local images / size (visible metadata progress) ───
    notify({
        "phase": "metadata",
        "found": total_found,
        "added": added,
        "updated": updated,
        "processed": 0,
        "message": f"正在读取元数据（0/{meta_total}）",
    })

    for idx, work in enumerate(pending_meta, start=1):
        existing: MediaItem = work["item"]
        all_parts: List[Path] = work["all_parts"]
        nfo_path: Optional[Path] = work["nfo_path"]
        root_path: Path = work["root_path"]
        files: List[str] = work["files"]
        first_stem: str = work["first_stem"]
        base_title: str = work["base_title"]
        category = work["category"]
        category_hint = work["category_hint"]
        is_new: bool = work["is_new"]

        display = (existing.title or base_title or existing.filename or "")[:80]
        notify({
            "phase": "metadata",
            "current": existing.file_path or "",
            "found": total_found,
            "added": added,
            "updated": updated,
            "processed": idx,
            "message": f"正在读取元数据：{display} ({idx}/{meta_total})",
        })

        skip_nfo = _should_skip_nfo(existing, nfo_path, is_new)
        nfo_data: Dict = {}
        if not skip_nfo and nfo_path is not None:
            nfo_data = _parse_nfo_safe(str(nfo_path))

        try:
            local_images = _images_from_files(root_path, files, first_stem)
        except Exception:
            local_images = {"poster": "", "fanart": ""}

        try:
            if nfo_data:
                poster = (
                    nfo_data.get("poster_url", "")
                    or local_images.get("poster", "")
                )
                fanart = (
                    nfo_data.get("fanart_url", "")
                    or local_images.get("fanart", "")
                )
                title = nfo_data.get("title") or existing.title or base_title
                nfo_type = nfo_data.get("nfo_type", "")
                if category_hint not in ("movie", "tvshow"):
                    is_tv = nfo_type == "tvshow" or any(
                        kw in root_path.name.lower() for kw in ["season", "s0", "s1", "s2"]
                    )
                    category = "tvshow" if is_tv else "movie"

                for key, val in nfo_data.items():
                    if val and key not in ("nfo_type",) and hasattr(existing, key):
                        setattr(existing, key, val)
                if poster:
                    existing.poster_url = poster
                if fanart:
                    existing.fanart_url = fanart
                existing.title = title
                existing.category = category
                existing.file_type = category
                if nfo_path is not None:
                    mt = _safe_mtime(nfo_path)
                    if mt is not None and hasattr(existing, "nfo_mtime"):
                        existing.nfo_mtime = float(mt)
            elif not skip_nfo:
                # No NFO — still apply local images if missing
                if not (existing.poster_url or "").strip() and local_images.get("poster"):
                    existing.poster_url = local_images["poster"]
                if not (existing.fanart_url or "").strip() and local_images.get("fanart"):
                    existing.fanart_url = local_images["fanart"]

            # Skip expensive rclone stat on unchanged existing items with size already set.
            need_size = is_new or not (existing.file_size and existing.file_size > 0)
            if need_size:
                existing.file_size = _safe_size(all_parts)

            existing.updated_at = datetime.now(timezone.utc)
            db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass

    notify({
        "phase": "cleanup",
        "message": "正在清理已删除的条目…",
        "added": added,
        "updated": updated,
        "found": total_found,
        "processed": meta_total,
    })

    scan_root = str(scan_path)
    removed = 0
    try:
        all_items = db.execute(select(MediaItem)).scalars().all()
        for item in all_items:
            folder_val = item.folder or ""
            in_this_scan = folder_val.startswith(scan_root) or (item.file_path or "").startswith(scan_root)
            if not in_this_scan:
                continue
            if item.file_path not in found_paths:
                db.delete(item)
                removed += 1
        db.commit()
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass

    result = {
        "added": added,
        "updated": updated,
        "total": added + updated,
        "removed": removed,
        "found": added + updated,
    }
    notify({
        "phase": "done",
        "added": added,
        "updated": updated,
        "removed": removed,
        "found": added + updated,
        "processed": added + updated,
        "message": f"扫描完成：新增 {added}，更新 {updated}，清理 {removed}",
    })
    return result


def delete_media_by_folder(folder_path: str, db: Session) -> int:
    """Delete all media items whose folder starts with the given path."""
    folder_fwd = folder_path.replace("\\", "/")
    folder_bwd = folder_path.replace("/", "\\")
    result = db.execute(
        select(MediaItem).where(
            MediaItem.folder.startswith(folder_path)
            | MediaItem.folder.startswith(folder_fwd)
            | MediaItem.folder.startswith(folder_bwd)
        )
    )
    items = result.scalars().all()
    for item in items:
        db.delete(item)
    db.commit()
    return len(items)
