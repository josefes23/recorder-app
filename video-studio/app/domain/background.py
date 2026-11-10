"""Un clip o imagen de la galería, listo para usarse como fondo de escena."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import PurePath
from typing import Literal

VIDEO_EXTS = frozenset({".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"})
IMAGE_EXTS = frozenset({".jpg", ".jpeg", ".png", ".webp", ".bmp"})
SUPPORTED_EXTS = VIDEO_EXTS | IMAGE_EXTS

# Los clips descargados por lotes llegan como «tema_1», «tema_2»… y se agrupan.
_SERIES = re.compile(r"_\d+$")

Kind = Literal["image", "video"]


def extension_of(name: str | None) -> str:
    return PurePath(name or "").suffix.lower()


def is_supported(name: str | None) -> bool:
    return extension_of(name) in SUPPORTED_EXTS


def is_image(name: str | None) -> bool:
    return extension_of(name) in IMAGE_EXTS


def kind_of(name: str) -> Kind:
    return "image" if is_image(name) else "video"


def group_of(stem: str) -> str:
    return _SERIES.sub("", stem)


@dataclass(frozen=True)
class Background:
    name: str
    stem: str
    group: str
    kind: Kind
    duration: float
    size_mb: float
    thumb: str | None

    @classmethod
    def describe(cls, name: str, duration: float, size_bytes: int, thumb: str | None) -> Background:
        """Construye la ficha a partir de lo que se sabe del archivo."""
        stem = PurePath(name).stem
        return cls(
            name=name,
            stem=stem,
            group=group_of(stem),
            kind=kind_of(name),
            duration=duration,
            size_mb=round(size_bytes / 1e6, 1),
            thumb=thumb,
        )

    def as_dict(self) -> dict:
        return asdict(self)
