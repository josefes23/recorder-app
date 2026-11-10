"""La línea de tiempo de fondos: en qué segundo entra cada uno."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass

# Un tramo más corto que esto no aporta nada y rompe la concatenación.
MIN_SPAN_SECONDS = 0.05


@dataclass(frozen=True)
class Scene:
    background: str | None = None
    start: float = 0.0

    @classmethod
    def from_dict(cls, data: dict | None) -> Scene:
        data = data or {}
        return cls(background=data.get("background") or None, start=float(data.get("start") or 0.0))

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Span:
    """Un fondo ocupando un tramo concreto del video."""

    background: str
    start: float
    end: float

    @property
    def duration(self) -> float:
        return self.end - self.start


def timeline_spans(scenes: Iterable[Scene], duration: float) -> list[Span]:
    """Convierte las escenas en tramos consecutivos que cubren el video.

    Las escenas sin fondo se ignoran; la primera arranca siempre en cero aunque
    el usuario la haya puesto más tarde; cada tramo dura hasta la siguiente o
    hasta el final del audio. Si no queda ninguna, la lista vacía le dice al
    motor que use su fondo procedural.
    """
    usable = sorted((s for s in scenes if s.background), key=lambda s: s.start)
    spans: list[Span] = []
    for i, scene in enumerate(usable):
        start = 0.0 if i == 0 else scene.start
        end = usable[i + 1].start if i + 1 < len(usable) else duration
        end = min(end, duration)
        if end - start <= MIN_SPAN_SECONDS:
            continue
        spans.append(Span(scene.background or "", start, end))
    return spans
