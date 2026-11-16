"""
La descripción con la que se publica el video: lo que leen los buscadores de
YouTube, TikTok e Instagram para decidir a quién se lo enseñan.

Lo que manda es el principio. Cada plataforma corta la descripción tras las
primeras líneas («… más») y su buscador pesa más lo que va primero, así que
las palabras clave van en la primera frase; después, un resumen fiel del video;
al final, unos pocos hashtags.
"""

from __future__ import annotations

import re

from app.domain.errors import WriterError
from app.domain.writer import strip_reasoning

#: El de YouTube, el más amplio de los tres. Instagram corta a 2200 y TikTok a
#: 4000: pasarse de ellos no se impide, la interfaz solo lo avisa.
DESCRIPTION_LIMIT = 5000
#: Por debajo de esto no es una descripción corta: es una respuesta rota.
MIN_DESCRIPTION = 80

DESCRIPTION_SYSTEM_PROMPT = """Escribes la descripción con la que se publica un video corto vertical (YouTube Shorts, TikTok, Reels) en español. La descripción es lo que leen los buscadores de cada plataforma: de ella depende que el video aparezca cuando alguien busca su tema.

Reglas:
- Empieza por las palabras clave. La primera frase contiene, dichas con naturalidad, las dos o tres búsquedas que alguien escribiría para encontrar este video. Las plataformas solo enseñan las primeras líneas.
- Después resume en dos o tres frases cortas lo que cuenta el video, fiel al guion: nada que el video no cumpla.
- Termina con una línea aparte de tres a cinco hashtags del tema, en minúsculas y sin tildes.
- Entre 300 y 600 caracteres en total.
- Español natural. Sin emojis, sin markdown y sin comillas. No amontones palabras clave: un texto relleno de ellas se lee mal y las plataformas lo penalizan.

Devuelve únicamente el texto de la descripción, sin título, sin etiquetas como «Descripción:» y sin explicaciones."""


def build_description_prompt(topic: str, title: str, script: str) -> str:
    prompt = f"Tema: {topic.strip() or 'sin tema'}"
    if title.strip():
        prompt += f"\nTítulo de la portada: {title.strip()}"
    return prompt + f"\n\nGuion del video:\n{script.strip()}"


_FENCE = re.compile(r"^```[a-z]*\s*|\s*```$", re.IGNORECASE)
#: «Descripción:», «**Descripción**:» y parecidos que algunos modelos anteponen.
_LABEL = re.compile(r"^\W*descripci[oó]n\W*:\s*", re.IGNORECASE)


def clean_description(raw: object) -> str:
    """
    Sin espacios de más en cada línea, como mucho una línea en blanco seguida y
    cortada por la última palabra que quepa en `DESCRIPTION_LIMIT`. Los saltos
    de línea se respetan: los hashtags van en la suya.
    """
    lines = [" ".join(line.split()) for line in str(raw or "").splitlines()]
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    if len(text) > DESCRIPTION_LIMIT:
        text = text[:DESCRIPTION_LIMIT].rsplit(" ", 1)[0].rstrip()
    return text


def parse_description(raw: str | None) -> str:
    """Lee la respuesta del modelo y la rechaza si no vale como descripción."""
    text = _FENCE.sub("", strip_reasoning(raw).strip())
    text = _LABEL.sub("", text.strip()).strip().strip("\"'«»“”")
    text = clean_description(text)
    if len(text) < MIN_DESCRIPTION:
        raise WriterError(
            "La descripción llegó vacía o incompleta. Vuelve a intentarlo, o cambia de modelo "
            "en «Modelo del guion»."
        )
    return text
