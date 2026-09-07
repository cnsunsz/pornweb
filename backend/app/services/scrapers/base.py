"""Shared scraper types and helpers."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


# Adult product codes: SSIS-001, DANDY-553, FC2-PPV-1234567 — not scene tags like H265/Identity.2026
CODE_RE = re.compile(
    r"(?i)\b(?:([A-Z]{2,10})[-_ ]?(\d{2,5})|(FC2[-_]?PPV[-_]?\d{5,10})|(HEYZO[-_]?\d{4,6}))\b"
)

# Scene / encode tokens that mean this is a western release name, not a JAV code
SCENE_TAG_RE = re.compile(
    r"(?i)\b("
    r"2160p|1080p|720p|480p|576p|4320p|"
    r"WEB-?DL|WEBRip|BluRay|Blu-?Ray|REMUX|HDTV|DVDRip|BDRip|"
    r"x264|x265|h\.?264|h\.?265|HEVC|AVC|AV1|XviD|"
    r"HDR10?\+?|Dolby[\s.]?Vision|\bDV\b|HLG|"
    r"DTS(?:-?HD)?(?:\.?MA)?|TrueHD|Atmos|AAC|AC3|EAC3|FLAC|PCM|"
    r"\d(?:\.\d)?fps|60fps|30fps|23\.?976|"
    r"10bit|8bit|Hi10P|"
    r"PROPER|REPACK|INTERNAL|EXTENDED|UNCUT|DIRECTORS?\.?CUT|"
    r"DreamHD|RARBG|YTS|YIFY|SPANiSH|FRENCH|GERMAN|MULTI"
    r")\b"
)

# Codecs / formats that must never be treated as adult studio codes
CODE_BLOCKLIST = {
    "HEVC", "AVC", "HDR", "HDR10", "AAC", "DTS", "AC3", "EAC3", "FLAC", "PCM",
    "WEB", "DL", "BD", "UHD", "FHD", "HD", "SD", "MP4", "MKV", "AVI", "MOV",
    "H264", "H265", "X264", "X265", "AV1", "VP9", "IMAX", "REMUX", "WEBDL",
}


@dataclass
class ScrapeResult:
    """NFO-like normalized metadata from a cloud provider."""

    provider: str = ""
    title: str = ""
    original_title: str = ""
    plot: str = ""
    year: Optional[int] = None
    genre: str = ""
    rating: Optional[float] = None
    director: str = ""
    cast_list: str = "[]"  # JSON array string
    poster_url: str = ""
    fanart_url: str = ""
    external_id: str = ""
    source_url: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def has_any(self) -> bool:
        return bool(
            (self.title or "").strip()
            or (self.plot or "").strip()
            or (self.poster_url or "").strip()
            or (self.genre or "").strip()
            or self.year is not None
            or self.rating is not None
            or (self.director or "").strip()
            or _cast_nonempty(self.cast_list)
        )


def _cast_nonempty(cast_list: str) -> bool:
    try:
        data = json.loads(cast_list or "[]")
        return isinstance(data, list) and any(str(x).strip() for x in data)
    except Exception:
        return bool((cast_list or "").strip() and cast_list.strip() not in ("[]", "null"))


def cast_to_json(names: List[str]) -> str:
    cleaned = [n.strip() for n in names if n and str(n).strip()]
    return json.dumps(cleaned, ensure_ascii=False)


def looks_like_scene_release(text: str) -> bool:
    """True for Scene/P2P names like Title.2024.2160p.WEB-DL.H265-Group."""
    if not text:
        return False
    return bool(SCENE_TAG_RE.search(text.replace("_", ".")))


def clean_release_title(text: str) -> Dict[str, Any]:
    """
    Emby/Jellyfin-style cleanup: dots→spaces, strip quality/codec/group, pull year.
    Example: Game.of.Identity.2026.2160p.WEB-DL.H265...-DreamHD → Game of Identity (2026)
    """
    if not text:
        return {"title": "", "year": None}
    stem = re.sub(r"\.[a-z0-9]{2,4}$", "", text.strip(), flags=re.I)
    # Release group after last hyphen if it looks like -GroupName
    stem = re.sub(r"[-_.]([A-Za-z0-9]{2,20})$", "", stem)
    # Normalize separators
    s = stem.replace("_", " ").replace(".", " ")
    s = re.sub(r"\s+", " ", s).strip()
    year = None
    ym = re.search(r"\b(19\d{2}|20\d{2})\b", s)
    if ym:
        try:
            year = int(ym.group(1))
        except ValueError:
            year = None
    # Cut at first scene tag
    mtag = SCENE_TAG_RE.search(s)
    if mtag:
        s = s[: mtag.start()].strip(" -_")
    # Also cut trailing year-only leftovers handled below; remove year from title body
    if year is not None:
        s = re.sub(rf"\b{year}\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" -_")
    # Title Case lightly if all lowercase/dots already spaced
    return {"title": s, "year": year}


def extract_product_code(text: str) -> Optional[str]:
    """Best-effort adult product code from filename/title. Skips scene releases."""
    if not text:
        return None
    if looks_like_scene_release(text):
        return None
    stem = re.sub(r"\.[a-z0-9]{2,4}$", "", text, flags=re.I)
    m = CODE_RE.search(stem.replace(".", " ").replace("_", "-"))
    if not m:
        return None
    if m.group(3):
        return re.sub(r"[-_]+", "-", m.group(3).upper())
    if m.group(4):
        return re.sub(r"[-_]+", "-", m.group(4).upper())
    prefix, num = m.group(1), m.group(2)
    if not prefix or not num:
        return None
    if prefix.upper() in CODE_BLOCKLIST:
        return None
    # Avoid Title.2024 style false positives when not a scene file but word+year
    if len(prefix) >= 5 and prefix.isalpha() and len(num) == 4 and num.startswith("19") or (
        len(prefix) >= 5 and prefix.isalpha() and len(num) == 4 and num.startswith("20")
    ):
        return None
    return f"{prefix.upper()}-{num}"



_CJK_RUN = re.compile(r"[\u4e00-\u9fff·：:]{2,}")
_CJK_NOISE = {
    "国语配音", "中文字幕", "粤语配音", "简体中字", "繁体中字", "中字", "内封",
    "帧率版本", "高清", "蓝光", "未删减", "剧场版",
}


def extract_cjk_title(*texts: str) -> str:
    """Pull a Chinese title from folder/filename (common CN release layout).

    Example folder:
    天才游戏[60帧率版本][国语配音+中文字幕].Game.of.Identity.2026...
    → 天才游戏
    """
    for text in texts:
        if not text:
            continue
        name = Path(str(text)).name
        # Leading CJK before [ or .English
        m = re.match(r"^([\u4e00-\u9fff·：:]{2,})", name)
        if m:
            return m.group(1)
        # First non-noise CJK run
        for m in _CJK_RUN.finditer(name):
            s = m.group(0)
            if s in _CJK_NOISE or any(n in s for n in ("配音", "字幕", "帧率")):
                continue
            if len(s) >= 2:
                return s
    return ""


def search_query_from_item(
    title: str = "",
    filename: str = "",
    file_path: str = "",
) -> Dict[str, Any]:
    """Build query hints for scrapers (cleaned title + year + optional JAV code)."""
    code = (
        extract_product_code(filename)
        or extract_product_code(title)
        or extract_product_code(file_path)
    )
    raw = (filename or "").strip() or (title or "").strip() or (file_path or "").strip()
    cleaned = clean_release_title(raw)
    # If DB title is already human (few dots), prefer cleaning that too
    if title and title.count(".") < 3 and not looks_like_scene_release(title):
        t2 = clean_release_title(title)
        if t2["title"]:
            # Prefer longer meaningful cleaned title from filename if title is still dump
            if looks_like_scene_release(title) or title.count(".") >= 3:
                pass
            elif len(t2["title"]) >= 2:
                cleaned = t2 if not cleaned["title"] else cleaned
                if not cleaned["year"]:
                    cleaned["year"] = t2["year"]
    q_title = cleaned["title"] or (title or "").strip()
    if not q_title and filename:
        q_title = clean_release_title(filename)["title"]
    zh = extract_cjk_title(file_path, filename, title)
    # Prefer Chinese folder title as primary search when present (Douban-friendly)
    primary = zh or q_title.strip()
    return {
        "title": primary.strip(),
        "en_title": q_title.strip(),
        "zh_title": zh,
        "code": code or "",
        "filename": filename or "",
        "year": cleaned.get("year"),
    }


META_FIELDS = (
    "title",
    "original_title",
    "plot",
    "year",
    "genre",
    "rating",
    "director",
    "cast_list",
    "poster_url",
    "fanart_url",
)


def is_meta_thin(item: Any) -> bool:
    """True when local metadata is missing/incomplete enough to try cloud."""
    title = (getattr(item, "title", None) or "").strip()
    plot = (getattr(item, "plot", None) or "").strip()
    poster = (getattr(item, "poster_url", None) or "").strip()
    genre = (getattr(item, "genre", None) or "").strip()
    year = getattr(item, "year", None)
    if not title:
        return True
    # Scene-style title counts as thin even if non-empty
    if looks_like_scene_release(title) or title.count(".") >= 3:
        return True
    richness = sum(
        [
            1 if plot else 0,
            1 if poster else 0,
            1 if genre else 0,
            1 if year else 0,
            1 if (getattr(item, "director", None) or "").strip() else 0,
            1 if _cast_nonempty(getattr(item, "cast_list", "") or "") else 0,
        ]
    )
    return richness < 2


def merge_meta(item: Any, data: Dict[str, Any], *, force: bool = False) -> List[str]:
    """Apply scraped fields onto a MediaItem. Returns list of changed field names."""
    changed: List[str] = []
    for key in META_FIELDS:
        if key not in data:
            continue
        val = data.get(key)
        if val is None:
            continue
        if isinstance(val, str) and not val.strip():
            continue
        if key == "cast_list":
            if not _cast_nonempty(str(val)) and not force:
                continue
        cur = getattr(item, key, None)
        empty = cur is None or (isinstance(cur, str) and not str(cur).strip())
        if key == "cast_list":
            empty = empty or not _cast_nonempty(str(cur or ""))
        # Overwrite scene dump titles when we have a cleaned cloud title
        if key == "title" and cur and looks_like_scene_release(str(cur)):
            empty = True
        if force or empty:
            if cur == val:
                continue
            setattr(item, key, val)
            changed.append(key)
    return changed


def empty_result(provider: str) -> ScrapeResult:
    return ScrapeResult(provider=provider)
