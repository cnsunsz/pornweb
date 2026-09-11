"""Discover sidecar / embedded subtitle tracks and convert to WebVTT for the browser."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

SUB_EXTS = {".srt", ".ass", ".ssa", ".vtt", ".sub"}
# Image / bitmap subtitle codecs — list them but do not attempt WebVTT conversion.
IMAGE_SUB_CODECS = {
    "hdmv_pgs_subtitle", "pgs", "pgssub",
    "dvd_subtitle", "dvdsub", "vobsub",
    "xsub", "dvb_subtitle", "dvb_teletext",
}
# Text codecs we expect ffmpeg/mkvextract to turn into SRT/VTT.
TEXT_SUB_CODECS = {
    "subrip", "srt", "ass", "ssa", "mov_text", "text",
    "webvtt", "ttml", "timed_text", "eia_608", "closed_caption",
}

LANG_ALIASES = {
    "zh": "zh", "chi": "zh", "chs": "zh-Hans", "cht": "zh-Hant",
    "zh-cn": "zh-Hans", "zh-tw": "zh-Hant", "zh-hans": "zh-Hans", "zh-hant": "zh-Hant",
    "cn": "zh-Hans", "sc": "zh-Hans", "tc": "zh-Hant",
    "en": "en", "eng": "en", "english": "en",
    "ja": "ja", "jp": "ja", "jpn": "ja",
    "ko": "ko", "kor": "ko",
    "fr": "fr", "fre": "fr", "fra": "fr",
    "de": "de", "ger": "de", "deu": "de",
    "es": "es", "spa": "es",
    "ru": "ru", "rus": "ru",
    "pt": "pt", "por": "pt",
    "it": "it", "ita": "it",
    "und": "und", "unknown": "und",
}
LANG_LABELS = {
    "zh": "中文", "zh-Hans": "简体中文", "zh-Hant": "繁体中文",
    "en": "English", "ja": "日本語", "ko": "한국어",
    "fr": "Français", "de": "Deutsch", "es": "Español",
    "ru": "Русский", "pt": "Português", "it": "Italiano", "und": "未知",
}

# rclone/FUSE MKV demux of a full text track can take several minutes.
EXTRACT_TIMEOUT_SEC = int(os.environ.get("MV_SUB_EXTRACT_TIMEOUT", "600"))
CACHE_DIR = Path(os.environ.get(
    "MV_SUB_CACHE_DIR",
    str(Path(__file__).resolve().parents[2] / "data" / "subcache"),
))
_warm_lock = threading.Lock()
_warming: set = set()
_extract_lock = threading.Lock()
_extract_events: Dict[str, threading.Event] = {}
_extract_results: Dict[str, Tuple[Optional[str], Optional[str]]] = {}
_prep_requested: set = set()
# Cap concurrent embedded extracts so remux/Range reads stay responsive.
EXTRACT_MAX = max(1, int(os.environ.get("MV_SUB_EXTRACT_MAX", "1")))
_extract_sem = threading.Semaphore(EXTRACT_MAX)

# Active extract process groups — paused (SIGSTOP) when player reports waiting.
_active_extract_pgids: set = set()
_extract_yield_video = False
_extract_pg_lock = threading.Lock()


def _stable_id(kind: str, key: str) -> str:
    digest = hashlib.sha1(key.encode("utf-8", errors="replace")).hexdigest()[:16]
    return f"{kind}.{digest}"


def resolve_video_path(item_file_path: str, media_root: str, parts: list, part: int = 0) -> Path:
    chosen = item_file_path
    if parts:
        idx = part if 0 <= part < len(parts) else 0
        chosen = parts[idx].get("path") or item_file_path
    if os.path.isabs(chosen):
        return Path(chosen)
    return Path(media_root) / chosen


def _guess_lang_from_name(name: str, stem: str) -> Tuple[str, str]:
    """Return (bcp47, label) from filename relative to video stem."""
    base = Path(name).stem
    # strip video stem prefix: Movie.zh.srt → zh ; Movie.srt → und
    extra = base
    if base.lower().startswith(stem.lower()):
        extra = base[len(stem):].lstrip("._- ")
    if not extra:
        return "und", "外挂字幕"
    # take first token as lang
    token = re.split(r"[._\-\s]+", extra)[0].lower()
    lang = LANG_ALIASES.get(token, token if re.fullmatch(r"[a-z]{2,3}(-[a-z0-9]+)?", token) else "und")
    label = LANG_LABELS.get(lang, extra or lang)
    # forced / sdh hints
    low = extra.lower()
    if "forced" in low:
        label = f"{label} (Forced)"
    if "sdh" in low or "cc" in low:
        label = f"{label} (SDH)"
    return lang, label


def discover_external(video: Path) -> List[Dict[str, Any]]:
    if not video.exists():
        return []
    stem = video.stem
    parent = video.parent
    candidates: List[Path] = []

    def collect(dir_path: Path):
        if not dir_path.is_dir():
            return
        try:
            for p in dir_path.iterdir():
                if not p.is_file():
                    continue
                if p.suffix.lower() not in SUB_EXTS:
                    continue
                name = p.name
                # match stem or stem.lang.*
                if name.lower().startswith(stem.lower()) or Path(name).stem.lower().startswith(stem.lower()):
                    candidates.append(p)
                elif dir_path != parent:
                    # inside Subs/: accept any subtitle file
                    candidates.append(p)
        except OSError:
            return

    collect(parent)
    for sub in ("Subs", "subs", "Subtitles", "subtitles", "字幕"):
        collect(parent / sub)

    # de-dupe, stable order
    seen = set()
    tracks = []
    for p in sorted(candidates, key=lambda x: x.name.lower()):
        key = str(p.resolve()) if p.exists() else str(p)
        if key in seen:
            continue
        seen.add(key)
        lang, label = _guess_lang_from_name(p.name, stem)
        tid = _stable_id("ext", key)
        tracks.append({
            "id": tid,
            "label": label,
            "language": lang,
            "format": p.suffix.lower().lstrip("."),
            "source": "external",
            "path": key,
            "supported": True,
            "unsupported_reason": None,
        })
    return tracks


def _is_image_codec(codec: str) -> bool:
    c = (codec or "").lower()
    if c in IMAGE_SUB_CODECS:
        return True
    if "pgs" in c or "vobsub" in c or "dvd_sub" in c or "hdmv" in c:
        return True
    return False


def discover_embedded(video: Path) -> List[Dict[str, Any]]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe or not video.exists():
        return []
    try:
        proc = subprocess.run(
            [
                ffprobe, "-v", "quiet", "-print_format", "json",
                "-show_streams", "-select_streams", "s", str(video),
            ],
            capture_output=True, text=True, timeout=30,
        )
        if proc.returncode != 0 or not proc.stdout:
            return []
        data = json.loads(proc.stdout)
    except Exception:
        return []
    tracks = []
    for sub_order, stream in enumerate(data.get("streams") or []):
        idx = stream.get("index")
        if idx is None:
            continue
        tags = stream.get("tags") or {}
        lang_raw = (tags.get("language") or tags.get("LANGUAGE") or "und").lower()
        lang = LANG_ALIASES.get(lang_raw, lang_raw)
        title = tags.get("title") or tags.get("TITLE") or ""
        label = title or LANG_LABELS.get(lang, lang)
        codec = (stream.get("codec_name") or "subrip").lower()
        image = _is_image_codec(codec)
        supported = not image
        reason = "不支持图字幕（PGS/VobSub），请使用外挂 SRT/ASS" if image else None
        if image and "图字幕" not in label:
            label = f"{label} [图字幕不可用]"
        tid = _stable_id("emb", f"{video.resolve()}:{idx}")
        tracks.append({
            "id": tid,
            "label": label,
            "language": lang,
            "format": codec,
            "source": "embedded",
            "index": int(idx),
            "sub_index": int(sub_order),  # for -map 0:s:N
            "path": str(video.resolve()),
            "supported": supported,
            "unsupported_reason": reason,
        })
    return tracks


def list_tracks(video: Path) -> List[Dict[str, Any]]:
    ext = discover_external(video)
    emb = discover_embedded(video)
    # public payload without absolute paths
    out = []
    for t in ext + emb:
        tid = t["id"]
        if t.get("source") == "external":
            cached = True
        elif t.get("supported", True) is False:
            cached = False
        else:
            try:
                cached = bool(_read_cache(tid, Path(t["path"])))
            except Exception:
                cached = False
        out.append({
            "id": tid,
            "label": t["label"],
            "language": t["language"],
            "format": t["format"],
            "source": t["source"],
            "index": t.get("index"),
            "supported": t.get("supported", True),
            "unsupported_reason": t.get("unsupported_reason"),
            "cached": cached,
        })
    # Optional warm (off by default): concurrent mkvextract/ffmpeg on rclone
    # starves video Range reads and causes endless buffering spinner.
    # Enable with MV_SUB_WARM=1 only on local disks.
    if os.environ.get("MV_SUB_WARM", "").strip().lower() in ("1", "true", "yes"):
        try:
            _schedule_warm(video, emb)
        except Exception:
            logger.exception("subtitle warm schedule failed")
    return out


def find_track(video: Path, track_id: str) -> Optional[Dict[str, Any]]:
    for t in discover_external(video) + discover_embedded(video):
        if t["id"] == track_id:
            return t
    return None


def _srt_timestamp_to_vtt(ts: str) -> str:
    ts = ts.strip().replace(",", ".")
    # ensure HH:MM:SS.mmm
    parts = ts.split(":")
    if len(parts) == 3:
        return ts
    if len(parts) == 2:
        return f"00:{ts}"
    return ts


def srt_to_vtt(text: str) -> str:
    text = text.lstrip("\ufeff")
    blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n").replace("\r", "\n").strip())
    cues = ["WEBVTT", ""]
    for block in blocks:
        lines = [ln for ln in block.split("\n") if ln.strip() != ""]
        if not lines:
            continue
        # optional index line
        if re.fullmatch(r"\d+", lines[0].strip()):
            lines = lines[1:]
        if not lines:
            continue
        m = re.match(
            r"(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3}|\d{1,2}:\d{2}[,.]\d{1,3})\s*-->\s*"
            r"(\d{1,2}:\d{2}:\d{2}[,.]\d{1,3}|\d{1,2}:\d{2}[,.]\d{1,3})",
            lines[0],
        )
        if not m:
            continue
        start = _srt_timestamp_to_vtt(m.group(1))
        end = _srt_timestamp_to_vtt(m.group(2))
        body = "\n".join(lines[1:]).strip()
        if not body:
            continue
        cues.append(f"{start} --> {end}")
        cues.append(body)
        cues.append("")
    return "\n".join(cues)


def _read_text(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "utf-8", "gb18030", "latin-1"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", errors="replace")


def ass_to_vtt_rough(text: str) -> str:
    """Best-effort ASS/SSA → VTT (dialogue text only, no styling)."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    cues = ["WEBVTT", ""]
    for line in text.split("\n"):
        if not line.startswith("Dialogue:"):
            continue
        # Dialogue: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
        try:
            payload = line[len("Dialogue:"):].strip()
            parts = payload.split(",", 9)
            if len(parts) < 10:
                continue
            start_raw, end_raw, body = parts[1].strip(), parts[2].strip(), parts[9]
        except Exception:
            continue
        # ASS time H:MM:SS.cs (centiseconds)
        def ass_ts(t: str) -> str:
            m = re.match(r"(\d+):(\d{2}):(\d{2})\.(\d{1,2})", t.strip())
            if not m:
                return "00:00:00.000"
            h, mi, s, cs = m.groups()
            ms = int((cs + "0")[:2]) * 10
            return f"{int(h):02d}:{mi}:{s}.{ms:03d}"
        # strip ASS override tags {\...}
        body = re.sub(r"\{[^}]*\}", "", body)
        body = body.replace("\\N", "\n").replace("\\n", "\n").strip()
        if not body:
            continue
        cues.append(f"{ass_ts(start_raw)} --> {ass_ts(end_raw)}")
        cues.append(body)
        cues.append("")
    return "\n".join(cues)


def _cache_path(track_id: str, video: Path) -> Path:
    try:
        mtime = int(video.stat().st_mtime)
    except OSError:
        mtime = 0
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", track_id)
    return CACHE_DIR / f"{safe}.{mtime}.vtt"


def _read_cache(track_id: str, video: Path) -> Optional[str]:
    path = _cache_path(track_id, video)
    if path.is_file() and path.stat().st_size > 8:
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
    return None


def _write_cache(track_id: str, video: Path, vtt: str) -> None:
    if not vtt or "WEBVTT" not in vtt:
        return
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = _cache_path(track_id, video)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(vtt, encoding="utf-8")
        tmp.replace(path)
    except OSError:
        logger.exception("subtitle cache write failed")




def set_extract_yield_to_video(prefer_video: bool) -> Dict[str, Any]:
    """Pause (SIGSTOP) or resume (SIGCONT) in-flight mkvextract/ffmpeg process groups.
    Used when the web player hits @waiting during subtitle prepare so video Range wins.
    """
    global _extract_yield_video
    prefer = bool(prefer_video)
    with _extract_pg_lock:
        _extract_yield_video = prefer
        pgids = list(_active_extract_pgids)
    sig = signal.SIGSTOP if prefer else signal.SIGCONT
    acted = 0
    for pgid in pgids:
        try:
            os.killpg(pgid, sig)
            acted += 1
        except ProcessLookupError:
            with _extract_pg_lock:
                _active_extract_pgids.discard(pgid)
        except PermissionError:
            logger.debug("cannot signal extract pgid=%s", pgid)
        except Exception:
            logger.exception("signal extract pgid=%s failed", pgid)
    return {"prefer": "video" if prefer else "extract", "signaled": acted, "active": len(pgids)}


def _run_prio_subprocess(cmd: list, timeout: int) -> subprocess.CompletedProcess:
    """Run extract with nice/ionice; track pgid so player can SIGSTOP/CONT on waiting."""
    full = _prio_cmd(cmd)
    # Honor existing yield before start
    with _extract_pg_lock:
        yielding = _extract_yield_video
    # brief wait if video currently preferred (soft lower)
    waited = 0.0
    while yielding and waited < 15.0:
        time.sleep(0.5)
        waited += 0.5
        with _extract_pg_lock:
            yielding = _extract_yield_video

    proc = subprocess.Popen(
        full,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        pgid = os.getpgid(proc.pid)
    except Exception:
        pgid = proc.pid
    with _extract_pg_lock:
        _active_extract_pgids.add(pgid)
        if _extract_yield_video:
            try:
                os.killpg(pgid, signal.SIGSTOP)
            except Exception:
                pass
    try:
        try:
            stdout, stderr = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(pgid, signal.SIGKILL)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            try:
                proc.communicate(timeout=5)
            except Exception:
                pass
            raise
        return subprocess.CompletedProcess(full, proc.returncode, stdout or "", stderr or "")
    finally:
        with _extract_pg_lock:
            _active_extract_pgids.discard(pgid)
            # Ensure not left stopped if somehow still alive
        try:
            if proc.poll() is None:
                os.killpg(pgid, signal.SIGCONT)
        except Exception:
            pass


def _prio_cmd(cmd: list) -> list:
    """Run extract tools at idle I/O + low CPU so video Range/remux win."""
    out: list = []
    if shutil.which("nice"):
        out += ["nice", "-n", "19"]
    if shutil.which("ionice"):
        # best-effort idle class; ignore if kernel lacks CFQ/BFQ ionice
        out += ["ionice", "-c3"]
    return out + list(cmd)


def _mkvextract_srt(video: Path, stream_index: int, out_srt: Path) -> Tuple[bool, str]:
    mkvextract = shutil.which("mkvextract")
    if not mkvextract:
        return False, "no mkvextract"
    # Prefer JSON identify so track id matches Matroska TID (usually == ffprobe index).
    tid = stream_index
    mkvmerge = shutil.which("mkvmerge")
    if mkvmerge:
        try:
            ident = subprocess.run(
                _prio_cmd([mkvmerge, "-J", str(video)]),
                capture_output=True, text=True, timeout=60,
            )
            if ident.returncode == 0 and ident.stdout:
                data = json.loads(ident.stdout)
                # Prefer matching by properties.number == ffprobe index when present
                for t in data.get("tracks") or []:
                    if t.get("type") != "subtitles":
                        continue
                    props = t.get("properties") or {}
                    num = props.get("number")
                    if num is not None and int(num) == int(stream_index):
                        tid = int(t["id"])
                        break
                else:
                    # fallback: ffprobe absolute index often equals mkvextract id on simple files
                    tid = stream_index
        except Exception as e:
            logger.debug("mkvmerge -J failed: %s", e)
    try:
        proc = _run_prio_subprocess(
            [mkvextract, "tracks", str(video), f"{tid}:{out_srt}"],
            EXTRACT_TIMEOUT_SEC,
        )
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "").strip()[:300]
            return False, err or f"mkvextract rc={proc.returncode}"
        if not out_srt.is_file() or out_srt.stat().st_size < 4:
            return False, "mkvextract produced empty file"
        return True, ""
    except subprocess.TimeoutExpired:
        return False, f"mkvextract 超时（>{EXTRACT_TIMEOUT_SEC}s，网盘文件抽取较慢）"
    except Exception as e:
        return False, str(e)


def _ffmpeg_extract_srt_or_vtt(video: Path, stream_index: int, sub_index: Optional[int], out_path: Path, as_vtt: bool) -> Tuple[bool, str]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return False, "未安装 ffmpeg"
    # Prefer absolute map 0:N (ffprobe index); also try 0:s:N (subtitle order).
    map_candidates = [f"0:{stream_index}"]
    if sub_index is not None:
        map_candidates.append(f"0:s:{sub_index}")
    last_err = ""
    for map_sel in map_candidates:
        try:
            if as_vtt:
                cmd = [
                    ffmpeg, "-nostdin", "-v", "error",
                    "-i", str(video), "-map", map_sel,
                    "-f", "webvtt", str(out_path), "-y",
                ]
            else:
                cmd = [
                    ffmpeg, "-nostdin", "-v", "error",
                    "-i", str(video), "-map", map_sel,
                    "-c:s", "srt", str(out_path), "-y",
                ]
            proc = _run_prio_subprocess(cmd, EXTRACT_TIMEOUT_SEC)
            if proc.returncode == 0 and out_path.is_file() and out_path.stat().st_size > 4:
                return True, ""
            last_err = (proc.stderr or "").strip()[:300] or f"ffmpeg rc={proc.returncode} map={map_sel}"
            # try next map
        except subprocess.TimeoutExpired:
            last_err = f"ffmpeg 超时（>{EXTRACT_TIMEOUT_SEC}s，网盘 MKV 抽取较慢，请稍后重试）"
            break
        except Exception as e:
            last_err = str(e)
            break
    return False, last_err


def _ffmpeg_extract_vtt_inner(video: Path, stream_index: int, sub_index: Optional[int], track_id: str) -> Tuple[Optional[str], Optional[str]]:
    """Actual extract worker (no single-flight). Uses low I/O priority + global concurrency cap."""
    if track_id:
        cached = _read_cache(track_id, video)
        if cached:
            return cached, None

    ffmpeg = shutil.which("ffmpeg")
    mkvextract = shutil.which("mkvextract")
    if not ffmpeg and not mkvextract:
        return None, "需要 ffmpeg 或 mkvextract 才能提取内嵌字幕"

    # Wait for a slot without starving forever; callers still have EXTRACT_TIMEOUT.
    if not _extract_sem.acquire(timeout=EXTRACT_TIMEOUT_SEC + 60):
        return None, "字幕提取队列繁忙，请稍后重试"
    try:
        return _ffmpeg_extract_vtt_locked(video, stream_index, sub_index, track_id)
    finally:
        _extract_sem.release()


def _ffmpeg_extract_vtt_locked(video: Path, stream_index: int, sub_index: Optional[int], track_id: str) -> Tuple[Optional[str], Optional[str]]:
    if track_id:
        cached = _read_cache(track_id, video)
        if cached:
            return cached, None

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    work = CACHE_DIR / f"work_{os.getpid()}_{stream_index}_{threading.get_ident()}"
    srt_path = work.with_suffix(".srt")
    vtt_path = work.with_suffix(".vtt")
    try:
        # 1) mkvextract for Matroska (often more reliable; still slow on rclone)
        if video.suffix.lower() in (".mkv", ".mka", ".mks") and mkvextract:
            ok, err = _mkvextract_srt(video, stream_index, srt_path)
            if ok:
                text = _read_text(srt_path)
                vtt = srt_to_vtt(text) if "-->" in text else None
                if vtt and "WEBVTT" in vtt:
                    if track_id:
                        _write_cache(track_id, video, vtt)
                    return vtt, None
            else:
                logger.info("mkvextract failed (%s), falling back to ffmpeg", err)

        # 2) ffmpeg → srt then convert (avoids webvtt muxer buffering quirks)
        ok, err = _ffmpeg_extract_srt_or_vtt(video, stream_index, sub_index, srt_path, as_vtt=False)
        if ok:
            text = _read_text(srt_path)
            if "-->" in text:
                vtt = srt_to_vtt(text)
                if track_id:
                    _write_cache(track_id, video, vtt)
                return vtt, None

        # 3) ffmpeg direct webvtt
        ok, err2 = _ffmpeg_extract_srt_or_vtt(video, stream_index, sub_index, vtt_path, as_vtt=True)
        if ok:
            vtt = _read_text(vtt_path)
            if "WEBVTT" not in vtt:
                vtt = "WEBVTT\n\n" + vtt
            if track_id:
                _write_cache(track_id, video, vtt)
            return vtt, None

        return None, err2 or err or "提取内嵌字幕失败"
    finally:
        for p in (srt_path, vtt_path):
            try:
                if p.exists():
                    p.unlink()
            except OSError:
                pass


def ffmpeg_extract_vtt(video: Path, stream_index: int, sub_index: Optional[int] = None, track_id: str = "") -> Tuple[Optional[str], Optional[str]]:
    """Extract embedded text subtitles to WebVTT. Single-flight per track_id."""
    if track_id:
        cached = _read_cache(track_id, video)
        if cached:
            return cached, None
        wait_event = None
        leader = False
        with _extract_lock:
            cached = _read_cache(track_id, video)
            if cached:
                return cached, None
            if track_id in _extract_events:
                wait_event = _extract_events[track_id]
            else:
                wait_event = threading.Event()
                _extract_events[track_id] = wait_event
                leader = True
        if not leader:
            wait_event.wait(timeout=EXTRACT_TIMEOUT_SEC + 30)
            with _extract_lock:
                if track_id in _extract_results:
                    return _extract_results[track_id]
            cached = _read_cache(track_id, video)
            if cached:
                return cached, None
            return None, "字幕提取进行中，请稍后重试"
        try:
            result = _ffmpeg_extract_vtt_inner(video, stream_index, sub_index, track_id)
            with _extract_lock:
                _extract_results[track_id] = result
            return result
        finally:
            with _extract_lock:
                ev = _extract_events.pop(track_id, None)
                # keep result briefly for waiters; drop later
            if ev:
                ev.set()
            def _clear(tid=track_id):
                time.sleep(2)
                with _extract_lock:
                    _extract_results.pop(tid, None)
            threading.Thread(target=_clear, daemon=True).start()
    return _ffmpeg_extract_vtt_inner(video, stream_index, sub_index, track_id)


def _lang_priority(lang: str) -> int:
    l = (lang or "").lower()
    if l.startswith("zh"):
        return 0
    if l in ("chi", "chs", "cht"):
        return 0
    if l.startswith("en") or l == "eng":
        return 1
    return 9


def _schedule_warm(video: Path, emb_tracks: List[Dict[str, Any]]) -> None:
    """Background-extract up to 2 preferred text tracks so first play is warmer."""
    text_tracks = [t for t in emb_tracks if t.get("supported", True)]
    if not text_tracks:
        return
    text_tracks.sort(key=lambda t: (_lang_priority(t.get("language") or ""), t.get("index") or 0))
    chosen = text_tracks[:2]
    for t in chosen:
        tid = t["id"]
        if _read_cache(tid, video):
            continue
        with _warm_lock:
            if tid in _warming:
                continue
            _warming.add(tid)

        def _run(track=t):
            try:
                ffmpeg_extract_vtt(
                    Path(track["path"]),
                    int(track["index"]),
                    track.get("sub_index"),
                    track_id=track["id"],
                )
            except Exception:
                logger.exception("warm extract failed for %s", track.get("id"))
            finally:
                with _warm_lock:
                    _warming.discard(track["id"])

        threading.Thread(target=_run, name=f"subwarm-{tid[:12]}", daemon=True).start()



def track_is_ready(track: Dict[str, Any]) -> bool:
    """True if VTT can be served without a long extract."""
    if track.get("supported") is False:
        return False
    if track.get("source") == "external":
        return True
    tid = str(track.get("id") or "")
    if not tid:
        return False
    try:
        return bool(_read_cache(tid, Path(track["path"])))
    except Exception:
        return False


def track_status(track: Dict[str, Any]) -> Dict[str, Any]:
    """ready | preparing | error | unavailable | idle — never blocks on extract."""
    tid = str(track.get("id") or "")
    if track.get("supported") is False or _is_image_codec(str(track.get("format") or "")):
        return {
            "status": "unavailable",
            "cached": False,
            "track_id": tid,
            "error": track.get("unsupported_reason") or "不支持图字幕（PGS/VobSub），无法转为 WebVTT",
        }
    if track.get("source") == "external":
        return {"status": "ready", "cached": True, "track_id": tid, "error": None}
    video = Path(track["path"])
    if tid and _read_cache(tid, video):
        return {"status": "ready", "cached": True, "track_id": tid, "error": None}
    with _extract_lock:
        preparing = (
            tid in _extract_events
            or tid in _prep_requested
            or tid in _warming
        )
        if tid in _extract_results:
            vtt, err = _extract_results[tid]
            if err:
                return {"status": "error", "cached": False, "track_id": tid, "error": err}
            if vtt:
                return {"status": "ready", "cached": True, "track_id": tid, "error": None}
    if preparing:
        return {"status": "preparing", "cached": False, "track_id": tid, "error": None}
    return {"status": "idle", "cached": False, "track_id": tid, "error": None}


def prepare_track(track: Dict[str, Any]) -> Dict[str, Any]:
    """Start background extract if needed; return status immediately (non-blocking)."""
    st = track_status(track)
    if st["status"] in ("ready", "unavailable", "error", "preparing"):
        return st
    if track.get("source") != "embedded":
        return st
    tid = str(track.get("id") or "")
    if not tid:
        return {"status": "error", "cached": False, "track_id": tid, "error": "缺少 track_id"}
    with _extract_lock:
        if tid in _extract_events or tid in _prep_requested or tid in _warming:
            return {"status": "preparing", "cached": False, "track_id": tid, "error": None}
        _prep_requested.add(tid)

    def _run(tr=track, track_id=tid):
        try:
            ffmpeg_extract_vtt(
                Path(tr["path"]),
                int(tr["index"]),
                tr.get("sub_index"),
                track_id=track_id,
            )
        except Exception:
            logger.exception("prepare extract failed for %s", track_id)
        finally:
            with _extract_lock:
                _prep_requested.discard(track_id)

    threading.Thread(target=_run, name=f"subprep-{tid[:12]}", daemon=True).start()
    return {"status": "preparing", "cached": False, "track_id": tid, "error": None}


def track_to_vtt(track: Dict[str, Any]) -> Tuple[str, Optional[str]]:
    """Return (vtt_text, error_detail)."""
    source = track.get("source")
    if source == "external":
        path = Path(track["path"])
        if not path.exists():
            return "", "字幕文件不存在"
        fmt = path.suffix.lower()
        text = _read_text(path)
        if fmt == ".vtt":
            if not text.lstrip().upper().startswith("WEBVTT"):
                text = "WEBVTT\n\n" + text
            return text, None
        if fmt == ".srt" or fmt == ".sub":
            # .sub often microdvd; try srt first
            if "-->" in text:
                return srt_to_vtt(text), None
            return "", "暂不支持该 .sub 格式"
        if fmt in (".ass", ".ssa"):
            return ass_to_vtt_rough(text), None
        return "", f"不支持的字幕格式: {fmt}"
    if source == "embedded":
        if track.get("supported") is False or _is_image_codec(str(track.get("format") or "")):
            return "", track.get("unsupported_reason") or "不支持图字幕（PGS/VobSub），无法转为 WebVTT"
        video = Path(track["path"])
        idx = int(track["index"])
        vtt, err = ffmpeg_extract_vtt(
            video, idx, track.get("sub_index"), track_id=str(track.get("id") or ""),
        )
        if vtt is None:
            return "", err or "提取内嵌字幕失败"
        return vtt, None
    return "", "未知字幕源"
