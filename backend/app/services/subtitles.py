"""Discover sidecar / embedded subtitle tracks and convert to WebVTT for the browser."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SUB_EXTS = {".srt", ".ass", ".ssa", ".vtt", ".sub"}
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
        })
    return tracks


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
    for stream in data.get("streams") or []:
        idx = stream.get("index")
        if idx is None:
            continue
        tags = stream.get("tags") or {}
        lang_raw = (tags.get("language") or tags.get("LANGUAGE") or "und").lower()
        lang = LANG_ALIASES.get(lang_raw, lang_raw)
        title = tags.get("title") or tags.get("TITLE") or ""
        label = title or LANG_LABELS.get(lang, lang)
        codec = (stream.get("codec_name") or "subrip").lower()
        tid = _stable_id("emb", f"{video.resolve()}:{idx}")
        tracks.append({
            "id": tid,
            "label": label,
            "language": lang,
            "format": codec,
            "source": "embedded",
            "index": int(idx),
            "path": str(video.resolve()),
        })
    return tracks


def list_tracks(video: Path) -> List[Dict[str, Any]]:
    ext = discover_external(video)
    emb = discover_embedded(video)
    # public payload without absolute paths
    out = []
    for t in ext + emb:
        out.append({
            "id": t["id"],
            "label": t["label"],
            "language": t["language"],
            "format": t["format"],
            "source": t["source"],
            "index": t.get("index"),
        })
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


def ffmpeg_extract_vtt(video: Path, stream_index: int) -> Optional[str]:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    try:
        proc = subprocess.run(
            [
                ffmpeg, "-v", "error", "-i", str(video),
                "-map", f"0:{stream_index}", "-f", "webvtt", "-",
            ],
            capture_output=True, text=True, timeout=120,
        )
        if proc.returncode != 0:
            return None
        out = proc.stdout or ""
        if "WEBVTT" not in out:
            return "WEBVTT\n\n" + out
        return out
    except Exception:
        return None


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
        video = Path(track["path"])
        idx = int(track["index"])
        vtt = ffmpeg_extract_vtt(video, idx)
        if vtt is None:
            return "", "需要 ffmpeg 才能提取内嵌字幕"
        return vtt, None
    return "", "未知字幕源"
