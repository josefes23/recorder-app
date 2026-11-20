"""El guion como texto: limpieza, duración estimada y rango objetivo."""

from __future__ import annotations

import re
from dataclasses import dataclass

# 2,7 palabras/s medido con las voces es-* a --rate +8%.
WORDS_PER_SECOND = 2.7

# Un Reel de 45–60 s de voz, con un poco de holgura a cada lado.
TARGET_SECONDS = (43.0, 63.0)

_MARKUP = re.compile(r"[*_#`\[\]]")
_SPACES = re.compile(r"\s+")


def clean_script(raw: str | None) -> str:
    """Quita marcas de markdown y deja un solo espacio entre palabras."""
    text = _MARKUP.sub(" ", raw or "")
    return _SPACES.sub(" ", text).strip()


def word_count(text: str | None) -> int:
    return len(clean_script(text).split())


def estimate_seconds(text: str | None) -> float:
    return word_count(text) / WORDS_PER_SECOND


def in_target_range(seconds: float) -> bool:
    low, high = TARGET_SECONDS
    return low <= seconds <= high


@dataclass(frozen=True)
class ScriptEstimate:
    seconds: float
    words: int
    in_range: bool


def estimate(text: str | None) -> ScriptEstimate:
    seconds = estimate_seconds(text)
    return ScriptEstimate(round(seconds, 1), word_count(text), in_target_range(seconds))
