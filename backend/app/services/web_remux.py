"""Streamable web remux: copy video, transcode audio → AAC, fMP4 pipe (Emby-like)."""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Iterator, Optional

logger = logging.getLogger(__name__)

MAX_CONCURRENT = int(os.environ.get("MV_WEB_REMUX_MAX", "2"))
AAC_BITRATE = os.environ.get("MV_WEB_AAC_BITRATE", "192k")
AAC_CHANNELS = int(os.environ.get("MV_WEB_AAC_CHANNELS", "2"))

_sem = threading.Semaphore(MAX_CONCURRENT)


def ffmpeg_available() -> bool:
    return bool(shutil.which("ffmpeg"))


def build_remux_cmd(
    src: Path,
    *,
    start_sec: float = 0.0,
    audio_index: int = 0,
    audio_mode: str = "transcode",
) -> list:
    """ffmpeg → fragmented MP4 on stdout. Video copy; audio AAC or copy."""
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin"]
    if start_sec and start_sec > 0.5:
        cmd += ["-ss", f"{start_sec:.3f}"]
    cmd += ["-i", str(src)]
    cmd += [
        "-map", "0:v:0?",
        "-map", f"0:a:{audio_index}?",
        "-c:v", "copy",
    ]
    if audio_mode == "copy":
        cmd += ["-c:a", "copy"]
    else:
        cmd += [
            "-c:a", "aac",
            "-ac", str(max(1, min(AAC_CHANNELS, 2))),
            "-b:a", AAC_BITRATE,
        ]
    cmd += [
        "-movflags", "+frag_keyframe+empty_moov+default_base_moof+delay_moov",
        "-f", "mp4",
        "pipe:1",
    ]
    return cmd


def iter_web_remux(
    src: Path,
    *,
    start_sec: float = 0.0,
    audio_index: int = 0,
    audio_mode: str = "transcode",
) -> Iterator[bytes]:
    """Yield fMP4 bytes from ffmpeg. Raises RuntimeError if ffmpeg missing/fails to start."""
    if not ffmpeg_available():
        raise RuntimeError("ffmpeg not found")
    if not src.exists():
        raise FileNotFoundError(str(src))

    if not _sem.acquire(timeout=30):
        raise RuntimeError("too many remux sessions")

    cmd = build_remux_cmd(
        src, start_sec=start_sec, audio_index=audio_index, audio_mode=audio_mode
    )
    proc: Optional[subprocess.Popen] = None
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1024 * 256,
        )
        assert proc.stdout is not None
        while True:
            chunk = proc.stdout.read(256 * 1024)
            if not chunk:
                break
            yield chunk
        rc = proc.wait(timeout=8)
        # Client abort / SIGPIPE commonly surfaces as 255, -13, -9, -15
        if rc not in (0, None, 255, -13, -9, -15, 1):
            err = b""
            try:
                if proc.stderr:
                    err = proc.stderr.read(800) or b""
            except Exception:
                pass
            logger.warning("web remux exit %s: %s", rc, err[:400])
    finally:
        try:
            if proc and proc.poll() is None:
                proc.kill()
                proc.wait(timeout=3)
        except Exception:
            pass
        _sem.release()
