"""Generadores de imagen: cómo se le pide una escena a cada API."""

from __future__ import annotations


def sniff_extension(data: bytes, mime: str | None = None) -> str:
    """
    La extensión según los primeros bytes, que mandan sobre lo que diga la
    cabecera: hay APIs que anuncian PNG y devuelven JPEG.
    """
    if data.startswith(b"\x89PNG"):
        return ".png"
    if data.startswith(b"\xff\xd8"):
        return ".jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return {"image/png": ".png", "image/webp": ".webp"}.get((mime or "").lower(), ".jpg")


def compact(text: str, limit: int = 200) -> str:
    """Un cuerpo de error en una línea, para enseñarlo en la interfaz."""
    return " ".join((text or "").split())[:limit]
