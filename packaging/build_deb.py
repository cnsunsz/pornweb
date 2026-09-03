#!/usr/bin/env python3
"""Build mediavault_1.0.0_all.deb on Windows or Linux (no dpkg-deb required)."""
from __future__ import annotations

import gzip
import hashlib
import io
import os
import stat
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG_NAME = "mediavault"
VERSION = "1.0.2"
OUT = ROOT / f"{PKG_NAME}_{VERSION}_all.deb"
DEBIAN = Path(__file__).resolve().parent / "debian"


def add_file(tf: tarfile.TarFile, arcname: str, data: bytes, mode: int = 0o644):
    info = tarfile.TarInfo(name="./" + arcname.lstrip("./"))
    info.size = len(data)
    info.mode = mode
    info.uid = 0
    info.gid = 0
    info.uname = "root"
    info.gname = "root"
    info.mtime = int(time.time())
    tf.addfile(info, io.BytesIO(data))


def add_dir(tf: tarfile.TarFile, arcname: str):
    info = tarfile.TarInfo(name="./" + arcname.lstrip("./").rstrip("/") + "/")
    info.type = tarfile.DIRTYPE
    info.mode = 0o755
    info.uid = 0
    info.gid = 0
    info.uname = "root"
    info.gname = "root"
    info.mtime = int(time.time())
    tf.addfile(info)


def collect_tree(src: Path, dest_prefix: str, skip_names: set[str]):
    files = []
    dirs = set()
    for path in src.rglob("*"):
        if any(p in skip_names for p in path.parts):
            continue
        rel = path.relative_to(src).as_posix()
        dest = f"{dest_prefix}/{rel}"
        if path.is_dir():
            dirs.add(dest)
        elif path.is_file():
            parent = str(Path(dest).parent).replace("\\", "/")
            while parent and parent != ".":
                dirs.add(parent)
                parent = str(Path(parent).parent).replace("\\", "/")
            files.append((dest, path.read_bytes(), 0o644))
    return dirs, files


def gzip_bytes(raw: bytes) -> bytes:
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb", mtime=0) as gz:
        gz.write(raw)
    return buf.getvalue()


def ar_member(name: str, data: bytes) -> bytes:
    header = (
        name.ljust(16).encode("ascii")
        + str(int(time.time())).ljust(12).encode("ascii")
        + b"0     "
        + b"0     "
        + b"100644  "
        + str(len(data)).ljust(10).encode("ascii")
        + b"`\n"
    )
    if len(data) % 2 == 1:
        data = data + b"\n"
    return header + data


def main():
    frontend = ROOT / "frontend" / "dist"
    backend_app = ROOT / "backend" / "app"
    req = ROOT / "backend" / "requirements.txt"
    if not frontend.exists():
        raise SystemExit("frontend/dist missing — run npm run build first")
    if not backend_app.exists():
        raise SystemExit("backend/app missing")

    skip = {"__pycache__", "venv", "node_modules", ".git"}

    data_buf = io.BytesIO()
    md5_lines = []
    installed = 0
    dirs = {
        "opt",
        "opt/mediavault",
        "opt/mediavault/backend",
        "opt/mediavault/frontend",
        "lib",
        "lib/systemd",
        "lib/systemd/system",
        "etc",
        "etc/nginx",
        "etc/nginx/sites-available",
        "usr",
        "usr/share",
        "usr/share/doc",
        "usr/share/doc/mediavault",
    }

    extra_files = []

    d1, f1 = collect_tree(backend_app, "opt/mediavault/backend/app", skip)
    dirs |= d1
    extra_files += f1
    extra_files.append(("opt/mediavault/backend/requirements.txt", req.read_bytes(), 0o644))
    extra_files.append(("opt/mediavault/backend/run.py", (ROOT / "backend" / "run.py").read_bytes(), 0o644))
    d2, f2 = collect_tree(frontend, "opt/mediavault/frontend", skip)
    dirs |= d2
    extra_files += f2
    extra_files.append(
        ("lib/systemd/system/mediavault.service", (DEBIAN / "mediavault.service").read_bytes(), 0o644)
    )
    extra_files.append(
        ("etc/nginx/sites-available/mediavault", (DEBIAN / "nginx.conf").read_bytes(), 0o644)
    )
    readme = (
        "Install:  sudo apt install ./mediavault_1.0.0_all.deb\n"
        "Remove:   sudo apt remove mediavault\n"
        "Purge:    sudo apt purge mediavault\n"
        "Web:      http://SERVER/  or  http://SERVER:8096/\n"
        "Data:     /var/lib/mediavault\n"
        "Config:   /etc/mediavault/mediavault.env\n"
    ).encode("utf-8")
    extra_files.append(("usr/share/doc/mediavault/README", readme, 0o644))
    extra_files.append(("usr/share/doc/mediavault/copyright", (DEBIAN / "copyright").read_bytes(), 0o644))

    with tarfile.open(fileobj=data_buf, mode="w") as tf:
        for d in sorted(dirs, key=lambda x: x.count("/")):
            add_dir(tf, d)
        for dest, data, mode in extra_files:
            add_file(tf, dest, data, mode)
            md5_lines.append(f"{hashlib.md5(data).hexdigest()}  {dest}")
            installed += len(data)

    data_gz = gzip_bytes(data_buf.getvalue())

    control_text = (DEBIAN / "control").read_text(encoding="utf-8")
    if "Installed-Size:" not in control_text:
        control_text = control_text.replace(
            "Architecture: all\n",
            f"Architecture: all\nInstalled-Size: {max(1, installed // 1024)}\n",
        )
    scripts = {
        "postinst": 0o755,
        "prerm": 0o755,
        "postrm": 0o755,
    }
    ctrl_buf = io.BytesIO()
    with tarfile.open(fileobj=ctrl_buf, mode="w") as tf:
        add_file(tf, "control", control_text.encode("utf-8"), 0o644)
        add_file(tf, "md5sums", ("\n".join(md5_lines) + "\n").encode("ascii"), 0o644)
        for name, mode in scripts.items():
            raw = (DEBIAN / name).read_bytes().replace(b"\r\n", b"\n")
            add_file(tf, name, raw, mode)
    control_gz = gzip_bytes(ctrl_buf.getvalue())

    debian_binary = b"2.0\n"
    deb = b"!<arch>\n" + ar_member("debian-binary", debian_binary)
    deb += ar_member("control.tar.gz", control_gz)
    deb += ar_member("data.tar.gz", data_gz)
    OUT.write_bytes(deb)
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes, {len(extra_files)} files)")


if __name__ == "__main__":
    main()
