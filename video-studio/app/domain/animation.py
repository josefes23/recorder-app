"""
Escenas animadas: de una imagen fija de la galería, un clip corto de video.

Un modelo de imagen a video (Gemini Omni Flash) toma la imagen de la escena
como primer fotograma e inventa el movimiento. El clip entra en la galería
como un fondo más (.mp4) y el motor ya sabe usarlo: le quita el audio y lo
repite si el tramo dura más que el clip.

Cada segundo animado se paga (no hay nivel gratuito), así que el clip se pide
del largo justo del tramo, redondeado hacia arriba.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from app.domain.errors import ValidationError
from app.domain.illustration import DEFAULT_STYLE, VisualGuide, as_sentence, cast_in

#: Límites del modelo: segundos enteros entre 3 y 15.
MIN_SECONDS = 3
MAX_SECONDS = 15

#: Vertical, como el resto del video.
ASPECT_RATIO = "9:16"


@dataclass(frozen=True)
class VideoProvider:
    id: str
    name: str
    #: El modelo por defecto; `model_env` en el .env lo cambia sin tocar código.
    model: str
    model_env: str
    #: La clave que usa: la misma que el generador de imágenes de ese proveedor.
    key_env: str
    resolution: str
    #: Precio de referencia por segundo a esa resolución, para estimar en la
    #: interfaz. Lo fija Google y cambia: es orientativo, no una factura.
    usd_per_second: float


#: Gemini Omni 1.2 Flash, 720p: unos 0,07 US$ por segundo (precio de Google
#: del 16-11-2026). Sale a 720x1280 y el motor lo escala a 1080x1920.
GEMINI_OMNI = VideoProvider(
    id="google",
    name="Gemini Omni Flash",
    model="gemini-omni-1.2-flash",
    model_env="GEMINI_VIDEO_MODEL",
    key_env="GEMINI_API_KEY",
    resolution="720p",
    usd_per_second=0.07,
)

VIDEO_PROVIDERS = (GEMINI_OMNI,)


@dataclass(frozen=True)
class GeneratedClip:
    """Los bytes de un clip recién generado."""

    data: bytes
    extension: str = ".mp4"


def clip_seconds(span: float) -> int:
    """Los segundos que se piden para cubrir un tramo: hacia arriba, entre 3 y 15."""
    # El margen evita que 6.0000001 (sumas de flotantes) se pida como 7.
    return max(MIN_SECONDS, min(MAX_SECONDS, math.ceil(span - 1e-6)))


def validate_seconds(seconds: object) -> int:
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or seconds != int(seconds):
        raise ValidationError("La duración del clip va en segundos enteros.")
    if not MIN_SECONDS <= seconds <= MAX_SECONDS:
        raise ValidationError(f"El clip tiene que durar entre {MIN_SECONDS} y {MAX_SECONDS} segundos.")
    return int(seconds)


def new_animation_key() -> str:
    return f"an-{uuid4().hex[:10]}"


def animation_name(source: str, job_key: str) -> str:
    """
    «ia-finanzas_37.jpg» → «ia-finanzas_37-mov-a1b2c3.mp4». Lleva el nombre de
    la imagen, así que en la galería el clip queda junto a ella; el sufijo
    sale de la clave del trabajo, y volver a animarla no pisa el clip anterior.
    """
    return f"{Path(source).stem}-mov-{job_key.rsplit('-', 1)[-1][:6]}.mp4"


#: El primer fotograma manda: sin esto el modelo toma la imagen como mera
#: referencia y reinventa la escena.
FIRST_FRAME = (
    "Anima esta imagen como un plano corto de película. La imagen es el primer fotograma: "
    "conserva el encuadre, las personas, los objetos, la luz y el estilo."
)
#: El movimiento cuando la escena no dice el suyo.
MOTION = "Movimiento natural y sutil de las personas y del ambiente; la cámara se mueve despacio."
#: Vaya con el movimiento de la escena o con el de siempre: el clip cubre un
#: tramo entero, y un corte dentro de él se vería como un salto.
ONE_SHOT = "Un solo plano, sin cortes."
#: El audio del clip no se usa (la voz va aparte): mejor que no hable nadie.
QUIET = "Sin diálogos ni voces, sin música: solo sonido ambiente. No agregues textos, letras ni subtítulos."

#: Lo que se mueve en una escena cabe en una frase; esto solo frena lo desbocado.
MOTION_LIMIT = 300


def validate_motion(motion: str | None) -> str:
    """El movimiento de una escena, en una línea. Vacío vale: entonces va `MOTION`."""
    text = " ".join((motion or "").split())
    if len(text) > MOTION_LIMIT:
        raise ValidationError(f"El movimiento es demasiado largo: déjalo por debajo de {MOTION_LIMIT} caracteres.")
    return text


def animation_prompt(description: str, guide: VisualGuide | None = None, motion: str = "") -> str:
    """
    El encargo para el modelo de video. Omni no admite prompts negativos como
    parámetro, pero sí entiende exclusiones dichas en el texto («sin…»).

    `motion` es lo que se mueve en esa escena —lo propone el guion visual o lo
    escribe el usuario—; sin él, un movimiento sutil que vale para cualquiera.
    """
    guide = guide or VisualGuide()
    lines = [FIRST_FRAME]
    if description.strip():
        lines.append(f"Qué pasa: {as_sentence(description)}")
        lines += [f"{c.name}: {as_sentence(c.traits)}" for c in cast_in(description, guide.characters)]
    lines.append(f"Estilo: {as_sentence(guide.look or DEFAULT_STYLE)}")
    lines.append(f"Movimiento: {as_sentence(motion)} {ONE_SHOT}" if motion.strip() else f"{MOTION} {ONE_SHOT}")
    lines.append(QUIET)
    return "\n".join(lines)
