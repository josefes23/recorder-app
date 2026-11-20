"""
El acabado de un video, hecho sonar y verse: ffmpeg para el audio, numpy para
el color y Pillow para las tarjetas. Las reglas (qué se recorta, cuánto vale
cada look) están en `domain.finish`.

Todo se hace dentro del mismo render que ya existe: no hay una segunda
codificación del video. Con Windows y Mac se usa el ffmpeg que trae moviepy
(`imageio-ffmpeg`), el mismo que codifica el video.
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from app.domain.errors import EngineError
from app.domain.finish import TARGET_LUFS, TRUE_PEAK_DB, ColorFinish

#: Un corte sin fundido suena a clic: unos milisegundos bastan.
CROSSFADE = 0.006


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


# Audio --------------------------------------------------------------------- #


def tighten_audio(src: Path, keep: Sequence[tuple[float, float]], out: Path) -> None:
    """La voz con solo los tramos `keep` (segundos), unidos con un fundido mínimo."""
    if not keep:
        raise EngineError("No queda nada de la voz al recortar las pausas.")
    parts, labels = [], []
    for i, (start, end) in enumerate(keep):
        length = end - start
        fade = min(CROSSFADE, length / 2)
        parts.append(
            f"[0:a]atrim=start={start:.4f}:end={end:.4f},asetpts=PTS-STARTPTS,"
            f"afade=t=in:d={fade:.4f},afade=t=out:st={max(length - fade, 0):.4f}:d={fade:.4f}[s{i}]"
        )
        labels.append(f"[s{i}]")
    parts.append(f"{''.join(labels)}concat=n={len(keep)}:v=0:a=1[out]")
    _run(
        ["-i", str(src), "-filter_complex", ";".join(parts), "-map", "[out]", "-c:a", "libmp3lame", "-b:a", "192k", str(out)],
        "recortar las pausas de la voz",
    )


#: Voz con presencia: sin graves que ensucian, volumen parejo y algo de brillo.
VOICE_CHAIN = (
    "highpass=f=70,"
    "acompressor=threshold=0.125:ratio=3:attack=8:release=120:makeup=1.6,"
    "equalizer=f=3200:t=q:w=1.2:g=2.5"
)


def clean_voice(src: Path, out: Path) -> None:
    _run(["-i", str(src), "-af", VOICE_CHAIN, "-c:a", "libmp3lame", "-b:a", "192k", str(out)], "limpiar la voz")


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


# Color --------------------------------------------------------------------- #


@dataclass(frozen=True)
class Look:
    #: Ganancia por canal (r, g, b).
    gain: tuple[float, float, float] = (1.0, 1.0, 1.0)
    #: Tinte añadido en las sombras y en las luces, por canal.
    shadows: tuple[float, float, float] = (0.0, 0.0, 0.0)
    highlights: tuple[float, float, float] = (0.0, 0.0, 0.0)
    contrast: float = 1.0
    saturation: float = 1.0


LOOK_PARAMS: dict[str, Look] = {
    "none": Look(),
    "warm": Look(gain=(1.06, 1.0, 0.92), saturation=1.05),
    "cool": Look(gain=(0.94, 1.0, 1.07)),
    "cine": Look(shadows=(-0.02, 0.015, 0.045), highlights=(0.045, 0.012, -0.04), contrast=1.12, saturation=0.92),
    "vivid": Look(contrast=1.10, saturation=1.32),
    "mono": Look(contrast=1.08, saturation=0.0),
}

_LUMA = (0.2126, 0.7152, 0.0722)


def channel_curves(color: ColorFinish):
    """Una tabla de 256 valores por canal con exposición, contraste y tinte; es lo que más rinde por fotograma."""
    import numpy as np

    look = LOOK_PARAMS[color.look]
    x = np.arange(256, dtype=np.float32) / 255.0
    exposure = 2.0 ** (0.8 * color.exposure)
    contrast = look.contrast * (1.0 + 0.5 * color.contrast)
    curves = []
    for c in range(3):
        y = x * look.gain[c] * exposure
        y = (y - 0.5) * contrast + 0.5
        y = y + look.shadows[c] * (1.0 - x) ** 2 + look.highlights[c] * x**2
        curves.append((np.clip(y, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8))
    return curves


def saturation_of(color: ColorFinish) -> float:
    return max(0.0, LOOK_PARAMS[color.look].saturation * (1.0 + color.saturation))


def make_grade(color: ColorFinish) -> Callable | None:
    """
    El fotograma (alto × ancho × 3, uint8) con el color aplicado, o None si el
    acabado no toca el color. Se aplica al fondo, antes de pintar los
    subtítulos: así el blanco de las letras no se tiñe.
    """
    if not color.active:
        return None
    import numpy as np

    curves = channel_curves(color)
    saturation = saturation_of(color)
    weights = np.array(_LUMA, dtype=np.float32)

    def grade(frame):
        toned = np.empty_like(frame)
        for c in range(3):
            toned[..., c] = curves[c][frame[..., c]]
        if abs(saturation - 1.0) < 1e-3:
            return toned
        values = toned.astype(np.float32)
        luma = values @ weights
        values = luma[..., None] + (values - luma[..., None]) * saturation
        return np.clip(values + 0.5, 0, 255).astype(np.uint8)

    return grade


# Tarjetas ------------------------------------------------------------------ #

ACCENT = (255, 138, 76)


def split_highlights(text: str) -> list[tuple[str, bool]]:
    """«Lo que *nadie* dice» → palabras con su marca de resaltado."""
    words: list[tuple[str, bool]] = []
    on = False
    for chunk in re.split(r"(\*)", text):
        if chunk == "*":
            on = not on
        else:
            words += [(word, on) for word in chunk.split()]
    return words


def card_frame(text: str, size: tuple[int, int], font_path: str | None):
    """La imagen de una tarjeta: degradado oscuro y el texto centrado, con lo marcado en el color de acento."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    width, height = size
    top, bottom = np.array((12, 14, 19), dtype=np.float32), np.array((44, 27, 17), dtype=np.float32)
    ramp = np.linspace(0.0, 1.0, height, dtype=np.float32)[:, None, None]
    base = (top + (bottom - top) * ramp).astype(np.uint8)
    image = Image.fromarray(np.broadcast_to(base, (height, width, 3)).copy())
    draw = ImageDraw.Draw(image)

    words = split_highlights(text)
    box = width * 0.82
    font_size = int(min(width, height) * 0.09)
    while True:
        font = ImageFont.truetype(font_path, font_size) if font_path else ImageFont.load_default(font_size)
        space = draw.textlength(" ", font=font)
        lines: list[list[tuple[str, bool]]] = [[]]
        used = 0.0
        for word, on in words:
            w = draw.textlength(word, font=font)
            if lines[-1] and used + space + w > box:
                lines.append([])
                used = 0.0
            used += (space if lines[-1] else 0.0) + w
            lines[-1].append((word, on))
        if (len(lines) <= 6 and all(
            sum(draw.textlength(w, font=font) for w, _ in line) + space * (len(line) - 1) <= box for line in lines
        )) or font_size <= 20:
            break
        font_size = int(font_size * 0.92)

    line_height = int(font_size * 1.25)
    y = (height - line_height * len(lines)) / 2
    for line in lines:
        total = sum(draw.textlength(w, font=font) for w, _ in line) + space * (len(line) - 1)
        x = (width - total) / 2
        for word, on in line:
            draw.text((x, y), word, font=font, fill=ACCENT if on else (245, 246, 250))
            x += draw.textlength(word, font=font) + space
        y += line_height
    return np.asarray(image)


def card_clip(text: str, size: tuple[int, int], font_path: str | None, seconds: float, fade: float = 0.25):
    """Una tarjeta como clip con su audio en silencio, para poder unirla al video."""
    import numpy as np
    from moviepy import AudioClip, ImageClip, vfx

    silence = AudioClip(
        lambda t: np.zeros(2) if np.isscalar(t) else np.zeros((len(t), 2)), duration=seconds, fps=44100,
    )
    clip = ImageClip(card_frame(text, size, font_path)).with_duration(seconds)
    return clip.with_effects([vfx.FadeIn(fade), vfx.FadeOut(fade)]).with_audio(silence)
