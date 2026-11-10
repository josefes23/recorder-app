"""Bloques de subtítulo tal como los produce el motor: start, duration, text."""

from __future__ import annotations


def clip_to_duration(captions: list[dict], duration: float) -> list[dict]:
    """Descarta los bloques que empiezan después del audio y recorta el último."""
    kept = [dict(c) for c in captions if c["start"] < duration]
    if kept:
        last = kept[-1]
        last["duration"] = min(last["duration"], duration - last["start"])
    return kept
