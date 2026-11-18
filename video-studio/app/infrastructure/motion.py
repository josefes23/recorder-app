"""
Fondo de imagen fija con movimiento: zoom continuo y cortes de ritmo
(`domain.motion`), pintado fotograma a fotograma.

Cada fotograma recorta la imagen original con decimales y la escala al cuadro
en un solo paso (`Image.resize(box=…)`). El zoom de moviepy (`resized` con una
función del tiempo) redondea el tamaño a píxeles enteros en cada fotograma, y
en un zoom lento eso se ve como un temblor.

Entre un encuadre y el siguiente va la transición de la escena
(`domain.transition`); con un corte, el salto de siempre.
"""

from __future__ import annotations

from pathlib import Path

from app.domain.motion import camera_on, crop_box, plan_shots
from app.domain.transition import Transition, moment, plan_changes
from app.infrastructure.transitions import blend_frames


def moving_image(
    path: Path, duration: float, size: tuple[int, int], seed: int = 0, transition: Transition | None = None,
):
    import numpy as np
    from moviepy import VideoClip
    from PIL import Image

    with Image.open(path) as opened:
        picture = opened.convert("RGB")
    shots = plan_shots(duration, seed)
    bounds = [shot.start for shot in shots] + [duration]
    changes = plan_changes(bounds, [transition or Transition()] * (len(shots) - 1))

    def paint(index: int, t: float):
        zoom, fx, fy = camera_on(shots[index], t)
        box = crop_box(picture.size, size, zoom, (fx, fy))
        return np.asarray(picture.resize(size, Image.Resampling.BICUBIC, box=box))

    def frame(t: float):
        index, blend = moment(changes, t)
        if blend is None:
            return paint(index, t)
        return blend_frames(blend, paint(index, t), paint(index + 1, t))

    return VideoClip(frame, duration=duration)
