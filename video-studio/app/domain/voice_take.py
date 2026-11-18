"""
Una toma de voz: el audio del guion y el segundo en que la voz dice cada palabra.

Hasta ahora la voz solo existía dentro del render: se generaba, se usaba y se
tiraba, así que antes de renderizar nadie sabía en qué momento caía cada frase,
y después tampoco. Ahora la voz se puede generar sola —es gratis y tarda unos
segundos— para escuchar la animática con ella, y se guarda: el render usa la
misma toma en vez de generar otra, y el video recuerda cuál usó.

Una toma la identifica exactamente lo que se sintetiza: el texto limpio, la voz,
la velocidad, el tono y la voz de cada personaje. Cambiar cualquiera es otra
toma; repetir los mismos es la misma (`take_key`).
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from app.domain.dialogue import clean_lines, validate_voices
from app.domain.errors import ValidationError
from app.domain.script import clean_script
from app.domain.voice import DEFAULT_PITCH, DEFAULT_RATE, DEFAULT_VOICE

#: Las claves son hexadecimales y cortas: van en nombres de archivo y en URL.
_KEY = re.compile(r"^[0-9a-f]{16}$")


@dataclass(frozen=True)
class TakeRequest:
    """Lo que se sintetiza, ya limpio: lo mismo que recibe el render."""

    #: Limpio; con las etiquetas «ANA:» al principio de cada línea si es diálogo.
    text: str
    voice: str
    rate: str
    pitch: str
    #: Voz de cada personaje; vacío = el guion entero con una sola voz.
    voices: dict = field(default_factory=dict)


def voice_text(script: str | None, voices: Mapping | None) -> str:
    """El texto que se le da a la voz: con diálogo se conservan las líneas, sin él un solo párrafo."""
    return clean_lines(script) if voices else clean_script(script)


def take_request(
    script: str | None, voice: str | None, rate: str | None, pitch: str | None, voices: Mapping | None,
) -> TakeRequest:
    checked = validate_voices(voices)
    text = voice_text(script, checked)
    if not text:
        raise ValidationError("El guion está vacío.")
    return TakeRequest(text, voice or DEFAULT_VOICE, rate or DEFAULT_RATE, pitch or DEFAULT_PITCH, checked)


def take_key(request: TakeRequest) -> str:
    """La misma entrada da siempre la misma clave: así el render encuentra la toma ya hecha."""
    payload = json.dumps(
        [request.text, request.voice, request.rate, request.pitch, sorted(request.voices.items())],
        ensure_ascii=False,
    )
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]


def is_take_key(value: object) -> bool:
    return isinstance(value, str) and bool(_KEY.match(value))


def clean_words(raw: object) -> list[dict]:
    """Las marcas de una toma guardada, comprobadas: texto, inicio y fin de cada palabra."""
    words: list[dict] = []
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        return words
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        try:
            words.append({"text": str(item["text"]), "start": float(item["start"]), "end": float(item["end"])})
        except (KeyError, TypeError, ValueError):
            continue
    return words


@dataclass(frozen=True)
class VoiceTake:
    key: str
    duration: float
    #: Cada palabra que dijo la voz: {text, start, end}, en segundos.
    words: list[dict]
    #: Si el audio sigue guardado. Las marcas se guardan siempre; el audio, solo
    #: el de las últimas tomas (ocupa un mega por minuto).
    audio: bool = True

    def as_dict(self) -> dict:
        return {"key": self.key, "duration": round(self.duration, 3), "words": self.words, "audio": self.audio}
