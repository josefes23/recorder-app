"""
La galería de música y cómo suena debajo de la voz.

Las pistas las sube el usuario (de bibliotecas libres de derechos): el estudio
no las genera ni las descarga. Al renderizar, la pista elegida se repite hasta
cubrir el video, entra y sale con un fundido, y **baja sola mientras hay voz**
(«ducking»): suena a su volumen en los silencios y a una fracción de él cuando
alguien habla, para que la voz siempre se entienda.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import PurePath

from app.domain.errors import ValidationError

MUSIC_EXTS = (".mp3", ".m4a", ".aac", ".wav", ".ogg")

#: Volumen de la música en los silencios, de 0 a 1. Bajo a propósito: es fondo.
DEFAULT_VOLUME = 0.25
#: Qué parte de ese volumen queda mientras hay voz.
DUCKED_RATIO = 0.35
#: Segundos que tarda en bajar o subir: un corte seco se nota.
RAMP = 0.3
#: Dos palabras separadas por menos que esto cuentan como la misma frase: la
#: música no sube entre palabra y palabra.
JOIN_GAP = 0.6
FADE_SECONDS = 2.0

#: Volumen del sonido ambiente de los clips animados, cuando se usa.
AMBIENT_VOLUME = 0.3


@dataclass(frozen=True)
class Track:
    name: str
    duration: float
    size_mb: float

    def as_dict(self) -> dict:
        return {"name": self.name, "duration": round(self.duration, 1), "size_mb": round(self.size_mb, 1)}


def is_music(name: str | None) -> bool:
    return PurePath(name or "").suffix.lower() in MUSIC_EXTS


def track_name(filename: str | None) -> str:
    """El nombre con el que se guarda: sin carpetas, y solo formatos de audio."""
    name = PurePath(filename or "").name.strip()
    if not name or name.startswith("."):
        raise ValidationError("El archivo de música no tiene nombre.")
    if not is_music(name):
        raise ValidationError(f"Formato de música no admitido. Usa {', '.join(MUSIC_EXTS)}.")
    return name


def validate_volume(volume: object) -> float:
    if isinstance(volume, bool) or not isinstance(volume, (int, float)) or not 0 <= volume <= 1:
        raise ValidationError("El volumen de la música va de 0 a 1.")
    return float(volume)


def voiced_intervals(words: Iterable[Mapping], gap: float = JOIN_GAP) -> list[tuple[float, float]]:
    """Los tramos en que alguien habla, a partir de las marcas de cada palabra."""
    spans = sorted((float(w["start"]), float(w["end"])) for w in words if w.get("end", 0) > w.get("start", 0))
    merged: list[list[float]] = []
    for start, end in spans:
        if merged and start - merged[-1][1] <= gap:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return [(a, b) for a, b in merged]


def duck_envelope(
    voiced: Sequence[tuple[float, float]],
    duration: float,
    volume: float,
    ratio: float = DUCKED_RATIO,
    ramp: float = RAMP,
) -> list[tuple[float, float]]:
    """
    Puntos (segundo, ganancia) de la música, en orden, para interpolar entre
    ellos: `volume` en los silencios y `volume * ratio` mientras hay voz, con
    rampas de `ramp` segundos que empiezan antes de que hable y terminan
    después, para que la primera palabra ya suene limpia.
    """
    low = volume * ratio
    points: list[tuple[float, float]] = [(0.0, volume)]
    for start, end in voiced:
        down_from, down_to = max(0.0, start - ramp), max(0.0, start)
        up_from, up_to = min(duration, end), min(duration, end + ramp)
        if down_from <= points[-1][0]:
            # Pegado al tramo anterior (o al principio): ya está abajo o baja ya.
            points.append((max(points[-1][0], down_to), low))
        else:
            points += [(down_from, volume), (down_to, low)]
        points += [(up_from, low), (up_to, volume)]
    points.append((max(duration, points[-1][0]), volume))
    # Sin retrocesos: el interpolador exige segundos crecientes.
    clean: list[tuple[float, float]] = []
    for t, g in points:
        if clean and t <= clean[-1][0]:
            clean[-1] = (clean[-1][0], g)
        else:
            clean.append((t, g))
    return clean
