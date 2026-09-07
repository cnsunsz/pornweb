"""Douban best-effort scraper (China VPS friendly; soft-fail if blocked)."""
from __future__ import annotations

import re
from typing import Optional
import httpx

from .base import ScrapeResult, cast_to_json, empty_result

SUGGEST = "https://movie.douban.com/j/subject_suggest"
SUBJECT = "https://movie.douban.com/subject/{sid}/"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


def scrape_douban(
    title: str,
    *,
    cookie: str = "",
    timeout: float = 8.0,
    proxy: Optional[str] = None,
) -> ScrapeResult:
    out = empty_result("douban")
    q = (title or "").strip()
    if not q:
        return out
    headers = {
        "User-Agent": UA,
        "Referer": "https://movie.douban.com/",
        "Accept": "application/json, text/javascript, */*; q=0.01",
    }
    if cookie:
        headers["Cookie"] = cookie
    try:
        with httpx.Client(timeout=timeout, proxy=proxy or None, follow_redirects=True, headers=headers) as client:
            r = client.get(SUGGEST, params={"q": q})
            if r.status_code != 200:
                return out
            try:
                suggestions = r.json()
            except Exception:
                return out
            if not isinstance(suggestions, list) or not suggestions:
                return out
            hit = suggestions[0]
            sid = str(hit.get("id") or "").strip()
            out.title = (hit.get("title") or "").strip()
            out.year = _safe_year(hit.get("year"))
            img = (hit.get("img") or "").strip()
            if img:
                # Prefer larger cover if Douban uses s_ratio / m_ratio thumbnails
                out.poster_url = re.sub(r"/s_ratio_poster/", "/l_ratio_poster/", img)
                out.poster_url = re.sub(r"/m_ratio_poster/", "/l_ratio_poster/", out.poster_url)
            if sid:
                out.external_id = sid
                out.source_url = SUBJECT.format(sid=sid)
                _enrich_subject(client, sid, out)
    except Exception:
        return empty_result("douban") if not out.has_any() else out
    return out


def _enrich_subject(client: httpx.Client, sid: str, out: ScrapeResult) -> None:
    try:
        r = client.get(SUBJECT.format(sid=sid))
        if r.status_code != 200:
            return
        html = r.text or ""
        if not out.plot:
            m = re.search(
                r'property="v:summary"[^>]*>(.*?)</span>',
                html,
                re.S | re.I,
            )
            if m:
                plot = re.sub(r"<[^>]+>", "", m.group(1))
                out.plot = re.sub(r"\s+", " ", plot).strip()
        if out.rating is None:
            m = re.search(r'property="v:average"[^>]*>([0-9.]+)<', html)
            if m:
                try:
                    out.rating = float(m.group(1))
                except ValueError:
                    pass
        if not out.year:
            m = re.search(r'<span class="year">\((\d{4})\)</span>', html)
            if m:
                out.year = _safe_year(m.group(1))
        if not out.director:
            dirs = re.findall(
                r'rel="v:directedBy"[^>]*>([^<]+)<',
                html,
            )
            if dirs:
                out.director = ", ".join(d.strip() for d in dirs if d.strip())
        if not _has_cast(out.cast_list):
            actors = re.findall(r'rel="v:starring"[^>]*>([^<]+)<', html)
            if actors:
                out.cast_list = cast_to_json([a.strip() for a in actors])
        if not out.genre:
            genres = re.findall(r'<span property="v:genre">([^<]+)</span>', html)
            if genres:
                out.genre = ", ".join(g.strip() for g in genres if g.strip())
        if not out.original_title:
            m = re.search(r'<span class="pl">又名:</span>\s*([^<]+)<br/?\s*>', html)
            if m:
                out.original_title = m.group(1).strip().split("/")[0].strip()
        if not out.fanart_url:
            # Douban subject pages rarely expose a separate fanart; reuse poster.
            if out.poster_url:
                out.fanart_url = out.poster_url
    except Exception:
        return


def _has_cast(cast_list: str) -> bool:
    return bool(cast_list and cast_list.strip() not in ("[]", "", "null"))


def _safe_year(val) -> Optional[int]:
    try:
        s = str(val or "").strip()
        if len(s) >= 4 and s[:4].isdigit():
            return int(s[:4])
    except Exception:
        pass
    return None
