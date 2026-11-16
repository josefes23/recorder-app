"""
La portada del video: un título gancho escrito en grande sobre una imagen.

Es lo que se ve en la cuadrícula del perfil y mientras alguien desliza el
dedo, así que se juzga en un segundo y en pequeño: pocas palabras, enormes, y
una de ellas en otro color para que el ojo caiga ahí primero.

Qué palabra resalta se marca en el propio título con asteriscos —«El *error*
que todos cometen»—: así cabe en un solo campo de texto, el modelo la propone
sin un formato aparte y el usuario la cambia sin otro control.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass

from app.domain.background import is_image
from app.domain.errors import ValidationError, WriterError
from app.domain.video import slugify
from app.domain.writer import strip_reasoning

#: Tope duro. Con más no hay letra que se lea en una miniatura; lo ideal son
#: de tres a seis, y eso lo pide el encargo al modelo y lo avisa la interfaz.
MAX_TITLE_WORDS = 12
TITLE_LIMIT = 90
#: Cuántos títulos propone el modelo de una vez.
MAX_SUGGESTIONS = 4


@dataclass(frozen=True)
class CoverDesign:
    id: str
    label: str


#: Los mismos ids viven en `web/domain/cover.ts`. Cómo se pinta cada uno lo
#: decide el pintor (`infrastructure/cover.py`); aquí solo cuáles existen.
COVER_DESIGNS: tuple[CoverDesign, ...] = (
    # Texto gigante en el tercio inferior sobre sombra, palabra en amarillo.
    CoverDesign("impacto", "Impacto"),
    # Cada línea sobre una franja amarilla e inclinada, arriba: rótulo de noticia.
    CoverDesign("franja", "Franja"),
    # Arriba sobre sombra, con la palabra dentro de una caja roja.
    CoverDesign("titular", "Titular"),
)
DEFAULT_DESIGN = COVER_DESIGNS[0].id
_DESIGN_IDS = frozenset(d.id for d in COVER_DESIGNS)


@dataclass(frozen=True)
class Cover:
    """Lo que hace falta para pintar la portada otra vez, tal cual."""

    title: str
    design: str = DEFAULT_DESIGN
    #: Nombre en la galería; None pinta el degradado del tema.
    background: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class CoverWord:
    text: str
    highlighted: bool


# --------------------------------------------------------------------- título

_QUOTES = "\"'«»“”‘’`"


def clean_title(raw: object) -> str:
    """En una línea, sin comillas alrededor ni punto final, y cortado si se pasa."""
    text = " ".join(str(raw or "").split()).strip(_QUOTES + " ")
    text = text.rstrip(".").strip(_QUOTES + " ")
    words = text.split()
    if len(words) > MAX_TITLE_WORDS:
        text = " ".join(words[:MAX_TITLE_WORDS])
    if len(text) > TITLE_LIMIT:
        text = text[:TITLE_LIMIT].rsplit(" ", 1)[0]
    return text


def plain_title(title: str) -> str:
    """El título sin las marcas de resaltado: para nombres de archivo y avisos."""
    return " ".join(title.replace("*", " ").split())


def cover_words(title: str) -> list[CoverWord]:
    """
    Las palabras en mayúsculas, cada una sabiendo si va resaltada.

    Lo que va entre asteriscos resalta, sea una palabra o varias. Un asterisco
    sin pareja se descarta en vez de resaltar hasta el final. Se trocea por
    espacios y no por asteriscos: en «*Padre*, no» la coma va con su palabra,
    no suelta como si fuera otra.
    """
    text = title
    if text.count("*") % 2:
        cut = text.rfind("*")
        text = text[:cut] + text[cut + 1 :]
    words: list[CoverWord] = []
    inside = False
    for token in text.split():
        letters: list[str] = []
        highlighted = False
        for char in token:
            if char == "*":
                inside = not inside
                continue
            letters.append(char)
            highlighted = highlighted or inside
        if letters:
            words.append(CoverWord("".join(letters).upper(), highlighted))
    return words


def default_title(topic: str) -> str:
    """
    El tema, con su palabra más larga resaltada. Es la portada que sale sin
    pedirle nada a ningún modelo; la interfaz aplica la misma regla.
    """
    title = clean_title(topic)
    if not title or "*" in title:
        return title
    words = title.split()
    longest = max(range(len(words)), key=lambda i: len(words[i].strip("¿?¡!,;:")))
    if len(words[longest].strip("¿?¡!,;:")) < 4:
        return title
    words[longest] = f"*{words[longest]}*"
    return " ".join(words)


# ------------------------------------------------------------------ validación

def validate_cover(title: object, design: object = DEFAULT_DESIGN, background: object = None) -> Cover:
    text = clean_title(title)
    if not plain_title(text):
        raise ValidationError("Escribe el título de la portada.")
    design_id = str(design or DEFAULT_DESIGN)
    if design_id not in _DESIGN_IDS:
        raise ValidationError(f"Diseño de portada desconocido: {design_id}")
    name = str(background).strip() if background else None
    return Cover(text, design_id, name or None)


def first_background(scenes: Sequence[Mapping]) -> str | None:
    """
    La imagen que la portada usa si nadie elige otra: la de la primera escena
    con imagen —las generadas ponen las caras arriba y se ven nítidas—, o el
    primer clip si no hay ninguna.
    """
    names = [s.get("background") for s in scenes if isinstance(s, Mapping) and s.get("background")]
    return next((n for n in names if is_image(n)), names[0] if names else None)


def stored_cover(raw: object, topic: str, scenes: Sequence[Mapping]) -> Cover:
    """
    La portada guardada con un video. Los renderizados antes de que existiera
    —o con una ficha que no se entiende— reciben la de por defecto, para que
    cualquier video de la biblioteca tenga portada que descargar.
    """
    if isinstance(raw, Mapping):
        try:
            return validate_cover(raw.get("title"), raw.get("design"), raw.get("background"))
        except ValidationError:
            pass
    return Cover(default_title(topic) or "Sin título", DEFAULT_DESIGN, first_background(scenes))


def read_cover(raw: object) -> dict:
    """La portada que llega con un render, lista para guardar; {} si no vale."""
    if not isinstance(raw, Mapping):
        return {}
    try:
        return validate_cover(raw.get("title"), raw.get("design"), raw.get("background")).as_dict()
    except ValidationError:
        return {}


def cover_filename(topic: str | None) -> str:
    return f"portada-{slugify(topic)}.jpg"


# ------------------------------------------------------- títulos con el modelo

TITLES_SYSTEM_PROMPT = """Escribes los títulos de portada de videos cortos verticales (Reels, Shorts, TikTok) en español. El título va escrito en grande sobre la miniatura del video, que la gente ve un segundo mientras desliza el dedo: su único trabajo es que se detenga y lo abra.

Reglas:
- Entre tres y seis palabras. Nunca más de ocho.
- Que despierte curiosidad o prometa algo concreto: una pregunta, una cifra, un error común, un secreto, una advertencia, un antes y un después.
- Fiel al video: nada que el guion no cumpla. Un título que engaña hace que la gente se vaya en el primer segundo.
- Español natural. Sin hashtags, sin emojis, sin comillas y sin punto final.
- Las cifras van en dígitos: en una portada se leen antes que las palabras ("3 errores", no "tres errores").
- Marca entre asteriscos la palabra que debe resaltar en otro color, o dos seguidas: la que más pesa. Una sola marca por título.

Propón cuatro títulos distintos entre sí, cada uno con un enfoque diferente.

Devuelve únicamente un JSON con esta forma, sin nada antes ni después:
{"titles": ["El *error* que todos cometen", "..."]}"""


def build_titles_prompt(topic: str, script: str) -> str:
    return f"Tema: {topic.strip() or 'sin tema'}\n\nGuion del video:\n{script.strip()}"


_BULLET = re.compile(r"^\s*(?:[-•]|\d+[.)])\s+")


def _candidates(text: str) -> list[object]:
    start, end = text.find("{"), text.rfind("}")
    if 0 <= start < end:
        try:
            data = json.loads(text[start : end + 1])
        except ValueError:
            data = None
        if isinstance(data, dict):
            titles = data.get("titles")
            return titles if isinstance(titles, list) else []
    # Sin JSON: hay modelos que contestan una lista. Vale cada línea con texto,
    # menos la que la presenta («Aquí tienes cuatro títulos:») y los restos de
    # un JSON roto.
    lines = (line.strip() for line in text.splitlines())
    return [
        _BULLET.sub("", line)
        for line in lines
        if line and not line.endswith(":") and not line.startswith(("{", "}", "[", "]", "`"))
    ]


def parse_titles(raw: str | None) -> list[str]:
    """Los títulos que valen, sin repetidos y como mucho `MAX_SUGGESTIONS`."""
    titles: list[str] = []
    seen: set[str] = set()
    for candidate in _candidates(strip_reasoning(raw)):
        if not isinstance(candidate, str):
            continue
        words = candidate.split()
        if not words or len(words) > MAX_TITLE_WORDS:
            continue
        title = clean_title(candidate)
        key = plain_title(title).casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        titles.append(title)
        if len(titles) == MAX_SUGGESTIONS:
            break
    if not titles:
        raise WriterError(
            "El modelo no propuso títulos que valgan. Vuelve a intentarlo, o cambia de modelo "
            "en «Modelo del guion»."
        )
    return titles
