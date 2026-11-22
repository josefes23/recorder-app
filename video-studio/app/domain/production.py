"""
Ajustes de producción de un video: formato, duración, sonido y transiciones.

Hasta ahora solo había un caso, el reel vertical de 30 a 45 segundos. Un
cortometraje puede ser horizontal y durar minutos, y eso cambia el tamaño del
cuadro, los subtítulos, cómo se encuadran las imágenes y cuánto se escribe.
Las mismas reglas viven en `web/domain/production.ts`.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from pathlib import PurePath

from app.domain.errors import ValidationError
from app.domain.finish import Finish, validate_finish
from app.domain.script import WORDS_PER_SECOND
from app.domain.transition import Transition, validate_transition


@dataclass(frozen=True)
class Format:
    id: str
    name: str
    width: int
    height: int
    #: Alto de la banda de subtítulos del motor (CAPTION_BOX_H).
    caption_box_h: int
    #: Cómo se le pide al generador que componga la imagen.
    framing: str
    #: Orientación de los clips de stock que encajan.
    stock_orientation: str
    #: Tamaño del fotograma de vista previa.
    preview_size: tuple[int, int]
    #: Lo que se le dice al guion visual sobre el cuadro.
    storyboard_rule: str
    #: La portada: 1080x1920 para reels, la miniatura de YouTube en horizontal.
    cover_size: tuple[int, int] = (1080, 1920)
    #: Ancho de la portada en la cuadrícula de la biblioteca: el doble de lo que
    #: ocupa en pantalla, para que se vea nítida en una pantalla retina.
    poster_width: int = 360

    @property
    def vertical(self) -> bool:
        return self.height > self.width


VERTICAL = Format(
    id="9:16",
    name="Vertical 9:16",
    width=1080,
    height=1920,
    caption_box_h=400,
    # Los subtítulos ocupan una banda que empieza a media pantalla: las caras arriba.
    framing="Imagen vertical, con el motivo principal y las caras en la mitad superior del encuadre.",
    stock_orientation="portrait",
    preview_size=(405, 720),
    storyboard_rule=(
        "El video es vertical y los subtítulos ocupan la franja central baja: "
        "el motivo principal y las caras van en la mitad superior."
    ),
)

HORIZONTAL = Format(
    id="16:9",
    name="Horizontal 16:9",
    width=1920,
    height=1080,
    caption_box_h=240,
    # Los subtítulos van abajo, como en el cine: el motivo en los dos tercios de arriba.
    framing="Imagen horizontal, con el motivo principal y las caras en los dos tercios superiores del encuadre.",
    stock_orientation="landscape",
    preview_size=(720, 405),
    storyboard_rule=(
        "El video es horizontal, como una película, y los subtítulos van abajo: "
        "el motivo principal y las caras van en los dos tercios superiores."
    ),
    cover_size=(1280, 720),
    poster_width=480,
)

FORMATS = {f.id: f for f in (VERTICAL, HORIZONTAL)}

#: Subtítulos que encajan en horizontal: más bajos, de menos líneas y más anchos.
HORIZONTAL_CAPTIONS = {"font_size": 64, "y_ratio": 0.74, "max_lines": 2, "max_chars": 42}


def format_by_id(format_id: str | None) -> Format:
    if not format_id:
        return VERTICAL
    found = FORMATS.get(format_id.strip())
    if found is None:
        raise ValidationError(f"Formato desconocido: «{format_id}». Usa 9:16 o 16:9.")
    return found


@dataclass(frozen=True)
class Length:
    id: str
    name: str
    #: Palabras que se le piden al redactor, y segundos de voz que salen.
    words: tuple[int, int]
    seconds: tuple[int, int]
    #: Tope de escenas del guion visual; `None`, sin tope: salen las que pida el
    #: guion, como mucho una por frase.
    max_scenes: int | None
    #: Cómo se le cuenta al redactor la forma del guion.
    structure: str
    #: Qué escribe el redactor: «Reels y Shorts», «cortometrajes».
    kind: str
    #: Un video corto de redes (gancho y llamada a la acción) y no una historia.
    reel_like: bool = False


REEL = Length(
    id="reel",
    name="Reel (45–60 s)",
    words=(120, 160),
    seconds=(45, 60),
    # Sin tope: las imágenes son las que pida el guion. En un minuto, con
    # escenas de 3 a 9 s, la respuesta del guion visual sigue cabiendo.
    max_scenes=None,
    structure=(
        "ocho piezas, en este orden, que retienen hasta el final.\n"
        "  1. Gancho: en los tres primeros segundos le habla por su situación o su dolor a una\n"
        "     persona concreta (sin saludo, sin «hola, soy…») y rompe con lo que venía viendo.\n"
        "  2. Introducción: promete algo concreto si se queda («las tres causas», «en un minuto»).\n"
        "  3. Cuerpo uno: algo útil que no sabía, valioso por sí solo.\n"
        "  4. Bucle abierto: una frase que deja una pregunta en el aire («pero esa es la fácil»).\n"
        "  5. Cuerpo dos: cierra ese bucle y entrega otro valor.\n"
        "  6. Bucle abierto: repite el mecanismo y sube la apuesta.\n"
        "  7. Cuerpo tres: cierra el último bucle con lo más fuerte del video, no con lo más flojo.\n"
        "  8. Llamada a la acción: un solo paso, concreto y fácil, y solo aquí, al final.\n"
        "  Cada bucle se paga en el cuerpo siguiente: un bucle que no se cierra es clickbait.\n"
        "  Si solo hay material para dos cuerpos, usa un único bucle."
    ),
    kind="Reels y Shorts",
    reel_like=True,
)

SHORT_FILM = Length(
    id="corto",
    name="Cortometraje (2–5 min)",
    words=(330, 780),
    seconds=(120, 290),
    # Más escenas que esto desborda la respuesta del guion visual y el bolsillo:
    # cada escena es una imagen (y quizá un clip animado).
    max_scenes=30,
    structure=(
        "una historia con planteamiento, nudo y desenlace: un gancho al principio, "
        "un conflicto que crece y un cierre que se recuerde."
    ),
    kind="cortometrajes",
)

LENGTHS = {length.id: length for length in (REEL, SHORT_FILM)}

#: Una duración a medida: los segundos que se quieren, p. ej. «90s» o «300s».
#: Sigue siendo un texto para viajar por los mismos campos `length` de siempre.
CUSTOM_LENGTH = re.compile(r"^(\d{1,4})s$")
MIN_CUSTOM_SECONDS = 20
MAX_CUSTOM_SECONDS = 600
#: Holgura a cada lado de lo pedido: la voz nunca sale al segundo exacto.
CUSTOM_TOLERANCE = 0.15
#: Un video de hasta esto se escribe como un reel; más largo, como un corto.
REEL_MAX_SECONDS = 60


def custom_length(seconds: int) -> Length:
    """Una duración elegida a mano, con las mismas medidas que los preajustes."""
    if not MIN_CUSTOM_SECONDS <= seconds <= MAX_CUSTOM_SECONDS:
        raise ValidationError(
            f"La duración debe estar entre {MIN_CUSTOM_SECONDS} segundos y "
            f"{MAX_CUSTOM_SECONDS // 60} minutos."
        )
    low = math.floor(seconds * (1 - CUSTOM_TOLERANCE))
    high = math.ceil(seconds * (1 + CUSTOM_TOLERANCE))
    base = REEL if seconds <= REEL_MAX_SECONDS else SHORT_FILM
    return Length(
        id=f"{seconds}s",
        name=f"{seconds} s",
        words=(round(low * WORDS_PER_SECOND), round(high * WORDS_PER_SECOND)),
        seconds=(low, high),
        max_scenes=None if base.max_scenes is None else max(3, min(base.max_scenes, math.ceil(seconds / 6))),
        structure=base.structure,
        kind=base.kind,
        reel_like=base.reel_like,
    )


def length_by_id(length_id: str | None) -> Length:
    if not length_id:
        return REEL
    key = length_id.strip().lower()
    found = LENGTHS.get(key)
    if found is not None:
        return found
    custom = CUSTOM_LENGTH.match(key)
    if custom:
        return custom_length(int(custom.group(1)))
    raise ValidationError(
        f"Duración desconocida: «{length_id}». Usa reel, corto o los segundos, como 90s."
    )


#: Dónde se guardan los ajustes de producción dentro del `style` de un video.
#: Así no cambia el esquema de la base: un servidor de una versión anterior la
#: sigue leyendo (ignora la clave), y «Reutilizar» la recupera.
PRODUCTION_KEY = "production"


def production_of(style: dict | None) -> dict:
    value = (style or {}).get(PRODUCTION_KEY)
    return value if isinstance(value, dict) else {}


def format_of(style: dict | None) -> Format:
    """El formato con que se hizo un video guardado; los de antes, verticales."""
    try:
        return format_by_id(production_of(style).get("format"))
    except ValidationError:
        return VERTICAL


def minutes_or_seconds(length: Length) -> str:
    low, high = length.seconds
    if high < 90:
        return f"entre {low} y {high} segundos"
    return f"entre {round(low / 60)} y {round(high / 60)} minutos"


@dataclass(frozen=True)
class Production:
    """Los ajustes de producción de un render, ya validados."""

    format: str = VERTICAL.id
    length: str = REEL.id
    #: Voz de cada personaje del diálogo; vacío = una sola voz.
    voices: dict = field(default_factory=dict)
    music: str = ""
    music_volume: float = 0.25
    ambient: bool = False
    #: Cómo entran las escenas que no eligen la suya (`domain.transition`).
    transition: Transition = field(default_factory=Transition)
    #: La toma de voz con que se renderizó (`domain.voice_take`). No la elige
    #: el usuario: la pone el render, para que «Reutilizar» recupere los
    #: tiempos reales de cada palabra.
    take: str = ""
    #: Lo que se le hace al video una vez armado (`domain.finish`): audio, color, ritmo y tarjetas.
    finish: Finish = field(default_factory=Finish)

    def as_dict(self) -> dict:
        return asdict(self)


def validate_production(data: Mapping | None) -> Production:
    """Los ajustes que llegan de la interfaz, comprobados uno a uno."""
    from app.domain.dialogue import validate_voices
    from app.domain.music import DEFAULT_VOLUME, is_music, validate_volume

    data = data or {}
    music = PurePath(str(data.get("music") or "")).name
    if music and not is_music(music):
        raise ValidationError(f"«{music}» no es una pista de la galería de música.")
    return Production(
        format=format_by_id(data.get("format")).id,
        length=length_by_id(data.get("length")).id,
        voices=validate_voices(data.get("voices")),
        music=music,
        music_volume=validate_volume(data.get("music_volume", DEFAULT_VOLUME)),
        ambient=bool(data.get("ambient")),
        transition=validate_transition(data.get("transition")),
        finish=validate_finish(data.get("finish")),
    )
