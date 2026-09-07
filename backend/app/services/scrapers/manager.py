"""Scraper orchestration: order, enable flags, soft-fail, timeouts."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Sequence

from ...core.config import settings
from .base import (
    ScrapeResult,
    is_meta_thin,
    merge_meta,
    search_query_from_item,
)
from .douban import scrape_douban
from .javdb import scrape_javdb
from .tmdb import scrape_tmdb

log = logging.getLogger("pornweb.scrapers")

PROVIDER_NAMES = ("tmdb", "douban", "javdb")


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


def get_scraper_config() -> Dict[str, Any]:
    """Live scraper config from settings (env + hot-applied PUT)."""
    order_raw = getattr(settings, "SCRAPER_ORDER", None) or "nfo,tmdb,douban,javdb"
    parts = [p.strip().lower() for p in str(order_raw).split(",") if p.strip()]
    # Keep only cloud providers for scrape order (nfo is handled by scanner)
    cloud_order = [p for p in parts if p in PROVIDER_NAMES]
    if not cloud_order:
        cloud_order = list(PROVIDER_NAMES)
    timeout = getattr(settings, "SCRAPER_TIMEOUT_SECONDS", 8.0)
    try:
        timeout_f = float(timeout)
    except (TypeError, ValueError):
        timeout_f = 8.0
    timeout_f = max(2.0, min(30.0, timeout_f))
    return {
        "prefer_local": _as_bool(getattr(settings, "SCRAPER_PREFER_LOCAL", True), True),
        "internet_enabled": _as_bool(getattr(settings, "SCRAPER_INTERNET_ENABLED", True), True),
        "metadata_language": (
            getattr(settings, "SCRAPER_METADATA_LANGUAGE", None) or "zh-CN"
        ).strip()
        or "zh-CN",
        "save_artwork": _as_bool(getattr(settings, "SCRAPER_SAVE_ARTWORK", False), False),
        "douban_enabled": _as_bool(getattr(settings, "SCRAPER_DOUBAN_ENABLED", False)),
        "tmdb_enabled": _as_bool(getattr(settings, "SCRAPER_TMDB_ENABLED", False)),
        "javdb_enabled": _as_bool(getattr(settings, "SCRAPER_JAVDB_ENABLED", False)),
        "tmdb_api_key": (getattr(settings, "TMDB_API_KEY", None) or "").strip(),
        "douban_cookie": (getattr(settings, "SCRAPER_DOUBAN_COOKIE", None) or "").strip(),
        "javdb_cookie": (getattr(settings, "SCRAPER_JAVDB_COOKIE", None) or "").strip(),
        "proxy": (getattr(settings, "SCRAPER_PROXY", None) or "").strip(),
        "order": cloud_order,
        "order_raw": ",".join(parts) if parts else "nfo,tmdb,douban,javdb",
        "timeout": timeout_f,
    }


def any_scraper_enabled(cfg: Optional[Dict[str, Any]] = None) -> bool:
    cfg = cfg or get_scraper_config()
    if not cfg.get("internet_enabled", True):
        return False
    if cfg["tmdb_enabled"] and cfg["tmdb_api_key"]:
        return True
    if cfg["douban_enabled"] or cfg["javdb_enabled"]:
        return True
    return False


def _run_one(
    name: str,
    *,
    title: str,
    filename: str,
    code: str,
    year: Optional[int],
    category: str,
    cfg: Dict[str, Any],
) -> ScrapeResult:
    timeout = cfg["timeout"]
    proxy = cfg["proxy"] or None
    try:
        if name == "tmdb":
            if not cfg["tmdb_enabled"] or not cfg["tmdb_api_key"]:
                return ScrapeResult(provider="tmdb")
            return scrape_tmdb(
                title or code,
                api_key=cfg["tmdb_api_key"],
                year=year,
                timeout=timeout,
                proxy=proxy,
                media_type=category or "movie",
                language=cfg.get("metadata_language") or "zh-CN",
            )
        if name == "douban":
            if not cfg["douban_enabled"]:
                return ScrapeResult(provider="douban")
            # Prefer Chinese folder title; fall back to English cleaned release name.
            alts = []
            for a in (cfg.get("_alt_titles") or []):
                if a and a != (title or code):
                    alts.append(a)
            return scrape_douban(
                title or code,
                alt_titles=alts,
                year=year,
                cookie=cfg["douban_cookie"],
                timeout=timeout,
                proxy=proxy,
            )
        if name == "javdb":
            if not cfg["javdb_enabled"]:
                return ScrapeResult(provider="javdb")
            return scrape_javdb(
                title=title,
                filename=filename,
                code=code,
                cookie=cfg["javdb_cookie"],
                timeout=timeout,
                proxy=proxy,
            )
    except Exception as exc:
        log.debug("scraper %s failed: %s", name, exc)
    return ScrapeResult(provider=name)


def scrape_for_item(
    item: Any,
    *,
    providers: Optional[Sequence[str]] = None,
    force: bool = False,
    cfg: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Try cloud providers in order; merge fill-empty (or force overwrite).
    Soft-fails: never raises. Returns summary dict for API/logs.
    """
    cfg = cfg or get_scraper_config()
    # Prefer local NFO/embedded: skip internet when metadata is already good.
    # When prefer_local is False, still only fill empty fields (merge_meta), but do not skip early.
    if not force and cfg.get("prefer_local", True) and not is_meta_thin(item) and not providers:
        return {"ok": True, "skipped": True, "reason": "prefer_local", "changed": [], "providers_tried": []}
    if not providers and not cfg.get("internet_enabled", True):
        return {"ok": True, "skipped": True, "reason": "internet_disabled", "changed": [], "providers_tried": []}

    hints = search_query_from_item(
        title=getattr(item, "title", "") or "",
        filename=getattr(item, "filename", "") or "",
        file_path=getattr(item, "file_path", "") or getattr(item, "folder", "") or "",
    )
    title = hints["title"]
    code = hints["code"]
    filename = hints["filename"]
    year = getattr(item, "year", None) or hints.get("year")
    category = getattr(item, "category", "") or "movie"
    # Douban needs Chinese; folder often has 天才游戏[...] .English.Release
    alt_titles = []
    for key in ("zh_title", "en_title", "title"):
        v = (hints.get(key) or "").strip()
        if v and v not in alt_titles:
            alt_titles.append(v)
    cfg = dict(cfg)  # shallow copy so we can stash alts
    cfg["_alt_titles"] = alt_titles

    # Filename identify (Emby-style): clean scene dumps even when cloud has no hit
    pre_changed = []
    raw_title = (getattr(item, "title", None) or "").strip()
    from .base import looks_like_scene_release
    if title and (force or looks_like_scene_release(raw_title) or raw_title.count(".") >= 3 or not raw_title):
        if title != raw_title:
            item.title = title
            pre_changed.append("title")
        if hints.get("year") and (force or not getattr(item, "year", None)):
            item.year = hints["year"]
            year = item.year
            if "year" not in pre_changed:
                pre_changed.append("year")

    if providers:
        order = [p.strip().lower() for p in providers if p and p.strip().lower() in PROVIDER_NAMES]
    else:
        order = list(cfg["order"])

    tried: List[str] = []
    used: List[str] = []
    changed: List[str] = []
    last: Optional[ScrapeResult] = None

    for name in order:
        # Skip disabled unless explicitly requested via providers=
        if providers:
            # explicit request: still need keys for tmdb
            if name == "tmdb" and not cfg["tmdb_api_key"]:
                tried.append(name)
                continue
        else:
            if name == "tmdb" and not (cfg["tmdb_enabled"] and cfg["tmdb_api_key"]):
                continue
            if name == "douban" and not cfg["douban_enabled"]:
                continue
            if name == "javdb" and not cfg["javdb_enabled"]:
                continue

        tried.append(name)
        result = _run_one(
            name,
            title=title,
            filename=filename,
            code=code,
            year=year,
            category=category,
            cfg=cfg,
        )
        last = result
        if not result.has_any():
            continue
        used.append(name)
        ch = merge_meta(item, result.to_dict(), force=force)
        changed.extend(ch)
        # Subsequent providers (esp. Douban) should use newly found CJK titles
        new_t = (getattr(item, "title", None) or "").strip()
        new_o = (getattr(item, "original_title", None) or "").strip()
        for v in (new_t, new_o):
            if v and v not in cfg["_alt_titles"]:
                cfg["_alt_titles"].insert(0, v)
        if new_t and any("一" <= c <= "鿿" for c in new_t):
            title = new_t
        # Stop early once metadata is no longer thin (unless force + want more fields)
        if not force and not is_meta_thin(item):
            break
        # On force, still try remaining only for empty fields (merge_meta handles)
        if force and not is_meta_thin(item) and (getattr(item, "plot", None) or "").strip():
            # keep going only if still missing poster
            if (getattr(item, "poster_url", None) or "").strip():
                break

    changed = sorted(set(list(pre_changed) + list(changed)))
    return {
        "ok": True,
        "skipped": False,
        "changed": changed,
        "providers_tried": tried,
        "providers_used": used,
        "provider": (used[0] if used else ("filename" if pre_changed else (last.provider if last else ""))),
        "title": getattr(item, "title", "") or "",
    }


def apply_live_config(updates: Dict[str, Any]) -> None:
    """Hot-apply scraper keys onto the settings singleton."""
    mapping = {
        "SCRAPER_PREFER_LOCAL": "SCRAPER_PREFER_LOCAL",
        "SCRAPER_INTERNET_ENABLED": "SCRAPER_INTERNET_ENABLED",
        "SCRAPER_METADATA_LANGUAGE": "SCRAPER_METADATA_LANGUAGE",
        "SCRAPER_SAVE_ARTWORK": "SCRAPER_SAVE_ARTWORK",
        "SCRAPER_DOUBAN_ENABLED": "SCRAPER_DOUBAN_ENABLED",
        "SCRAPER_TMDB_ENABLED": "SCRAPER_TMDB_ENABLED",
        "SCRAPER_JAVDB_ENABLED": "SCRAPER_JAVDB_ENABLED",
        "TMDB_API_KEY": "TMDB_API_KEY",
        "SCRAPER_ORDER": "SCRAPER_ORDER",
        "SCRAPER_DOUBAN_COOKIE": "SCRAPER_DOUBAN_COOKIE",
        "SCRAPER_JAVDB_COOKIE": "SCRAPER_JAVDB_COOKIE",
        "SCRAPER_PROXY": "SCRAPER_PROXY",
        "SCRAPER_TIMEOUT_SECONDS": "SCRAPER_TIMEOUT_SECONDS",
    }
    for env_key, attr in mapping.items():
        if env_key in updates:
            val = updates[env_key]
            if attr.endswith("_ENABLED") or attr in ("SCRAPER_PREFER_LOCAL", "SCRAPER_SAVE_ARTWORK"):
                default_true = attr in ("SCRAPER_PREFER_LOCAL", "SCRAPER_INTERNET_ENABLED")
                setattr(settings, attr, _as_bool(val, default_true))
            elif attr == "SCRAPER_TIMEOUT_SECONDS":
                try:
                    setattr(settings, attr, float(val))
                except (TypeError, ValueError):
                    pass
            else:
                setattr(settings, attr, str(val) if val is not None else "")
