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
    #: «9:16» (vertical, reels) o «16:9» (horizontal). Ver `domain.formats`.
    format: str = "9:16"
    #: Voz de cada personaje del diálogo; vacío = el guion se lee con una sola voz.
    voices: dict = field(default_factory=dict)
    #: Pista de la galería de música, o vacío para ninguna.
    music: str = ""
    music_volume: float = 0.25
    #: Mezclar debajo de la voz el sonido de los clips (los animados lo traen).
    ambient: bool = False
    #: La transición por defecto: la de las escenas que no eligen la suya.
    transition: dict = field(default_factory=dict)
    #: La toma de voz que usa: si ya está generada, el render no sintetiza otra.
    take: str = ""
    #: Dónde están las tomas: la carpeta del servidor que encarga el render.
    takes_dir: str = ""
    #: El acabado (`domain.finish`): audio, color, ritmo y tarjetas. Vacío = sin retoques.
    finish: dict = field(default_factory=dict)

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
            format=data.get("format") or "9:16",
            voices=data.get("voices") or {},
            music=data.get("music") or "",
            music_volume=float(data.get("music_volume", 0.25)),
            ambient=bool(data.get("ambient", False)),
            transition=data.get("transition") or {},
            take=data.get("take") or "",
            takes_dir=data.get("takes_dir") or "",
            finish=data.get("finish") or {},
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
