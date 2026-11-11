"""
Fondo de imagen fija con movimiento: zoom continuo y cortes de ritmo
(`domain.motion`), pintado fotograma a fotograma.

Cada fotograma recorta la imagen original con decimales y la escala al cuadro
en un solo paso (`Image.resize(box=…)`). El zoom de moviepy (`resized` con una
función del tiempo) redondea el tamaño a píxeles enteros en cada fotograma, y
en un zoom lento eso se ve como un temblor.
"""

from __future__ import annotations

from pathlib import Path

from app.domain.motion import camera_at, crop_box, plan_shots


def moving_image(path: Path, duration: float, size: tuple[int, int], seed: int = 0):
    import numpy as np
    from moviepy import VideoClip
    from PIL import Image

    with Image.open(path) as opened:
        picture = opened.convert("RGB")
    shots = plan_shots(duration, seed)

    def frame(t: float):
        zoom, fx, fy = camera_at(shots, t)
        box = crop_box(picture.size, size, zoom, (fx, fy))
        return np.asarray(picture.resize(size, Image.Resampling.BICUBIC, box=box))

    return VideoClip(frame, duration=duration)
