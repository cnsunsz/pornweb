import json
import os
import re
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from xml.etree import ElementTree as ET

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".ts", ".m4v", ".rmvb", ".rm", ".mpg", ".mpeg", ".webm"}
NFO_EXTENSIONS = {".nfo"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

POSTER_NAMES = ["poster", "folder", "cover", "default", "movie", "show"]
FANART_NAMES = ["fanart", "backdrop", "background"]
BANNER_NAMES = ["banner"]
THUMB_NAMES = ["thumb", "landscape"]

# Multi-part patterns (Jellyfin style)
MULTIPART_PATTERNS = [
    # CD1, CD2, Disc1, Disc2
    re.compile(r"^(.+?)[\s._-]*(?:cd|disc|disk)[\s._-]*(\d+)$", re.IGNORECASE),
    # Part1, Part2, PT1, PT2
    re.compile(r"^(.+?)[\s._-]*(?:part|pt)[\s._-]*(\d+)$", re.IGNORECASE),
]


def get_base_title(filename_stem: str) -> Tuple[str, Optional[int]]:
    """Extract base title and part number from filename.
    
    Examples:
        "DANDY-553-CD1" -> ("DANDY-553", 1)
        "DANDY-553-CD2" -> ("DANDY-553", 2)
        "Movie Part 1" -> ("Movie", 1)
        "Movie-disc3" -> ("Movie", 3)
        "Movie" -> ("Movie", None)
    """
    stem = filename_stem.strip()
    
    for pattern in MULTIPART_PATTERNS:
        m = pattern.match(stem)
        if m:
            base = m.group(1).strip(" -._")
            try:
                part_num = int(m.group(2))
                return base, part_num
            except (ValueError, IndexError):
                pass
    
    return stem, None


def find_local_images(directory: str, stem: str = "") -> Dict[str, str]:
    result = {"poster": "", "fanart": "", "banner": "", "thumb": ""}
    dirpath = Path(directory)
    if not dirpath.exists():
        return result
    
    all_images = {}
    for f in dirpath.iterdir():
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS:
            all_images[f.stem.lower()] = str(f)
    
    if stem:
        stem_lower = stem.lower()
        # Jellyfin: MovieName-poster.jpg / MovieName.jpg / MovieName.poster.jpg
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
    
    for name in BANNER_NAMES:
        if name in all_images:
            result["banner"] = all_images[name]
            break
    
    for name in THUMB_NAMES:
        if name in all_images:
            result["thumb"] = all_images[name]
            break
    
    return result


def parse_nfo(nfo_path: str) -> Optional[Dict]:
    encodings = ["utf-8", "utf-8-sig", "gbk", "gb18030", "latin-1", "cp1252"]
    content = None
    
    for enc in encodings:
        try:
            with open(nfo_path, "r", encoding=enc) as f:
                content = f.read()
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    
    if not content:
        try:
            with open(nfo_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception:
            return None
    
    try:
        root = ET.fromstring(content)
    except Exception:
        return None
    
    result = {}
    nfo_dir = str(Path(nfo_path).parent)
    
    # Type
    result["nfo_type"] = root.tag.lower()
    
    # Title
    result["title"] = _get_text(root, "title") or _get_text(root, "originaltitle") or ""
    result["original_title"] = _get_text(root, "originaltitle") or ""
    
    # Plot
    result["plot"] = _get_text(root, "plot") or _get_text(root, "outline") or ""
    
    # Year
    year_str = _get_text(root, "year")
    if not year_str:
        premiered = _get_text(root, "premiered") or _get_text(root, "releasedate") or ""
        if len(premiered) >= 4:
            year_str = premiered[:4]
    try:
        result["year"] = int(year_str) if year_str else None
    except (ValueError, TypeError):
        result["year"] = None
    
    # Genre
    genres = [g.text.strip() for g in root.findall("genre") if g.text]
    result["genre"] = ", ".join(genres)
    
    # Rating
    rating_el = root.find("rating")
    if rating_el is not None:
        if rating_el.text and rating_el.text.strip():
            try:
                result["rating"] = float(rating_el.text.strip())
            except (ValueError, TypeError):
                result["rating"] = None
        else:
            value_el = rating_el.find("value")
            if value_el is not None and value_el.text:
                try:
                    result["rating"] = float(value_el.text.strip())
                except (ValueError, TypeError):
                    result["rating"] = None
            else:
                result["rating"] = None
    else:
        result["rating"] = None
    
    # Director
    result["director"] = _get_text(root, "director") or ""
    
    # Cast
    actors = []
    for actor in root.findall("actor"):
        name_el = actor.find("name")
        if name_el is not None and name_el.text:
            actors.append(name_el.text.strip())
    result["cast_list"] = json.dumps(actors, ensure_ascii=False)
    
    # Poster - resolve relative paths
    poster_raw = _get_text(root, "poster") or _get_text(root, "thumb") or ""
    if not poster_raw:
        poster_el = root.find(".//poster")
        if poster_el is not None and poster_el.text:
            poster_raw = poster_el.text.strip()
    
    if poster_raw and not poster_raw.startswith("http"):
        poster_candidate = Path(nfo_dir) / poster_raw
        if poster_candidate.exists():
            result["poster_url"] = str(poster_candidate)
        else:
            result["poster_url"] = poster_raw
    else:
        result["poster_url"] = poster_raw
    
    # Fanart
    fanart_raw = ""
    fanart_el = root.find("fanart")
    if fanart_el is not None:
        if fanart_el.text and fanart_el.text.strip():
            fanart_raw = fanart_el.text.strip()
        else:
            thumbs = fanart_el.findall("thumb")
            if thumbs and thumbs[0].text:
                fanart_raw = thumbs[0].text.strip()
    if not fanart_raw:
        fanart_raw = _get_text(root, "thumb") or ""
    
    if fanart_raw and not fanart_raw.startswith("http"):
        fanart_candidate = Path(nfo_dir) / fanart_raw
        if fanart_candidate.exists():
            result["fanart_url"] = str(fanart_candidate)
        else:
            result["fanart_url"] = fanart_raw
    else:
        result["fanart_url"] = fanart_raw
    
    return result


def _get_text(element, tag: str) -> Optional[str]:
    el = element.find(tag)
    if el is not None and el.text:
        return el.text.strip()
    return None


def get_media_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext in NFO_EXTENSIONS:
        return "nfo"
    if ext in VIDEO_EXTENSIONS:
        return "video"
    if ext in IMAGE_EXTENSIONS:
        return "image"
    return "other"


def is_sample(filename: str) -> bool:
    name = filename.lower()
    return any(kw in name for kw in ["sample", "trailer", "预告", "花絮"])
