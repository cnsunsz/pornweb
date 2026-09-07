"""TMDB official API scraper (requires TMDB_API_KEY)."""
from __future__ import annotations

from typing import Optional
import httpx

from .base import ScrapeResult, cast_to_json, empty_result

# api.themoviedb.org is often unreachable on AWS China / CN networks;
# api.tmdb.org is the same API and usually works there.
TMDB_API = "https://api.tmdb.org/3"
TMDB_API_FALLBACKS = (
    "https://api.tmdb.org/3",
    "https://api.themoviedb.org/3",
)
IMG_BASE = "https://image.tmdb.org/t/p"


def _tmdb_bases(primary: Optional[str] = None):
    seen = set()
    for b in ((primary,) if primary else ()) + TMDB_API_FALLBACKS:
        if not b or b in seen:
            continue
        seen.add(b)
        yield b.rstrip("/")


def _tmdb_get(client: httpx.Client, path: str, params: dict):
    """Try CN-reachable api.tmdb.org first, then official host."""
    last_exc = None
    for base in _tmdb_bases(TMDB_API):
        try:
            r = client.get(f"{base}{path}", params=params)
            if r.status_code == 200 or r.status_code < 500:
                return r
        except Exception as e:
            last_exc = e
            continue
    if last_exc:
        raise last_exc
    raise RuntimeError("TMDB unreachable")


def scrape_tmdb(
    title: str,
    *,
    api_key: str,
    year: Optional[int] = None,
    timeout: float = 8.0,
    proxy: Optional[str] = None,
    media_type: str = "movie",
    language: str = "zh-CN",
) -> ScrapeResult:
    out = empty_result("tmdb")
    if not api_key or not (title or "").strip():
        return out
    q = title.strip()
    lang = (language or "zh-CN").strip() or "zh-CN"
    try:
        with httpx.Client(timeout=timeout, proxy=proxy or None, follow_redirects=True) as client:
            kind = "tv" if media_type == "tvshow" else "movie"
            params = {"api_key": api_key, "query": q, "include_adult": "true", "language": lang}
            if year and kind == "movie":
                params["year"] = str(year)
            r = _tmdb_get(client, f"/search/{kind}", params)
            if r.status_code != 200:
                return out
            results = (r.json() or {}).get("results") or []
            if not results:
                # fallback English / no language
                params.pop("language", None)
                r = _tmdb_get(client, f"/search/{kind}", params)
                if r.status_code != 200:
                    return out
                results = (r.json() or {}).get("results") or []
            if not results:
                return out
            hit = results[0]
            tid = hit.get("id")
            detail = {}
            credits = {}
            if tid:
                dr = _tmdb_get(
                    client,
                    f"/{kind}/{tid}",
                    {"api_key": api_key, "language": lang},
                )
                if dr.status_code == 200:
                    detail = dr.json() or {}
                cr = _tmdb_get(
                    client,
                    f"/{kind}/{tid}/credits",
                    {"api_key": api_key},
                )
                if cr.status_code == 200:
                    credits = cr.json() or {}

            name = (
                detail.get("title")
                or detail.get("name")
                or hit.get("title")
                or hit.get("name")
                or ""
            )
            orig = (
                detail.get("original_title")
                or detail.get("original_name")
                or hit.get("original_title")
                or hit.get("original_name")
                or ""
            )
            overview = detail.get("overview") or hit.get("overview") or ""
            date = (
                detail.get("release_date")
                or detail.get("first_air_date")
                or hit.get("release_date")
                or hit.get("first_air_date")
                or ""
            )
            y = None
            if date and len(date) >= 4:
                try:
                    y = int(date[:4])
                except ValueError:
                    y = None
            genres = ", ".join(
                g.get("name", "").strip()
                for g in (detail.get("genres") or [])
                if g.get("name")
            )
            rating = detail.get("vote_average")
            if rating is None:
                rating = hit.get("vote_average")
            try:
                rating_f = float(rating) if rating is not None else None
            except (TypeError, ValueError):
                rating_f = None

            cast_names = []
            for c in (credits.get("cast") or [])[:12]:
                n = (c.get("name") or "").strip()
                if n:
                    cast_names.append(n)
            directors = []
            for c in credits.get("crew") or []:
                if (c.get("job") or "").lower() == "director":
                    n = (c.get("name") or "").strip()
                    if n:
                        directors.append(n)

            poster_path = detail.get("poster_path") or hit.get("poster_path") or ""
            backdrop = detail.get("backdrop_path") or hit.get("backdrop_path") or ""

            out.title = name
            out.original_title = orig
            out.plot = overview
            out.year = y
            out.genre = genres
            out.rating = rating_f
            out.director = ", ".join(directors)
            out.cast_list = cast_to_json(cast_names)
            if poster_path:
                out.poster_url = f"{IMG_BASE}/w500{poster_path}"
            if backdrop:
                out.fanart_url = f"{IMG_BASE}/w1280{backdrop}"
            out.external_id = str(tid or "")
            out.source_url = f"https://www.themoviedb.org/{kind}/{tid}" if tid else ""
    except Exception:
        return empty_result("tmdb")
    return out
