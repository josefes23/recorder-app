"""
Guiones con diálogo: varias voces en un mismo video.

Con el modo diálogo, cada línea que empieza con un nombre en MAYÚSCULAS y dos
puntos («ANA: ¿Viste eso?») la dice ese personaje con su voz; las demás, el
narrador. La etiqueta no se lee ni sale en los subtítulos. Sin modo diálogo
el guion se lee entero con una sola voz, como siempre: así un «OJO: …» de un
reel no pierde su primera palabra.

Las mismas reglas viven en `web/domain/dialogue.ts`.
"""

from __future__ import annotations

import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass

from app.domain.errors import ValidationError
from app.domain.script import clean_script

#: «ANA:», «DON PEDRO:», «NARRADORA:». Hasta 30 caracteres: más es una frase.
LABEL = re.compile(r"^\s*([A-ZÁÉÍÓÚÜÑ][A-ZÁÉÍÓÚÜÑ ]{0,29}?)\s*:\s*(.*)$")

#: Etiquetas que son el narrador: su voz es la del video.
NARRATOR_LABELS = frozenset({"NARRADOR", "NARRADORA", "NARRACIÓN", "NARRACION", "VOZ EN OFF"})

#: Clave del narrador en las líneas.
NARRATOR = ""

#: Silencio entre una intervención y la siguiente, en segundos.
TURN_GAP = 0.35

MAX_SPEAKERS = 8


@dataclass(frozen=True)
class Line:
    #: La etiqueta en mayúsculas, o "" para el narrador.
    speaker: str
    text: str


def speakers_in(raw: str | None) -> list[str]:
    """Las etiquetas que aparecen al principio de una línea, sin el narrador, en orden."""
    found: list[str] = []
    for row in (raw or "").splitlines():
        match = LABEL.match(row)
        if match and match.group(2).strip():
            name = match.group(1).strip()
            if name not in NARRATOR_LABELS and name not in found:
                found.append(name)
    return found


def split_dialogue(raw: str | None, speakers: Collection[str]) -> list[Line]:
    """
    El guion en intervenciones. Solo cuentan como etiqueta los `speakers`
    (y el narrador); cualquier otra línea la dice el narrador tal cual. Las
    líneas seguidas del mismo hablante se juntan: una sola llamada a la voz.
    """
    known = set(speakers)
    lines: list[Line] = []
    for row in (raw or "").splitlines():
        match = LABEL.match(row)
        speaker, text = NARRATOR, row
        if match and match.group(2).strip():
            name = match.group(1).strip()
            if name in NARRATOR_LABELS:
                text = match.group(2)
            elif name in known:
                speaker, text = name, match.group(2)
        text = clean_script(text)
        if not text:
            continue
        if lines and lines[-1].speaker == speaker:
            lines[-1] = Line(speaker, f"{lines[-1].text} {text}")
        else:
            lines.append(Line(speaker, text))
    return lines


def clean_lines(raw: str | None) -> str:
    """El guion limpio línea a línea, sin aplanarlo: las etiquetas siguen al principio."""
    return "\n".join(line for line in map(clean_script, (raw or "").splitlines()) if line)


def spoken_text(lines: list[Line]) -> str:
    """Lo que se oye, sin etiquetas: con esto se arman los subtítulos y se sitúan las escenas."""
    return " ".join(line.text for line in lines)


def validate_voices(voices: Mapping | None) -> dict[str, str]:
    """La voz de cada personaje, con las etiquetas en mayúsculas como en el guion."""
    if not voices:
        return {}
    if not isinstance(voices, Mapping):
        raise ValidationError("Las voces del diálogo llegaron con un formato que no se entiende.")
    clean: dict[str, str] = {}
    for name, voice in voices.items():
        label = str(name).strip().upper()
        if not label or not isinstance(voice, str) or not voice.strip():
            continue
        clean[label] = voice.strip()
    if len(clean) > MAX_SPEAKERS:
        raise ValidationError(f"Como mucho {MAX_SPEAKERS} personajes con voz propia por video.")
    return clean
