"""El video como ficha del historial y como encargo de render."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from enum import StrEnum


class VideoStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


ACTIVE_STATUSES = frozenset({VideoStatus.QUEUED, VideoStatus.RUNNING})


@dataclass(frozen=True)
class NewVideo:
    """Lo que hace falta para abrir una ficha en el historial."""

    topic: str
    script: str
    voice: str
    style: dict
    scenes: list[dict]
    #: Título, diseño e imagen de la portada (`domain.cover`); {} si no llegó.
    cover: dict = field(default_factory=dict)
    #: El texto con que se publica (`domain.description`); vacío si no se escribió.
    description: str = ""


@dataclass(frozen=True)
class Video:
    id: int
    topic: str
    script: str
    voice: str
    style: dict
    scenes: list
    filename: str | None
    duration: float | None
    size_mb: float | None
    captions: int | None
    status: str
    error: str | None
    created_at: str
    #: Vacía en los videos de antes de que hubiera portadas.
    cover: dict = field(default_factory=dict)
    description: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class RenderSpec:
    """Todo lo que el worker necesita para renderizar sin consultar nada más."""

    topic: str
    script: str
    voice: str
    rate: str
    pitch: str
    style: dict = field(default_factory=dict)
    scenes: list[dict] = field(default_factory=list)
    output: str = ""
    keep_audio: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> RenderSpec:
        return cls(
            topic=data.get("topic", ""),
            script=data.get("script", ""),
            voice=data.get("voice", ""),
            rate=data.get("rate", ""),
            pitch=data.get("pitch", ""),
            style=data.get("style") or {},
            scenes=data.get("scenes") or [],
            output=data.get("output", ""),
            keep_audio=bool(data.get("keep_audio", False)),
        )

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class RenderResult:
    output: str
    duration: float | None
    size_mb: float | None
    captions: int | None

    @classmethod
    def from_dict(cls, data: dict) -> RenderResult:
        return cls(
            output=data["output"],
            duration=data.get("duration"),
            size_mb=data.get("size_mb"),
            captions=data.get("captions"),
        )


def slugify(text: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:60] or "video"


def output_filename(topic: str | None, stamp: str) -> str:
    return f"{slugify(topic)}_{stamp}.mp4"
