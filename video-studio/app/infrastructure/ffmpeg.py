"""Miniaturas y duraciones con ffmpeg/ffprobe del sistema."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

from app.domain.background import VIDEO_EXTS, is_image


def thumbnail_file(path: Path, thumbs_dir: Path) -> Path:
    """Dónde va (o está) la miniatura de un archivo: cambia si el archivo cambia."""
    key = hashlib.md5(f"{path.name}:{path.stat().st_mtime_ns}".encode()).hexdigest()[:16]
    return thumbs_dir / f"{key}.jpg"


def thumbnail(path: Path, thumbs_dir: Path) -> Path | None:
    """Extrae un fotograma como miniatura; se cachea por nombre+mtime."""
    out = thumbnail_file(path, thumbs_dir)
    if out.exists():
        return out
    thumbs_dir.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-loglevel", "error"]
    if path.suffix.lower() in VIDEO_EXTS:
        cmd += ["-ss", "2"]
    cmd += ["-i", str(path), "-frames:v", "1", "-vf", "scale=180:320", str(out)]
    try:
        subprocess.run(cmd, check=True, timeout=60)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return None
    return out if out.exists() else None


def probe_duration(path: Path) -> float:
    if is_image(path.name):
        return 0.0
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=30,
        )
        return round(float(out.stdout.strip()), 1)
    except (ValueError, subprocess.SubprocessError, OSError):
        return 0.0
