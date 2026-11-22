"""
El volumen de la mezcla final (voz y música), llevado al de las plataformas.

YouTube, Instagram y TikTok bajan o suben el volumen de lo que se sube hasta su
nivel: un video que llega más flojo suena más bajo que el de al lado. El render
siempre deja la mezcla en `TARGET_LUFS`. Con Windows y Mac se usa el ffmpeg que
trae moviepy (`imageio-ffmpeg`), el mismo que codifica el video.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from app.domain.errors import EngineError

#: El nivel de YouTube, Instagram y TikTok.
TARGET_LUFS = -14.0
#: Margen para que el códec de la plataforma no sature los picos.
TRUE_PEAK_DB = -1.5


def ffmpeg_exe() -> str:
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # noqa: BLE001 - sin imageio-ffmpeg, el del sistema
        return "ffmpeg"


def _run(args: Sequence[str], what: str) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(
            [ffmpeg_exe(), "-y", "-hide_banner", "-loglevel", "info", *args],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise EngineError(f"No se pudo {what}: ffmpeg no respondió ({type(exc).__name__}).") from exc
    if result.returncode != 0:
        tail = " ".join(result.stderr.strip().splitlines()[-2:])
        raise EngineError(f"No se pudo {what}: {tail[:240]}")
    return result


@dataclass(frozen=True)
class Loudness:
    integrated: float
    true_peak: float
    range: float
    threshold: float
    offset: float


def _loudnorm(target: float = TARGET_LUFS) -> str:
    return f"loudnorm=I={target}:TP={TRUE_PEAK_DB}:LRA=11"


def parse_loudnorm(stderr: str) -> Loudness:
    """Lo que midió la primera pasada de `loudnorm`: un bloque JSON al final de lo que ffmpeg escribe."""
    blocks = re.findall(r"\{[^{}]*\}", stderr, flags=re.DOTALL)
    if not blocks:
        raise EngineError("ffmpeg no midió el volumen del audio.")
    try:
        data = json.loads(blocks[-1])
        return Loudness(
            integrated=float(data["input_i"]),
            true_peak=float(data["input_tp"]),
            range=float(data["input_lra"]),
            threshold=float(data["input_thresh"]),
            offset=float(data["target_offset"]),
        )
    except (ValueError, KeyError) as exc:
        raise EngineError("ffmpeg midió el volumen del audio de una forma que no se entiende.") from exc


def measure_loudness(src: Path) -> Loudness:
    result = _run(["-i", str(src), "-af", f"{_loudnorm()}:print_format=json", "-f", "null", "-"], "medir el volumen")
    return parse_loudnorm(result.stderr)


def normalize_loudness(src: Path, out: Path, target: float = TARGET_LUFS) -> Loudness:
    """
    Lleva el audio a `target` LUFS en dos pasadas: se mide y se corrige con esa
    medida, en lineal, así el resultado no «respira» como con una sola pasada.
    Devuelve lo que midió del original.
    """
    heard = measure_loudness(src)
    second = (
        f"{_loudnorm(target)}:measured_I={heard.integrated}:measured_TP={heard.true_peak}"
        f":measured_LRA={heard.range}:measured_thresh={heard.threshold}:offset={heard.offset}:linear=true"
    )
    _run(["-i", str(src), "-af", second, "-ar", "44100", "-c:a", "pcm_s16le", str(out)], "normalizar el volumen")
    return heard
