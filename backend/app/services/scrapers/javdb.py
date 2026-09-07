"""JavDB best-effort scraper for adult product codes (soft-fail if blocked)."""
from __future__ import annotations

import re
from typing import Optional
import httpx

from .base import ScrapeResult, cast_to_json, empty_result, extract_product_code

SEARCH = "https://javdb.com/search"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


def scrape_javdb(
    title: str = "",
    filename: str = "",
    code: str = "",
    *,
    cookie: str = "",
    timeout: float = 8.0,
    proxy: Optional[str] = None,
) -> ScrapeResult:
    out = empty_result("javdb")
    code = (code or extract_product_code(filename) or extract_product_code(title) or "").strip().upper()
    if not code:
        return out
    headers = {
        "User-Agent": UA,
        "Referer": "https://javdb.com/",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,ja;q=0.7",
    }
    if cookie:
        headers["Cookie"] = cookie
    try:
        with httpx.Client(timeout=timeout, proxy=proxy or None, follow_redirects=True, headers=headers) as client:
            r = client.get(SEARCH, params={"q": code, "f": "all"})
            if r.status_code != 200:
                return out
            html = r.text or ""
            # Cloudflare / login walls
            if "cf-browser-verification" in html.lower() or "just a moment" in html.lower():
                return out
            href, cover = _first_result(html, code)
            if not href:
                return out
            if cover:
                out.poster_url = cover
            detail_url = href if href.startswith("http") else f"https://javdb.com{href}"
            out.source_url = detail_url
            dr = client.get(detail_url)
            if dr.status_code != 200:
                # Still return whatever we have from search card
                out.title = code
                out.original_title = code
                return out
            _parse_detail(dr.text or "", out, code)
    except Exception:
        return empty_result("javdb") if not out.has_any() else out
    return out


def _first_result(html: str, code: str) -> tuple:
    """Return (href, cover_url) for best matching search card."""
    # movie-list items: <a href="/v/XXXX" ...> ... <img src="..."
    cards = re.findall(
        r'<a[^>]+href="(/v/[^"]+)"[^>]*>[\s\S]*?</a>',
        html,
        re.I,
    )
    # Fallback simpler: first /v/ link near the code
    if not cards:
        m = re.search(r'href="(/v/[^"]+)"', html, re.I)
        if not m:
            return "", ""
        href = m.group(1)
        img = ""
        im = re.search(r'<img[^>]+(?:src|data-src)="(https?://[^"]+)"', html, re.I)
        if im:
            img = im.group(1)
        return href, img

    code_compact = code.replace("-", "").upper()
    best_href = ""
    best_cover = ""
    # Re-scan with surrounding context for uid + cover
    for m in re.finditer(
        r'<a[^>]+href="(/v/[^"]+)"[^>]*>([\s\S]*?)</a>',
        html,
        re.I,
    ):
        href, body = m.group(1), m.group(2)
        uid_m = re.search(r'class="uid"[^>]*>([^<]+)<', body, re.I)
        uid = (uid_m.group(1) if uid_m else "").strip().upper().replace(" ", "")
        img_m = re.search(r'(?:src|data-src)="(https?://[^"]+)"', body, re.I)
        cover = img_m.group(1) if img_m else ""
        if uid and (uid == code or uid.replace("-", "") == code_compact):
            return href, cover
        if not best_href:
            best_href, best_cover = href, cover
    return best_href, best_cover


def _parse_detail(html: str, out: ScrapeResult, code: str) -> None:
    title = ""
    m = re.search(r"<h2[^>]*class=\"[^\"]*title[^\"]*\"[^>]*>\s*<strong>([^<]+)</strong>", html, re.I)
    if m:
        title = m.group(1).strip()
    if not title:
        m = re.search(r"<title>([^<]+)</title>", html, re.I)
        if m:
            title = m.group(1).split("|")[0].strip()
    out.title = title or code
    out.original_title = code

    # Cover / fanart
    img = re.search(r'class="[^"]*video-cover[^"]*"[^>]+src="(https?://[^"]+)"', html, re.I)
    if not img:
        img = re.search(r'<img[^>]+class="[^"]*cover[^"]*"[^>]+src="(https?://[^"]+)"', html, re.I)
    if img:
        out.poster_url = img.group(1)
        out.fanart_url = out.poster_url

    # Panel meta rows: <strong>類型:</strong> ... <strong>演員:</strong>
    def _panel(label: str) -> str:
        pat = rf"<strong>\s*{re.escape(label)}\s*:?\s*</strong>\s*((?:(?!</div>).)*)"
        mm = re.search(pat, html, re.I | re.S)
        if not mm:
            return ""
        chunk = mm.group(1)
        texts = re.findall(r"<a[^>]*>([^<]+)</a>", chunk)
        if texts:
            return ", ".join(t.strip() for t in texts if t.strip())
        plain = re.sub(r"<[^>]+>", " ", chunk)
        return re.sub(r"\s+", " ", plain).strip()

    genres = _panel("類別") or _panel("类别") or _panel("Tags") or _panel("類型") or _panel("类型")
    if genres:
        out.genre = genres
    actors = _panel("演員") or _panel("演员") or _panel("Actor") or _panel("Actors")
    if actors:
        names = [a.strip() for a in re.split(r"[,，、/]", actors) if a.strip()]
        # Prefer anchor-parsed list
        if "," in actors and not names:
            names = [actors]
        # Re-extract anchors for actors panel more carefully
        am = re.search(
            r"<strong>\s*(?:演員|演员|Actors?)\s*:?\s*</strong>\s*((?:(?!</div>).)*)",
            html,
            re.I | re.S,
        )
        if am:
            names = [t.strip() for t in re.findall(r"<a[^>]*>([^<]+)</a>", am.group(1)) if t.strip()] or names
        out.cast_list = cast_to_json(names)

    director = _panel("導演") or _panel("导演") or _panel("Director")
    if director:
        out.director = director.split(",")[0].strip()

    date_s = _panel("日期") or _panel("Released") or _panel("上市")
    if date_s:
        ym = re.search(r"(20\d{2}|19\d{2})", date_s)
        if ym:
            try:
                out.year = int(ym.group(1))
            except ValueError:
                pass

    # Score e.g. 4.2分
    sm = re.search(r"score-stars[\s\S]*?(\d+(?:\.\d+)?)\s*分", html, re.I)
    if sm:
        try:
            out.rating = float(sm.group(1))
        except ValueError:
            pass

    # Plot / description
    pm = re.search(
        r"<strong>\s*(?:簡介|简介|Description)\s*:?\s*</strong>\s*((?:(?!</div>).)*)",
        html,
        re.I | re.S,
    )
    if pm:
        plot = re.sub(r"<[^>]+>", " ", pm.group(1))
        out.plot = re.sub(r"\s+", " ", plot).strip()
