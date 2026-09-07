"""Resolve actor profile photos online (Emby/Jellyfin-style people metadata).

Order: TMDB person → Douban celebrity suggest. Never fabricate placeholders.
JavDB skipped when unreachable (common on CN AWS).
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from urllib.parse import quote

import httpx
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.actor_photo import ActorPhoto

log = logging.getLogger("pornweb.actor_photo")

TMDB_BASES = ("https://api.tmdb.org/3", "https://api.themoviedb.org/3")
IMG_BASE = "https://image.tmdb.org/t/p/w185"
DOUBAN_SUGGEST = "https://movie.douban.com/j/subject_suggest"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
MISS_TTL = timedelta(days=3)
HIT_TTL = timedelta(days=30)


def name_key(name: str) -> str:
    return (name or "").strip().lower()


def _tmdb_key() -> str:
    return (getattr(settings, "TMDB_API_KEY", None) or "").strip()


def _as_bool(val, default: bool = False) -> bool:
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    if s in ("1", "true", "yes", "on"):
        return True
    if s in ("0", "false", "no", "off", ""):
        return False
    return default


def _tmdb_enabled() -> bool:
    return _as_bool(getattr(settings, "SCRAPER_TMDB_ENABLED", False)) and bool(_tmdb_key())


def _douban_enabled() -> bool:
    # Prefer explicit flag; if internet scrapers on, allow Douban for people even when movie douban off
    if _as_bool(getattr(settings, "SCRAPER_DOUBAN_ENABLED", False)):
        return True
    # People photos: Douban celebrity is CN-friendly; enable when internet scraping is on
    return _as_bool(getattr(settings, "SCRAPER_INTERNET_ENABLED", True), True)


def _fresh(row: ActorPhoto) -> bool:
    if not row or not row.updated_at:
        return False
    age = datetime.utcnow() - row.updated_at
    if row.status == "ok":
        return age < HIT_TTL
    return age < MISS_TTL


def get_cached(db: Session, name: str) -> Optional[ActorPhoto]:
    key = name_key(name)
    if not key:
        return None
    return db.query(ActorPhoto).filter(ActorPhoto.name_key == key).one_or_none()


def public_photo_path(name: str) -> str:
    return f"/api/actors/photo?name={quote(name, safe='')}"


def _upgrade_douban_img(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    u = re.sub(r"/s_ratio_poster/", "/l_ratio_poster/", u)
    u = re.sub(r"/m_ratio_poster/", "/l_ratio_poster/", u)
    u = re.sub(r"/personage/m/", "/personage/l/", u)
    u = re.sub(r"/celebrity/m/", "/celebrity/l/", u)
    u = re.sub(r"/personage/s/", "/personage/l/", u)
    return u


async def resolve_remote_url(db: Session, name: str, *, force: bool = False) -> Tuple[str, str]:
    """Return (remote_url, source). Empty means no photo — do not invent one."""
    n = (name or "").strip()
    if not n:
        return "", ""
    row = get_cached(db, n)
    if row and _fresh(row) and not force:
        if row.status == "ok" and (row.remote_url or "").strip():
            return row.remote_url.strip(), row.source or ""
        return "", ""

    remote, source, ext = "", "", ""
    # Emby-like provider order: TMDB then Douban celebrity
    if _tmdb_enabled():
        remote, source, ext = await _fetch_tmdb_person(n)
    if not remote and _douban_enabled():
        remote, source, ext = await _fetch_douban_celebrity(n)

    key = name_key(n)
    if row is None:
        row = ActorPhoto(name_key=key, name=n)
        db.add(row)
    row.name = n
    if remote:
        row.status = "ok"
        row.remote_url = remote
        row.source = source
        row.external_id = ext
    else:
        row.status = "miss"
        row.remote_url = ""
        row.source = source or ""
        row.external_id = ""
    row.updated_at = datetime.utcnow()
    try:
        db.commit()
    except Exception:
        db.rollback()
        log.debug("actor photo cache commit failed for %s", n)
    return remote, source


async def scrape_many(db: Session, names: List[str], *, force: bool = False, limit: int = 200) -> dict:
    """Batch resolve like Emby people library refresh. Soft-fail per name."""
    seen = set()
    uniq = []
    for n in names:
        n = (n or "").strip()
        if not n:
            continue
        k = name_key(n)
        if k in seen:
            continue
        seen.add(k)
        uniq.append(n)
        if len(uniq) >= max(1, min(int(limit), 500)):
            break
    ok = miss = 0
    for n in uniq:
        url, _ = await resolve_remote_url(db, n, force=force)
        if url:
            ok += 1
        else:
            miss += 1
    return {"tried": len(uniq), "ok": ok, "miss": miss}


async def _fetch_tmdb_person(name: str) -> Tuple[str, str, str]:
    key = _tmdb_key()
    if not key:
        return "", "", ""
    params = {
        "api_key": key,
        "query": name,
        "include_adult": "true",
        "language": getattr(settings, "SCRAPER_METADATA_LANGUAGE", None) or "zh-CN",
    }
    headers = {"User-Agent": "PornWeb/2.1.6"}
    last_exc = None
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            data = None
            for base in TMDB_BASES:
                try:
                    r = await client.get(f"{base}/search/person", params=params, headers=headers)
                    if r.status_code == 200:
                        data = r.json() or {}
                        break
                except Exception as e:
                    last_exc = e
                    continue
            if not data:
                if last_exc:
                    log.debug("tmdb person search fail: %s", last_exc)
                return "", "", ""
            results = data.get("results") or []
            if not results:
                return "", "", ""
            hit = None
            nl = name.strip().lower()
            for r in results:
                nm = (r.get("name") or "").strip().lower()
                if nm == nl and r.get("profile_path"):
                    hit = r
                    break
            if hit is None:
                for r in results:
                    if r.get("profile_path"):
                        hit = r
                        break
            if not hit:
                return "", "", ""
            path = hit.get("profile_path") or ""
            if not path:
                return "", "", ""
            return f"{IMG_BASE}{path}", "tmdb", str(hit.get("id") or "")
    except Exception as e:
        log.debug("tmdb person search error: %s", e)
        return "", "", ""


async def _fetch_douban_celebrity(name: str) -> Tuple[str, str, str]:
    """Douban subject_suggest returns type=celebrity with img — works on CN VPS."""
    q = (name or "").strip()
    if not q:
        return "", "", ""
    headers = {
        "User-Agent": UA,
        "Referer": "https://movie.douban.com/",
        "Accept": "application/json, text/javascript, */*; q=0.01",
    }
    cookie = (getattr(settings, "SCRAPER_DOUBAN_COOKIE", None) or "").strip()
    if cookie:
        headers["Cookie"] = cookie
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=headers) as client:
            r = await client.get(DOUBAN_SUGGEST, params={"q": q})
            if r.status_code != 200:
                return "", "", ""
            try:
                suggestions = r.json()
            except Exception:
                return "", "", ""
            if not isinstance(suggestions, list) or not suggestions:
                return "", "", ""
            nl = q.lower()
            hit = None
            for s in suggestions:
                if (s.get("type") or "").lower() != "celebrity":
                    continue
                title = (s.get("title") or "").strip()
                img = (s.get("img") or "").strip()
                if not img:
                    continue
                if title.lower() == nl:
                    hit = s
                    break
                if hit is None:
                    hit = s
            if not hit:
                # Do NOT fall back to movie posters as people photos (would be 乱加)
                return "", "", ""
            img = _upgrade_douban_img(hit.get("img") or "")
            if not img:
                return "", "", ""
            return img, "douban", str(hit.get("id") or "")
    except Exception as e:
        log.debug("douban celebrity search error: %s", e)
        return "", "", ""
