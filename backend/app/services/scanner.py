import os
import json
from pathlib import Path
from typing import Dict, Set, List, Tuple
from collections import defaultdict
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models.media import MediaItem
from ..services.nfo_parser import (
    parse_nfo, get_media_type, find_local_images, is_sample,
    get_base_title, VIDEO_EXTENSIONS
)

SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", "venv", ".venv",
    "dist", "build", ".vscode", ".idea", "$RECYCLE.BIN",
    "System Volume Information", ".Trash", "Thumbs",
}

def _should_skip(dirpath: str) -> bool:
    name = Path(dirpath).name
    if name.startswith("."):
        return True
    return name.lower() in {d.lower() for d in SKIP_DIRS}


def scan_directory(media_root: str, user_id: int, db: Session, folder: str = "", category_hint: str = "") -> Dict:
    folder = folder.strip()
    
    if os.path.isabs(folder):
        scan_path = Path(folder)
    elif folder and folder != "/":
        scan_path = Path(media_root) / folder
    else:
        scan_path = Path(media_root)
    
    if not scan_path.exists():
        return {"added": 0, "updated": 0, "total": 0, "removed": 0,
                "error": f"路径不存在: {scan_path}"}
    
    # Collect all video files grouped by directory + base title
    dir_videos: Dict[Tuple[str, str], List[Tuple[int, Path, str]]] = defaultdict(list)
    dir_nfos: Dict[str, Dict[str, Path]] = {}
    
    for root, dirs, files in os.walk(scan_path):
        dirs[:] = [d for d in dirs if not _should_skip(d)]
        root_path = Path(root)
        dir_key = str(root_path)
        
        videos_in_dir = {}
        nfos_in_dir = {}
        
        for f in files:
            ftype = get_media_type(f)
            if ftype == "video" and not is_sample(f):
                stem = Path(f).stem
                videos_in_dir[stem] = root_path / f
            elif ftype == "nfo":
                stem = Path(f).stem
                nfos_in_dir[stem] = root_path / f
        
        if videos_in_dir:
            dir_nfos[dir_key] = nfos_in_dir
        
        for stem, video_path in videos_in_dir.items():
            base_title, part_num = get_base_title(stem)
            dir_videos[(dir_key, base_title)].append((part_num or 0, video_path, stem))
    
    added = 0
    updated = 0
    found_paths: Set[str] = set()
    
    for (dir_key, base_title), parts in dir_videos.items():
        root_path = Path(dir_key)
        parts.sort(key=lambda x: x[0])
        first_part = parts[0]
        all_parts = [p[1] for p in parts]
        first_stem = first_part[2]
        primary_video = first_part[1]
        
        try:
            rel_path = str(primary_video.relative_to(Path(media_root)))
        except ValueError:
            rel_path = str(primary_video)
        
        found_paths.add(rel_path)
        for _, vp, _ in parts[1:]:
            try:
                found_paths.add(str(vp.relative_to(Path(media_root))))
            except ValueError:
                found_paths.add(str(vp))
        
        result = db.execute(
            select(MediaItem).where(
                MediaItem.file_path == rel_path,
                MediaItem.user_id == user_id
            )
        )
        existing = result.scalar_one_or_none()
        
        # NFO
        nfos_in_dir = dir_nfos.get(dir_key, {})
        nfo_data = {}
        for stem_to_try in [first_stem, base_title, base_title.lower()]:
            if stem_to_try in nfos_in_dir:
                nfo_data = parse_nfo(str(nfos_in_dir[stem_to_try])) or {}
                break
        if not nfo_data:
            for fallback in ["tvshow.nfo", "movie.nfo"]:
                fallback_path = root_path / fallback
                if fallback_path.exists():
                    nfo_data = parse_nfo(str(fallback_path)) or {}
                    break
        
        # Images: THIS directory only (not parent folders)
        local_images = find_local_images(str(root_path), first_stem)
        folder_images = find_local_images(str(root_path), "")
        
        poster = (
            nfo_data.get("poster_url", "")
            or local_images.get("poster", "")
            or folder_images.get("poster", "")
        )
        fanart = (
            nfo_data.get("fanart_url", "")
            or local_images.get("fanart", "")
            or folder_images.get("fanart", "")
        )
        
        title = nfo_data.get("title") or base_title
        
        nfo_type = nfo_data.get("nfo_type", "")
        parent_name = root_path.name.lower()
        if category_hint in ("movie", "tvshow"):
            category = category_hint
        else:
            is_tv = nfo_type == "tvshow" or any(kw in parent_name for kw in ["season", "s0", "s1", "s2"])
            category = "tvshow" if is_tv else "movie"

        extra = []
        for pnum, vp, stem in parts:
            try:
                pth = str(vp.relative_to(Path(media_root)))
            except ValueError:
                pth = str(vp)
            label = f"CD{pnum}" if pnum else stem
            extra.append({"label": label, "path": pth})
        extra_json = json.dumps(extra, ensure_ascii=False)

        total_size = sum(p.stat().st_size for p in all_parts if p.exists())
        is_multipart = len(parts) > 1
        part_count = len(parts)

        if existing:
            for key, val in nfo_data.items():
                if val and key not in ("nfo_type",):
                    setattr(existing, key, val)
            if poster:
                existing.poster_url = poster
            if fanart:
                existing.fanart_url = fanart
            existing.file_size = total_size
            existing.filename = primary_video.name + (f" +{part_count-1}" if is_multipart else "")
            existing.extra_files = extra_json
            existing.category = category
            existing.file_type = category
            updated += 1
        else:
            display_name = primary_video.name + (f" +{part_count-1}" if is_multipart else "")
            item = MediaItem(
                user_id=user_id,
                file_path=rel_path,
                filename=display_name,
                file_type=category,
                file_size=total_size,
                folder=str(root_path),
                category=category,
                title=title,
                original_title=nfo_data.get("original_title", ""),
                plot=nfo_data.get("plot", ""),
                year=nfo_data.get("year"),
                genre=nfo_data.get("genre", ""),
                rating=nfo_data.get("rating"),
                director=nfo_data.get("director", ""),
                cast_list=nfo_data.get("cast_list", "[]"),
                poster_url=poster,
                fanart_url=fanart,
                extra_files=extra_json,
            )
            db.add(item)
            added += 1
    
    # Cleanup missing files — only items that belong to this scan root
    scan_root = str(scan_path)
    all_items = db.execute(select(MediaItem))
    removed = 0
    for item in all_items.scalars():
        folder = item.folder or ""
        in_this_scan = folder.startswith(scan_root) or (item.file_path or "").startswith(scan_root)
        if not in_this_scan:
            continue
        if item.file_path not in found_paths:
            if os.path.isabs(item.file_path):
                exists = Path(item.file_path).exists()
            else:
                exists = (Path(media_root) / item.file_path).exists()
            if not exists:
                db.delete(item)
                removed += 1
    
    db.commit()
    return {"added": added, "updated": updated, "total": added + updated, "removed": removed}


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
