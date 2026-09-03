import os
import json
from pathlib import Path
from typing import Callable, Dict, Optional, Set, List, Tuple
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
    total = 0
    for p in paths:
        try:
            total += p.stat().st_size
        except OSError:
            pass
    return total


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

    def notify(info: Dict):
        if progress_cb:
            try:
                progress_cb(info)
            except Exception:
                pass

    if not scan_path.exists():
        err = f"路径不存在: {scan_path}"
        notify({"status": "error", "error": err, "message": err})
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

    existing_map: Dict[str, MediaItem] = {}
    try:
        rows = db.execute(select(MediaItem).where(MediaItem.user_id == user_id))
        for item in rows.scalars():
            existing_map[item.file_path] = item
    except Exception:
        existing_map = {}

    def onerror(err):
        notify({"message": f"跳过无法访问的路径: {err}"})

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

            nfo_type = ""
            if category_hint in ("movie", "tvshow"):
                category = category_hint
            else:
                parent_name = root_path.name.lower()
                is_tv = any(kw in parent_name for kw in ["season", "s0", "s1", "s2"])
                category = "tvshow" if is_tv else "movie"

            existing = existing_map.get(rel_path)
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

            notify({
                "phase": "discover",
                "current": rel_path,
                "found": added + updated,
                "added": added,
                "updated": updated,
                "processed": added + updated,
                "message": f"扫描中：已入库 {added + updated} 项（新增 {added}，更新 {updated}）",
            })

            # Metadata (NFO / local images / size) — never abort the library
            nfo_data = {}
            try:
                for stem_to_try in [first_stem, base_title, base_title.lower()]:
                    if stem_to_try in nfos_in_dir:
                        nfo_data = _parse_nfo_safe(str(nfos_in_dir[stem_to_try]))
                        if nfo_data:
                            break
                if not nfo_data:
                    for fallback in ["tvshow.nfo", "movie.nfo"]:
                        real = files_lower.get(fallback)
                        if real:
                            nfo_data = _parse_nfo_safe(str(root_path / real))
                            if nfo_data:
                                break
            except Exception:
                nfo_data = {}

            try:
                local_images = _images_from_files(root_path, files, first_stem)
            except Exception:
                local_images = {"poster": "", "fanart": ""}

            try:
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
                existing.file_size = _safe_size(all_parts)
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
        "found": added + updated,
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
