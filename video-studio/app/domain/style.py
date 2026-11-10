"""Estilo de los subtítulos: lo que la interfaz ajusta y el motor aplica."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import ClassVar


@dataclass(frozen=True)
class CaptionStyle:
    font_size: int = 92
    stroke: int = 8
    y_ratio: float = 0.52
    max_chars: int = 30
    max_words: int = 5
    max_lines: int = 3
    animate: bool = True

    # Suelo del autoajuste de palabras largas que hace el motor.
    AUTOFIT_FLOOR: ClassVar[int] = 52

    @classmethod
    def from_dict(cls, style: dict | None) -> CaptionStyle:
        """Completa con los valores por defecto lo que la interfaz no mande."""
        merged = {**DEFAULT_STYLE, **(style or {})}
        return cls(
            font_size=int(merged["font_size"]),
            stroke=int(merged["stroke"]),
            y_ratio=float(merged["y_ratio"]),
            max_chars=int(merged["max_chars"]),
            max_words=int(merged["max_words"]),
            max_lines=int(merged["max_lines"]),
            animate=bool(merged["animate"]),
        )

    @property
    def min_font_size(self) -> int:
        """El suelo de autoajuste no puede quedar por encima del tamaño pedido."""
        return min(self.AUTOFIT_FLOOR, self.font_size)

    def as_dict(self) -> dict:
        return asdict(self)


DEFAULT_STYLE: dict = CaptionStyle().as_dict()
