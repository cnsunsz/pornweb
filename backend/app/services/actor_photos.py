"""Resolve actor profile photos from online sources (TMDB). Soft-fail; never fabricate."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple
from urllib.parse import quote

import httpx
from sqlalchemy.orm import Session

from ..core.config import settings
from ..models.actor_photo import ActorPhoto

log = logging.getLogger("pornweb.actor_photo")

TMDB_BASES = ("https://api.tmdb.org/3", "https://api.themoviedb.org/3")
IMG_BASE = "https://image.tmdb.org/t/p/w185"
# Re-check misses after this; hits kept longer
MISS_TTL = timedelta(days=3)
HIT_TTL = timedelta(days=30)


def name_key(name: str) -> str:
    return (name or "").strip().lower()


def _tmdb_key() -> str:
    return (getattr(settings, "TMDB_API_KEY", None) or "").strip()


def _tmdb_enabled() -> bool:
    return bool(getattr(settings, "SCRAPER_TMDB_ENABLED", False)) and bool(_tmdb_key())


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
    """Stable same-origin path; 404 means no online photo (UI must stay empty)."""
    return f"/api/actors/photo?name={quote(name, safe='')}"


async def resolve_remote_url(db: Session, name: str, *, force: bool = False) -> Tuple[str, str]:
    """Return (remote_url, source). Empty url means no photo — do not invent one."""
    n = (name or "").strip()
    if not n:
        return "", ""
    row = get_cached(db, n)
    if row and _fresh(row) and not force:
        if row.status == "ok" and (row.remote_url or "").strip():
            return row.remote_url.strip(), row.source or ""
        return "", ""

    remote, source, ext = "", "", ""
    if _tmdb_enabled():
        remote, source, ext = await _fetch_tmdb_person(n)

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
    headers = {"User-Agent": "PornWeb/2.1.5"}
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
            # Prefer exact name match (case-insensitive), else first with a profile
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
            if hit is None:
                return "", "", ""
            path = hit.get("profile_path") or ""
            if not path:
                return "", "", ""
            return f"{IMG_BASE}{path}", "tmdb", str(hit.get("id") or "")
    except Exception as e:
        log.debug("tmdb person search error: %s", e)
        return "", "", ""
