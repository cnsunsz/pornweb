import json
import re
from pathlib import Path
from typing import Optional, Dict, Tuple

# Prefer defusedxml to avoid XXE on untrusted NFO; fall back to stdlib.
try:
    from defusedxml.ElementTree import fromstring as _xml_fromstring
except ImportError:  # pragma: no cover
    from xml.etree.ElementTree import fromstring as _xml_fromstring

VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".ts", ".m4v", ".rmvb", ".rm", ".mpg", ".mpeg", ".webm"}
NFO_EXTENSIONS = {".nfo"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

POSTER_NAMES = ["poster", "folder", "cover", "default", "movie", "show"]
FANART_NAMES = ["fanart", "backdrop", "background"]
BANNER_NAMES = ["banner"]
THUMB_NAMES = ["thumb", "landscape"]

# Cap NFO read size — huge files on rclone FUSE would stall forever.
NFO_MAX_BYTES = 2 * 1024 * 1024
NFO_ENCODINGS = ("utf-8", "utf-8-sig", "gbk", "gb18030", "latin-1", "cp1252")

MULTIPART_PATTERNS = [
    re.compile(r"^(.+?)[\s._-]*(?:cd|disc|disk)[\s._-]*(\d+)$", re.IGNORECASE),
    re.compile(r"^(.+?)[\s._-]*(?:part|pt)[\s._-]*(\d+)$", re.IGNORECASE),
]


def get_base_title(filename_stem: str) -> Tuple[str, Optional[int]]:
    """Extract base title and part number from filename.

    Examples:
        "DANDY-553-CD1" -> ("DANDY-553", 1)
        "Movie Part 1" -> ("Movie", 1)
        "Movie" -> ("Movie", None)
    """
    stem = filename_stem.strip()
    for pattern in MULTIPART_PATTERNS:
        m = pattern.match(stem)
        if m:
            base = m.group(1).strip(" -._")
            try:
                return base, int(m.group(2))
            except (ValueError, IndexError):
                pass
    return stem, None


def find_local_images(directory: str, stem: str = "") -> Dict[str, str]:
    result = {"poster": "", "fanart": "", "banner": "", "thumb": ""}
    dirpath = Path(directory)
    # Avoid Path.exists() on rclone FUSE when possible — listdir failure is enough.
    try:
        entries = list(dirpath.iterdir())
    except OSError:
        return result

    all_images = {}
    for f in entries:
        try:
            if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS:
                all_images[f.stem.lower()] = str(f)
        except OSError:
            continue

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

    for name in BANNER_NAMES:
        if name in all_images:
            result["banner"] = all_images[name]
            break

    for name in THUMB_NAMES:
        if name in all_images:
            result["thumb"] = all_images[name]
            break

    return result


def _resolve_local_media_path(nfo_dir: str, raw: str) -> str:
    """Join relative poster/fanart paths without Path.exists() (rclone FUSE hangs)."""
    if not raw or raw.startswith("http"):
        return raw or ""
    # Absolute paths keep as-is; relative join under NFO dir. UI/stream can 404 later.
    p = Path(raw)
    if p.is_absolute():
        return str(p)
    return str(Path(nfo_dir) / raw)


def parse_nfo(nfo_path: str) -> Optional[Dict]:
    """Parse NFO: read bytes once, decode in-memory, no per-encoding reopen."""
    try:
        with open(nfo_path, "rb") as f:
            raw = f.read(NFO_MAX_BYTES + 1)
        if len(raw) > NFO_MAX_BYTES:
            raw = raw[:NFO_MAX_BYTES]
    except OSError:
        return None

    content = None
    for enc in NFO_ENCODINGS:
        try:
            content = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if content is None:
        content = raw.decode("utf-8", errors="replace")

    try:
        root = _xml_fromstring(content)
    except Exception:
        return None

    result: Dict = {}
    nfo_dir = str(Path(nfo_path).parent)

    result["nfo_type"] = root.tag.lower()
    result["title"] = _get_text(root, "title") or _get_text(root, "originaltitle") or ""
    result["original_title"] = _get_text(root, "originaltitle") or ""
    result["plot"] = _get_text(root, "plot") or _get_text(root, "outline") or ""

    year_str = _get_text(root, "year")
    if not year_str:
        premiered = _get_text(root, "premiered") or _get_text(root, "releasedate") or ""
        if len(premiered) >= 4:
            year_str = premiered[:4]
    try:
        result["year"] = int(year_str) if year_str else None
    except (ValueError, TypeError):
        result["year"] = None

    genres = [g.text.strip() for g in root.findall("genre") if g.text]
    result["genre"] = ", ".join(genres)

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

    result["director"] = _get_text(root, "director") or ""

    actors = []
    for actor in root.findall("actor"):
        name_el = actor.find("name")
        if name_el is not None and name_el.text:
            actors.append(name_el.text.strip())
    result["cast_list"] = json.dumps(actors, ensure_ascii=False)

    poster_raw = _get_text(root, "poster") or _get_text(root, "thumb") or ""
    if not poster_raw:
        poster_el = root.find(".//poster")
        if poster_el is not None and poster_el.text:
            poster_raw = poster_el.text.strip()
    result["poster_url"] = _resolve_local_media_path(nfo_dir, poster_raw)

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
    result["fanart_url"] = _resolve_local_media_path(nfo_dir, fanart_raw)

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
