"""Utilidades mínimas sobre ffmpeg / ffprobe."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

# Homebrew separa ffmpeg en dos: `ffmpeg` (sin libass, no quema subtítulos) y
# `ffmpeg-full` (completo), que se instala fuera del PATH. Si está, se usa ese.
_BREW_FULL = ["/opt/homebrew/opt/ffmpeg-full/bin", "/usr/local/opt/ffmpeg-full/bin"]


def install_hint() -> str:
    """Cómo instalar un ffmpeg completo (con libass) en este sistema."""
    if sys.platform == "darwin":
        return "brew install ffmpeg-full"
    if os.name == "nt":
        return "winget install Gyan.FFmpeg  (después abrí una terminal nueva)"
    return "sudo apt install ffmpeg  (Fedora: sudo dnf install ffmpeg)"


@lru_cache(maxsize=None)
def need(tool: str) -> str:
    dirs = [os.path.expanduser(os.environ["FFMPEG_DIR"])] if os.environ.get("FFMPEG_DIR") else []
    if sys.platform == "darwin":
        dirs += _BREW_FULL
    for d in dirs:
        if found := shutil.which(tool, path=d):
            return found
    if found := shutil.which(tool):
        return found
    raise SystemExit(f"ERROR: falta {tool}. Instalalo con: {install_hint()}")


def _run(args: list[str], **kw) -> subprocess.CompletedProcess:
    # utf-8 explícito: en Windows la página de códigos local no decodifica
    # rutas con tildes que ffmpeg repite en sus mensajes.
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", **kw)


def run(args: list[str], cwd: Path | None = None) -> None:
    """Ejecuta ffmpeg y, si falla, muestra solo el final del log (lo útil)."""
    proc = _run([need("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", *args], cwd=cwd)
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-15:])
        raise RuntimeError(f"ffmpeg falló:\n{tail}")


def duration(path: Path) -> float:
    out = _run([need("ffprobe"), "-v", "error", "-show_entries", "format=duration",
                "-of", "json", str(path)], check=True).stdout
    return float(json.loads(out)["format"]["duration"])


def size(path: Path) -> tuple[int, int]:
    out = _run([need("ffprobe"), "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height", "-of", "json", str(path)],
               check=True).stdout
    s = json.loads(out)["streams"][0]
    return int(s["width"]), int(s["height"])


@lru_cache(maxsize=None)
def has_filter(name: str) -> bool:
    out = _run([need("ffmpeg"), "-hide_banner", "-filters"]).stdout
    return any(line.split()[1:2] == [name] for line in out.splitlines() if line.strip())
