"""
Guion visual: qué imagen acompaña a cada escena, decidido de una vez para todo
el video.

El generador de imágenes pinta cada escena por separado y sin ver el guion. Con
solo la frase de la voz, dibuja la frase —letras incluidas— o se inventa un
personaje distinto en cada imagen. Por eso, antes de pintar, el modelo del
guion hace de director de arte: fija un estilo común, un reparto con rasgos
que no cambian —personas, animales, objetos, lugares— y lo que se ve en cada
escena (`illustration.VisualGuide`). Propone también qué se mueve en cada una,
por si se anima (`animation.animation_prompt`).

También decide dónde cambia la imagen. Repartido solo por longitud
(`illustration.plan_cuts`), un tramo juntaba el final de una idea con el
principio de la siguiente —Josefo seguía en pantalla mientras la voz decía
«Segundo, el bautismo y la crucifixión»— o duraba 2 s uno y 11 s el de al
lado. El modelo recibe el guion en frases y corta donde cambia lo que debe
verse, siempre entre frases y como mucho en `MAX_SCENES` escenas.

La biblioteca de elementos guardados (`domain.saved_characters`) no se le
ofrece: lo guardado solo entra en un video si el usuario lo mete a mano, y
llega aquí con el resto del reparto. Ofrecida, el modelo traía a los mismos a
todos los videos porque «encajaban».

Aquí viven el encargo y las reglas de la respuesta; hablar con el modelo es de
`infrastructure.llm`, como con el guion.
"""

from __future__ import annotations

import json
import math
import secrets
from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.animation import MOTION_LIMIT
from app.domain.errors import WriterError
from app.domain.illustration import (
    DEFAULT_KIND,
    DEFAULT_STYLE,
    KINDS,
    LOOK_LIMIT,
    MAX_CHARACTERS,
    MAX_SCENES,
    NAME_LIMIT,
    TRAITS_LIMIT,
    Character,
    VisualGuide,
    beats_from_cuts,
    fold,
    plan_cuts,
)
from app.domain.production import REEL, VERTICAL, Format, Length
from app.domain.script import WORDS_PER_SECOND
from app.domain.writer import strip_reasoning

#: Lo que se ve en una escena. El encargo pide de 25 a 60 palabras; esto solo
#: recorta lo que llegue desbocado.
SCENE_LIMIT = 700

#: Más que esto con la misma imagen se nota parado aunque el motor la mueva.
#: Fija cuántas escenas se piden como mínimo; el encargo dice «de 3 a 9 segundos».
LONGEST_SCENE_SECONDS = 9.0

_SYSTEM_TEMPLATE = """Eres director de arte de {kind}. Recibes el guion de un video dividido en frases numeradas, decides en qué frases cambia la imagen y qué imagen acompaña a cada tramo.

Un modelo de texto a imagen pintará cada escena por separado. No ve el guion ni las otras escenas: solo lee lo que tú escribas. Tu trabajo es que todas las imágenes cuenten la misma historia y parezcan del mismo video.

1. Estilo común ("look"): técnica, paleta de color, luz, óptica y textura, en una o dos frases. Parte del estilo que pida el usuario y concrétalo. Si todo el video ocurre en la misma época y lugar, inclúyelos; si el guion salta de época o de lugar, deja eso para cada escena.

2. Elementos que se repiten ("characters"): cada persona, animal, objeto (una máquina, un juguete, un juego, un vehículo) o lugar que aparezca en más de una escena, con un nombre corto que lo identifique, su tipo ("kind": "persona", "animal", "objeto" o "lugar") y sus rasgos fijos ("traits"). En una persona: edad, complexión, tono de piel, cara, pelo, vello facial y ropa con sus colores y materiales. En lo demás: forma, tamaño, materiales, colores y lo que lo distingue. Que dos no puedan confundirse. Si es una figura conocida —histórica, religiosa o de ficción—, descríbela como la muestra su iconografía habitual. Como mucho seis; puede no haber ninguno.
- Si recibes elementos que ya están en el video, mantén los que encajen con este guion, con sus nombres, tipos y rasgos exactos; los que sean de otro tema, déjalos fuera.

3. Dónde cambia la imagen ("scenes"): agrupa las frases en escenas de frases seguidas. Corta donde cambia lo que tiene que verse: otra persona o se habla de otra, otro lugar u otra época, otra idea, un «primero», «segundo» o «tercero». Las frases que siguen contando lo mismo comparten imagen.
- Cada escena empieza al principio de una frase, nunca a mitad.
- Cada frase dice cuánto tarda en decirse. Una escena dura de 3 a 9 segundos. Una frase de menos de 3 segundos nunca va sola: se une a la siguiente si esta desarrolla su idea («Primero, las fuentes.» va con la frase que presenta la primera fuente), o si no a la anterior. Una frase de más de 9 segundos va sola.
- Haz tantas escenas como pida el encargo.

4. Una imagen por escena: lo que se ve, concreto y literal: quién, haciendo qué, dónde, con qué luz y desde qué plano. Entre 25 y 60 palabras.
- Muestra la idea principal de las frases de esa escena —de quién o de qué hablan—, no un detalle nombrado de pasada ni lo que cuentan las escenas de al lado.
- Nombra a cada elemento con su nombre exacto y no vuelvas a describirlo: sus rasgos se añaden solos. Lo que salga en una sola escena se describe ahí mismo.
- Las frases abstractas («no lo dejes para mañana», «tu vida cambia») se cuentan con un momento visible: un gesto, una acción, un lugar.
- Las escenas siguen un hilo, como los planos de una película: si alguien empieza algo, las siguientes lo continúan o muestran su consecuencia.
- El modelo dibuja como letras cualquier palabra que lea como texto. No cites frases del guion ni pongas en la imagen carteles, letreros, libros abiertos, pantallas, pancartas u otros objetos con letras. Describe solo lo que se ve, nunca lo que no debe aparecer.
- El generador tiene un filtro que bloquea la imagen entera si ve cuerpos mojados o con poca ropa, heridas o violencia. Cuéntalo con planos que no los muestren: ropa seca, un plano más abierto, el gesto o la cara en vez del cuerpo.
- {frame_rule}

5. Un movimiento por escena ("motion"): si la escena se anima, un modelo de video parte de su imagen como primer fotograma y la mueve durante la escena, en un solo plano. Di en una frase de 5 a 15 palabras qué se mueve y qué hace la cámara: «Ana sirve el café y el vapor sube; la cámara se acerca despacio».
- Solo lo que cabe en esa imagen y en esos segundos: un gesto o una acción sencilla de quien ya está en el plano. Nadie entra ni sale, el lugar no cambia y no hay cortes.
- Un solo movimiento de cámara: fija, se acerca, se aleja, gira hacia un lado o sigue a alguien.
- No repitas lo que ya dice la descripción: solo el movimiento.

Responde solo con un objeto JSON, sin markdown ni comentarios, todo en español:
{{"look": "...", "characters": [{{"name": "...", "kind": "persona", "traits": "..."}}], "scenes": [{{"from": 1, "description": "...", "motion": "..."}}, {{"from": 3, "description": "...", "motion": "..."}}]}}
"from" es el número de la frase con la que empieza la escena. La primera empieza en la frase 1, cada una en una frase posterior a la de la anterior, y dura hasta la frase antes de la siguiente."""


def system_prompt(fmt: Format = VERTICAL, length: Length = REEL) -> str:
    """El encargo del director de arte, con el tipo de video y dónde caben las caras."""
    if length is REEL and fmt.vertical:
        kind = "videos cortos verticales (Reels, Shorts, TikTok)"
    elif length is REEL:
        kind = "videos cortos horizontales"
    else:
        kind = f"cortometrajes en formato {'vertical' if fmt.vertical else 'horizontal'}"
    return _SYSTEM_TEMPLATE.format(kind=kind, frame_rule=fmt.storyboard_rule)


SYSTEM_PROMPT = system_prompt()


@dataclass(frozen=True)
class StoryboardScene:
    #: Segundo en el que entra: lo fija el reparto del guion, no el modelo.
    start: float
    #: Lo que dice la voz en ese tramo.
    text: str
    #: Lo que se ve. Es lo que el usuario edita y lo que se pinta.
    description: str
    #: Qué se mueve si la escena se anima (`animation.animation_prompt`). Puede
    #: faltar: un modelo que no lo escriba no tumba el guion visual.
    motion: str = ""

    def as_dict(self) -> dict:
        return {"start": self.start, "text": self.text, "description": self.description, "motion": self.motion}


@dataclass(frozen=True)
class Storyboard:
    guide: VisualGuide
    scenes: tuple[StoryboardScene, ...]

    def as_dict(self) -> dict:
        return {"guide": self.guide.as_dict(), "scenes": [s.as_dict() for s in self.scenes]}


def _listed(characters: Sequence[Character]) -> list[str]:
    return [f"- {c.name} ({c.kind}): {c.traits}" for c in characters]


def _seconds(sentence: str) -> float:
    return len(sentence.split()) / WORDS_PER_SECOND


def scene_range(sentences: Sequence[str], max_scenes: int = MAX_SCENES) -> tuple[int, int]:
    """
    Cuántas escenas pedir: como mucho `MAX_SCENES` (cada imagen cuesta) y una
    por frase; como poco, las que hacen falta para que ninguna pase, de media,
    de `LONGEST_SCENE_SECONDS`.
    """
    high = min(max_scenes, len(sentences))
    low = math.ceil(sum(map(_seconds, sentences)) / LONGEST_SCENE_SECONDS)
    return min(high, max(1, low)), high


def build_prompt(
    topic: str,
    style: str,
    sentences: Sequence[str],
    current: Sequence[Character] = (),
    max_scenes: int = MAX_SCENES,
) -> str:
    """
    El encargo del guion visual: el guion en frases numeradas, con lo que
    tarda cada una, para que el modelo decida dónde cambia la imagen.

    `current` es lo que ya está en el video —puesto a mano, traído de la
    biblioteca o de un guion visual anterior—. No es obligatorio: el reparto
    sigue en el panel al cambiar de guion, y un video sobre Kafka no debe
    arrastrar al Jesús del anterior. El modelo se queda con lo que encaje.
    """
    lines = [
        f"Tema: {topic.strip() or 'el del guion'}",
        f"Estilo que pide el usuario: {style.strip() or DEFAULT_STYLE}",
    ]
    if current:
        lines += ["", "Elementos que ya están en el video (mantén los que encajen):", *_listed(current)]
    lines += ["", f"Guion en {len(sentences)} frases, con lo que tarda cada una en decirse:"]
    lines += [f"{n}. ({max(1, round(_seconds(s)))} s) {s}" for n, s in enumerate(sentences, start=1)]
    low, high = scene_range(sentences, max_scenes)
    lines += ["", f"Escenas: {high}." if low == high else f"Escenas: entre {low} y {high}."]
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


def _cast(items: object, current: Sequence[Character]) -> list[Character]:
    """
    Los elementos del guion visual. Lo que el modelo toma del video entra con
    sus rasgos y su referencia de siempre, no con lo que el modelo haya
    reescrito. Lo que inventa es nuevo aunque se llame como algo guardado: la
    biblioteca no se enlaza por coincidencia de nombre.
    """
    known = {fold(c.name): c for c in current}
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


def _cuts(items: object, sentences: Sequence[str], max_scenes: int = MAX_SCENES) -> list[tuple[int, str, str]]:
    """
    Dónde empieza cada escena (índice de su primera frase, desde 0), qué se ve
    y qué se mueve.

    Se arregla lo que tiene arreglo sin inventar nada: las escenas van en orden
    de frase aunque lleguen desordenadas, una frase que abre dos escenas se
    queda con la primera, lo que apunta fuera del guion se descarta y la
    primera escena abre el video aunque el modelo la empiece más tarde.

    Si se pasa de `MAX_SCENES`, se queda con las que cubren el principio de
    cada tramo del reparto por longitud (`plan_cuts`): siguen cortando donde
    el modelo quiso, solo que menos veces, y cada imagen con su descripción.
    """
    found: dict[int, tuple[str, str]] = {}
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        first = _number(item.get("from"), 0) - 1
        text = _clip(item.get("description"), SCENE_LIMIT)
        if 0 <= first < len(sentences) and text:
            found.setdefault(first, (text, _clip(item.get("motion"), MOTION_LIMIT)))

    cuts = [(first, text, motion) for first, (text, motion) in sorted(found.items())]
    if not cuts:
        return []
    cuts[0] = (0, *cuts[0][1:])
    if len(cuts) <= max_scenes:
        return cuts

    kept: list[tuple[int, str, str]] = []
    for first in plan_cuts(sentences, max_scenes=max_scenes):
        cover = next(cut for cut in reversed(cuts) if cut[0] <= first)
        if not kept or kept[-1] != cover:
            kept.append(cover)
    return kept


def parse_storyboard(
    raw: str | None,
    sentences: Sequence[str],
    seed: int,
    current: Sequence[Character] = (),
    max_scenes: int = MAX_SCENES,
) -> Storyboard:
    """
    Lee la respuesta del modelo. Las escenas salen de sus cortes; el segundo
    de cada una, de las palabras que la preceden, como la duración del guion.
    """
    data = _json_object(raw)

    look = _clip(data.get("look"), LOOK_LIMIT)
    if not look:
        raise WriterError("El guion visual llegó sin estilo. Vuelve a intentarlo.")

    characters = _cast(data.get("characters"), current)

    cuts = _cuts(data.get("scenes"), sentences, max_scenes)
    if not cuts:
        raise WriterError("El guion visual llegó sin escenas que encajen con el guion. Vuelve a intentarlo.")

    beats = beats_from_cuts(sentences, [first for first, _, _ in cuts])
    return Storyboard(
        VisualGuide(look, tuple(characters), seed),
        tuple(StoryboardScene(b.start, b.text, shot, motion) for b, (_, shot, motion) in zip(beats, cuts)),
    )
