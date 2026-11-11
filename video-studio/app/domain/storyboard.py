"""
Guion visual: qué imagen acompaña a cada escena, decidido de una vez para todo
el video.

El generador de imágenes pinta cada escena por separado y sin ver el guion. Con
solo la frase de la voz, dibuja la frase —letras incluidas— o se inventa un
personaje distinto en cada imagen. Por eso, antes de pintar, el modelo del
guion hace de director de arte: fija un estilo común, un reparto con rasgos
que no cambian —personas, animales, objetos, lugares— y lo que se ve en cada
escena (`illustration.VisualGuide`). Si hay elementos guardados de otros
videos (`domain.saved_characters`), los reutiliza en vez de inventar otros.

Aquí viven el encargo y las reglas de la respuesta; hablar con el modelo es de
`infrastructure.llm`, como con el guion.
"""

from __future__ import annotations

import json
import secrets
from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.errors import WriterError
from app.domain.illustration import (
    DEFAULT_KIND,
    DEFAULT_STYLE,
    KINDS,
    LOOK_LIMIT,
    MAX_CHARACTERS,
    NAME_LIMIT,
    TRAITS_LIMIT,
    Beat,
    Character,
    VisualGuide,
    fold,
)
from app.domain.script import clean_script
from app.domain.writer import strip_reasoning

#: Lo que se ve en una escena. El encargo pide de 25 a 60 palabras; esto solo
#: recorta lo que llegue desbocado.
SCENE_LIMIT = 700

SYSTEM_PROMPT = """Eres director de arte de videos cortos verticales (Reels, Shorts, TikTok). Recibes el guion de un video ya dividido en escenas y decides qué imagen acompaña a cada una.

Un modelo de texto a imagen pintará cada escena por separado. No ve el guion ni las otras escenas: solo lee lo que tú escribas. Tu trabajo es que todas las imágenes cuenten la misma historia y parezcan del mismo video.

1. Estilo común ("look"): técnica, paleta de color, luz, óptica y textura, en una o dos frases. Parte del estilo que pida el usuario y concrétalo. Si todo el video ocurre en la misma época y lugar, inclúyelos; si el guion salta de época o de lugar, deja eso para cada escena.

2. Elementos que se repiten ("characters"): cada persona, animal, objeto (una máquina, un juguete, un juego, un vehículo) o lugar que aparezca en más de una escena, con un nombre corto que lo identifique, su tipo ("kind": "persona", "animal", "objeto" o "lugar") y sus rasgos fijos ("traits"). En una persona: edad, complexión, tono de piel, cara, pelo, vello facial y ropa con sus colores y materiales. En lo demás: forma, tamaño, materiales, colores y lo que lo distingue. Que dos no puedan confundirse. Si es una figura conocida —histórica, religiosa o de ficción—, descríbela como la muestra su iconografía habitual. Como mucho seis; puede no haber ninguno.
- Si recibes elementos que ya están en el video, mantén los que encajen con este guion, con sus nombres, tipos y rasgos exactos; los que sean de otro tema, déjalos fuera.
- Si recibes elementos guardados de otros videos, usa los que encajen con el guion —con su nombre exacto, sin cambiar sus rasgos— antes de inventar otros parecidos. Los que no encajen, ignóralos.

3. Una imagen por escena ("scenes"): lo que se ve, concreto y literal: quién, haciendo qué, dónde, con qué luz y desde qué plano. Entre 25 y 60 palabras.
- Nombra a cada elemento con su nombre exacto y no vuelvas a describirlo: sus rasgos se añaden solos. Lo que salga en una sola escena se describe ahí mismo.
- Las frases abstractas («no lo dejes para mañana», «tu vida cambia») se cuentan con un momento visible: un gesto, una acción, un lugar.
- Las escenas siguen un hilo, como los planos de una película: si alguien empieza algo, las siguientes lo continúan o muestran su consecuencia.
- El modelo dibuja como letras cualquier palabra que lea como texto. No cites frases del guion ni pongas en la imagen carteles, letreros, libros abiertos, pantallas, pancartas u otros objetos con letras. Describe solo lo que se ve, nunca lo que no debe aparecer.
- El generador tiene un filtro que bloquea la imagen entera si ve cuerpos mojados o con poca ropa, heridas o violencia. Cuéntalo con planos que no los muestren: ropa seca, un plano más abierto, el gesto o la cara en vez del cuerpo.
- El video es vertical y los subtítulos ocupan la franja central baja: el motivo principal y las caras van en la mitad superior.

Responde solo con un objeto JSON, sin markdown ni comentarios, todo en español:
{"look": "...", "characters": [{"name": "...", "kind": "persona", "traits": "..."}], "scenes": [{"n": 1, "description": "..."}]}
Una entrada en "scenes" por cada escena recibida, con su mismo número."""


@dataclass(frozen=True)
class StoryboardScene:
    #: Segundo en el que entra: lo fija el reparto del guion, no el modelo.
    start: float
    #: Lo que dice la voz en ese tramo.
    text: str
    #: Lo que se ve. Es lo que el usuario edita y lo que se pinta.
    description: str

    def as_dict(self) -> dict:
        return {"start": self.start, "text": self.text, "description": self.description}


@dataclass(frozen=True)
class Storyboard:
    guide: VisualGuide
    scenes: tuple[StoryboardScene, ...]

    def as_dict(self) -> dict:
        return {"guide": self.guide.as_dict(), "scenes": [s.as_dict() for s in self.scenes]}


def _listed(characters: Sequence[Character]) -> list[str]:
    return [f"- {c.name} ({c.kind}): {c.traits}" for c in characters]


def build_prompt(
    topic: str,
    style: str,
    script: str,
    beats: list[Beat],
    current: Sequence[Character] = (),
    offered: Sequence[Character] = (),
) -> str:
    """
    El encargo del guion visual. `current` es lo que ya está en el video
    —puesto a mano, traído de la biblioteca o de un guion visual anterior—;
    `offered`, lo guardado de otros videos.

    Ni lo uno ni lo otro es obligatorio: el reparto sigue en el panel al
    cambiar de guion, y un video sobre Kafka no debe arrastrar al Jesús del
    anterior. El modelo se queda con lo que encaje.
    """
    lines = [
        f"Tema: {topic.strip() or 'el del guion'}",
        f"Estilo que pide el usuario: {style.strip() or DEFAULT_STYLE}",
    ]
    if current:
        lines += ["", "Elementos que ya están en el video (mantén los que encajen):", *_listed(current)]
    if offered:
        lines += ["", "Elementos guardados de otros videos (usa los que encajen):", *_listed(offered)]
    lines += [
        "",
        "Guion completo:",
        clean_script(script),
        "",
        f"Escenas ({len(beats)}):",
    ]
    lines += [f"{n}. {beat.text}" for n, beat in enumerate(beats, start=1)]
    return "\n".join(lines)


def new_seed() -> int:
    """Una por video: todas sus escenas la comparten."""
    return secrets.randbelow(2**31 - 1) + 1


def _clip(value: object, limit: int) -> str:
    """El texto en una línea, cortado por la última palabra que quepa."""
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0]


def _json_object(raw: str | None) -> dict:
    # Los modelos abiertos a veces envuelven el JSON en ```json … ``` o lo
    # preceden de su razonamiento: vale lo que haya entre la primera llave y
    # la última.
    text = strip_reasoning(raw)
    start, end = text.find("{"), text.rfind("}")
    try:
        data = json.loads(text[start : end + 1]) if 0 <= start < end else None
    except ValueError:
        data = None
    if not isinstance(data, dict):
        raise WriterError(
            "El modelo no devolvió el guion visual en el formato esperado. Vuelve a intentarlo, "
            "o cambia de modelo en «Modelo del guion»."
        )
    return data


def _number(value: object, fallback: int) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return fallback


def _cast(items: object, current: Sequence[Character], offered: Sequence[Character]) -> list[Character]:
    """
    Los elementos del guion visual. Lo que el modelo toma del video o de la
    biblioteca entra con sus rasgos y su referencia de siempre, no con lo que
    el modelo haya reescrito.
    """
    known = {fold(c.name): c for c in offered} | {fold(c.name): c for c in current}
    cast: list[Character] = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        name = _clip(item.get("name"), NAME_LIMIT)
        if not name or any(fold(c.name) == fold(name) for c in cast):
            continue
        if fold(name) in known:
            cast.append(known[fold(name)])
            continue
        traits = _clip(item.get("traits"), TRAITS_LIMIT)
        kind = str(item.get("kind") or "").strip().lower()
        if traits:
            cast.append(Character(name, traits, kind if kind in KINDS else DEFAULT_KIND))
    return cast[:MAX_CHARACTERS]


def parse_storyboard(
    raw: str | None,
    beats: list[Beat],
    seed: int,
    current: Sequence[Character] = (),
    offered: Sequence[Character] = (),
) -> Storyboard:
    """Lee la respuesta del modelo y la rechaza si le falta alguna escena."""
    data = _json_object(raw)

    look = _clip(data.get("look"), LOOK_LIMIT)
    if not look:
        raise WriterError("El guion visual llegó sin estilo. Vuelve a intentarlo.")

    characters = _cast(data.get("characters"), current, offered)

    shots: dict[int, str] = {}
    for position, item in enumerate(data.get("scenes") or [], start=1):
        if isinstance(item, dict) and (text := _clip(item.get("description"), SCENE_LIMIT)):
            shots.setdefault(_number(item.get("n"), position), text)

    missing = [n for n in range(1, len(beats) + 1) if n not in shots]
    if missing:
        raise WriterError(
            f"El guion visual llegó incompleto: faltan {len(missing)} de {len(beats)} escenas. "
            "Vuelve a intentarlo."
        )

    return Storyboard(
        VisualGuide(look, tuple(characters), seed),
        tuple(StoryboardScene(b.start, b.text, shots[n]) for n, b in enumerate(beats, start=1)),
    )
