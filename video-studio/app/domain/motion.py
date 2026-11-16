"""
Movimiento de las escenas con imagen fija: zoom continuo y cortes de ritmo.

Una imagen quieta seis segundos se nota quieta, y el motor solo le aplicaba un
acercamiento del 7 % repartido en toda la escena: casi no se veía. Aquí cada
escena se parte en planos de 3 a 4 segundos sobre la misma imagen, como haría
un montador con una foto:

- dentro de cada plano, un acercamiento lento y constante (ZOOM_PER_SECOND);
- entre un plano y el siguiente, un corte a otro encuadre: el primero abierto,
  después uno cerrado sobre el motivo, después uno intermedio, ligeramente a un
  lado y al otro. El salto de escala (más del 10 %) se lee como corte buscado,
  no como un tropiezo.

Los encuadres miran a la mitad superior (FOCUS_Y): ahí pide el guion visual las
caras, lejos de los subtítulos.

Aquí solo se decide dónde está la cámara en cada instante. Pintar los
fotogramas es de `infrastructure.motion`.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

#: Ningún plano pasa de esto: más tiempo en el mismo encuadre y el ojo se acostumbra.
MAX_SHOT_SECONDS = 4.0
#: Ni baja de esto: un corte cada dos segundos sobre la misma foto marea.
MIN_SHOT_SECONDS = 2.5

#: Acercamiento continuo dentro de cada plano: un 2 % por segundo se ve sin
#: llamar la atención; en un plano de 3 s son 6 puntos.
ZOOM_PER_SECOND = 0.02

#: Escala con la que arranca cada tipo de plano, sobre la imagen ya ajustada al
#: cuadro (1.0 = la imagen entera). Entre el final de un plano abierto (1,06 en
#: 3 s) y el principio de uno cerrado (1,18) hay un salto que se lee como corte.
WIDE, MEDIUM, CLOSE = 1.0, 1.10, 1.18

#: Altura a la que miran los encuadres cerrados, de 0 (arriba) a 1 (abajo): la
#: mitad superior, donde van las caras (FRAMING en `domain.illustration`).
FOCUS_Y = 0.40

#: Una imagen bastante más alta que el cuadro (una vertical en un video
#: horizontal) se encuadra más arriba: ahí van las caras.
TALL_SOURCE = 1.5
TALL_FOCUS_Y = 0.25
#: Cuánto se desplazan a un lado los encuadres cerrados, y cuánto derivan
#: dentro del plano: lo justo para que el corte no sea solo un zoom.
SIDE_OFFSET = 0.06
DRIFT = 0.025


@dataclass(frozen=True)
class Shot:
    """Un plano: dónde está la cámara al empezar y al acabar."""

    start: float
    duration: float
    zoom_from: float
    zoom_to: float
    #: Punto al que mira, en fracciones del cuadro: (0.5, 0.5) es el centro.
    focus_from: tuple[float, float]
    focus_to: tuple[float, float]

    @property
    def end(self) -> float:
        return self.start + self.duration


def shot_count(duration: float) -> int:
    """Cuántos planos caben: los menos posibles sin pasar de MAX_SHOT_SECONDS ni bajar de MIN_SHOT_SECONDS."""
    count = max(1, math.ceil(duration / MAX_SHOT_SECONDS))
    while count > 1 and duration / count < MIN_SHOT_SECONDS:
        count -= 1
    return count


def plan_shots(duration: float, seed: int = 0) -> list[Shot]:
    """
    Los planos de una escena de `duration` segundos. La misma semilla da los
    mismos planos: un video renderizado dos veces sale igual.
    """
    if duration <= 0:
        return []
    count = shot_count(duration)
    length = duration / count
    rng = random.Random(seed)
    side = rng.choice((-1, 1))
    # Abierto para situar; después se alterna cerrado e intermedio.
    sizes = [WIDE] + [CLOSE if i % 2 else MEDIUM for i in range(1, count)]

    shots: list[Shot] = []
    for i, zoom in enumerate(sizes):
        if zoom == WIDE:
            focus = (0.5, 0.5)
            drift = (0.0, 0.0)
        else:
            side = -side
            focus = (0.5 + side * SIDE_OFFSET, FOCUS_Y)
            drift = (-side * DRIFT, 0.0)
        shots.append(Shot(
            start=i * length,
            duration=length,
            zoom_from=zoom,
            zoom_to=zoom + ZOOM_PER_SECOND * length,
            focus_from=focus,
            focus_to=(focus[0] + drift[0], focus[1] + drift[1]),
        ))
    return shots


def shot_at(shots: list[Shot], t: float) -> Shot:
    for shot in shots:
        if t < shot.end:
            return shot
    return shots[-1]


def camera_at(shots: list[Shot], t: float) -> tuple[float, float, float]:
    """(zoom, foco_x, foco_y) en el instante `t`, con movimiento uniforme dentro del plano."""
    shot = shot_at(shots, t)
    k = min(max((t - shot.start) / shot.duration, 0.0), 1.0) if shot.duration > 0 else 0.0
    zoom = shot.zoom_from + (shot.zoom_to - shot.zoom_from) * k
    fx = shot.focus_from[0] + (shot.focus_to[0] - shot.focus_from[0]) * k
    fy = shot.focus_from[1] + (shot.focus_to[1] - shot.focus_from[1]) * k
    return zoom, fx, fy


def crop_box(
    source: tuple[int, int], frame: tuple[int, int], zoom: float, focus: tuple[float, float]
) -> tuple[float, float, float, float]:
    """
    El rectángulo de la imagen original (izquierda, arriba, derecha, abajo, en
    píxeles con decimales) que se ve en el cuadro. Primero el mayor rectángulo
    con la forma del cuadro que cabe en la imagen —como «cover»—, después se
    estrecha `zoom` veces alrededor del foco, sin salirse nunca de la imagen.
    Los decimales importan: redondear a píxeles enteros hace temblar el zoom.
    """
    sw, sh = source
    fw, fh = frame
    # Una imagen vertical en un cuadro apaisado deja fuera dos tercios del alto,
    # y las imágenes generadas ponen las caras en la mitad superior (FRAMING en
    # `domain.illustration`): se mira más arriba en vez de al centro.
    if sh / sw > (fh / fw) * TALL_SOURCE:
        focus = (focus[0], min(focus[1], TALL_FOCUS_Y))
    cover = min(sw / fw, sh / fh)
    w, h = fw * cover / zoom, fh * cover / zoom
    left = min(max(focus[0] * sw - w / 2, 0.0), sw - w)
    top = min(max(focus[1] * sh - h / 2, 0.0), sh - h)
    # Pegado a un borde, el redondeo puede dejar -1e-13: se fija al borde exacto.
    return (max(left, 0.0), max(top, 0.0), min(left + w, sw), min(top + h, sh))


def scene_seed(index: int, name: str) -> int:
    """Una semilla estable por escena: cambia de una a otra, no de un render al siguiente."""
    return index * 7919 + sum(ord(c) for c in name)
