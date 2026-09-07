"""Shared scraper types and helpers."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


# Adult / western product codes: SSIS-001, DANDY-553, ABC-12345, FC2-PPV-1234567
CODE_RE = re.compile(
    r"(?i)\b(?:([A-Z]{2,10})[-_ ]?(\d{2,5})|(FC2[-_]?PPV[-_]?\d{5,10})|(HEYZO[-_]?\d{4,6}))\b"
)


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


def extract_product_code(text: str) -> Optional[str]:
    """Best-effort adult product code from filename/title."""
    if not text:
        return None
    # Prefer stem without extension
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
    return f"{prefix.upper()}-{num}"


def search_query_from_item(
    title: str = "",
    filename: str = "",
    file_path: str = "",
) -> Dict[str, str]:
    """Build query hints for scrapers."""
    code = (
        extract_product_code(filename)
        or extract_product_code(title)
        or extract_product_code(file_path)
    )
    # Strip common junk from title for movie search
    q_title = (title or "").strip() or ""
    if not q_title and filename:
        q_title = re.sub(r"\.[a-z0-9]{2,4}$", "", filename, flags=re.I)
    if code and q_title.upper().startswith(code.split("-")[0]):
        # Prefer code as primary for adult scrapers; keep title for TMDB/Douban
        pass
    return {"title": q_title.strip(), "code": code or "", "filename": filename or ""}


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
    # Title alone (often just filename stem) without plot/poster/genre/year → thin
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
        if force or empty:
            if cur == val:
                continue
            setattr(item, key, val)
            changed.append(key)
    return changed


def empty_result(provider: str) -> ScrapeResult:
    return ScrapeResult(provider=provider)
