"""Probe container/codecs for web playback decisions (browser-safe audio)."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Audio that Chrome/Firefox typically cannot decode in <video> (silent or error).
# Chrome/Firefox usually lack AC3/E-AC3/DTS/TrueHD in <video> → silent or error.
BROWSER_UNSAFE_AUDIO = {
    "eac3", "ec-3", "ec3", "ac3", "dts", "dca", "truehd", "mlp",
    "pcm_bluray", "pcm_dvd", "dtshd", "dts-hd", "atmos",
}
# Stats helper: "premium" cinema tracks (vs aac/ac3 for library survey)
PREMIUM_AUDIO = {"eac3", "dts", "truehd", "mlp", "dtshd", "pcm_bluray"}
# Prefer these for direct browser play (still may fail on exotic containers).
BROWSER_SAFE_AUDIO = {"aac", "mp3", "opus", "vorbis", "flac", "mp4a"}

PROBE_TIMEOUT = int(os.environ.get("MV_AV_PROBE_TIMEOUT", "90"))
CACHE_DIR = Path(os.environ.get(
    "MV_PROBE_CACHE_DIR",
    str(Path(__file__).resolve().parents[2] / "data" / "probe_cache"),
))
_mem: Dict[str, Dict[str, Any]] = {}
_lock = threading.Lock()


def _cache_key(path: Path) -> str:
    try:
        st = path.stat()
        raw = f"{path}|{st.st_size}|{int(st.st_mtime)}"
    except OSError:
        raw = str(path)
    return hashlib.sha1(raw.encode("utf-8", errors="replace")).hexdigest()


def _disk_get(key: str) -> Optional[Dict[str, Any]]:
    p = CACHE_DIR / f"{key}.json"
    try:
        if p.is_file():
            return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    return None


def _disk_put(key: str, data: Dict[str, Any]) -> None:
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        (CACHE_DIR / f"{key}.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )
    except Exception as exc:
        logger.debug("probe cache write failed: %s", exc)


def _normalize_audio(name: str) -> str:
    n = (name or "").lower().strip()
    if n in ("ec-3", "ec3"):
        return "eac3"
    if n in ("dca",):
        return "dts"
    return n


def needs_audio_remux(audio_codecs: List[str], container: str = "") -> bool:
    """True when the *default/first* audio track is not browser-safe.

    Browsers almost always pick track 0; a later AAC does not help if #0 is E-AC3.
    """
    auds = [_normalize_audio(a) for a in (audio_codecs or []) if a]
    if not auds:
        return (container or "").lower() in ("matroska", "mkv", "")
    first = auds[0]
    if first in BROWSER_SAFE_AUDIO:
        return False
    if first in BROWSER_UNSAFE_AUDIO:
        return True
    return (container or "").lower() in ("matroska", "mkv")


def probe_file(path: Path, use_cache: bool = True) -> Dict[str, Any]:
    """Return {container, video_codec, audio_codecs, audio_channels, needs_audio_remux, ...}."""
    empty = {
        "container": "",
        "video_codec": "",
        "audio_codecs": [],
        "audio_codec": "",
        "audio_channels": 0,
        "needs_audio_remux": False,
        "probed": False,
        "error": None,
    }
    if not path or not Path(path).exists():
        empty["error"] = "missing"
        return empty

    path = Path(path)
    key = _cache_key(path)
    if use_cache:
        with _lock:
            if key in _mem:
                return dict(_mem[key])
        disk = _disk_get(key)
        if disk and disk.get("probed"):
            with _lock:
                _mem[key] = disk
            return dict(disk)

    if not shutil_which("ffprobe"):
        empty["error"] = "no_ffprobe"
        # Conservative: treat .mkv as needing remux for web
        if path.suffix.lower() == ".mkv":
            empty["container"] = "matroska"
            empty["needs_audio_remux"] = True
        return empty

    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=format_name:stream=index,codec_type,codec_name,channels",
            "-of", "json",
            str(path),
        ]
        out = subprocess.check_output(cmd, timeout=PROBE_TIMEOUT, stderr=subprocess.DEVNULL)
        data = json.loads(out.decode("utf-8", errors="replace") or "{}")
    except Exception as exc:
        logger.warning("ffprobe failed %s: %s", path, exc)
        empty["error"] = str(exc)[:200]
        if path.suffix.lower() == ".mkv":
            empty["container"] = "matroska"
            empty["needs_audio_remux"] = True
        return empty

    fmt = ((data.get("format") or {}).get("format_name") or "")
    container = "matroska" if "matroska" in fmt.lower() or path.suffix.lower() == ".mkv" else (
        "mp4" if "mp4" in fmt.lower() or path.suffix.lower() in (".mp4", ".m4v") else fmt.split(",")[0]
    )
    video = ""
    auds: List[str] = []
    channels = 0
    for s in data.get("streams") or []:
        ctype = s.get("codec_type")
        cname = _normalize_audio(s.get("codec_name") or "") if ctype == "audio" else (s.get("codec_name") or "")
        if ctype == "video" and not video:
            video = (s.get("codec_name") or "").lower()
        elif ctype == "audio":
            auds.append(cname)
            try:
                ch = int(s.get("channels") or 0)
            except (TypeError, ValueError):
                ch = 0
            if ch > channels:
                channels = ch

    # Prefer remuxing an already-safe track by copy when default is unsafe
    preferred_idx = 0
    remux_mode = "transcode"  # or "copy"
    # Only AAC/MP3 copy cleanly into fMP4; opus/flac/vorbis still transcode.
    for i, a in enumerate(auds):
        if a in ("aac", "mp3", "mp4a"):
            preferred_idx = i
            remux_mode = "copy"
            break
    need = needs_audio_remux(auds, container)
    if need and remux_mode == "copy":
        # still need remux container for web, but audio can be copied
        pass
    elif not need:
        remux_mode = "none"
        preferred_idx = 0

    result = {
        "container": container,
        "video_codec": video,
        "audio_codecs": auds,
        "audio_codec": auds[0] if auds else "",
        "audio_channels": channels,
        "needs_audio_remux": need,
        "preferred_audio_index": preferred_idx,
        "remux_mode": remux_mode,
        "probed": True,
        "error": None,
        "probed_at": int(time.time()),
    }
    with _lock:
        _mem[key] = result
    _disk_put(key, result)
    return dict(result)


def shutil_which(cmd: str) -> Optional[str]:
    import shutil
    return shutil.which(cmd)


def probe_media_path(path: Path) -> Dict[str, Any]:
    return probe_file(path)
