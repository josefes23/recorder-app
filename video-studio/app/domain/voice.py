"""Voces disponibles y valores por defecto de la locución."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Voice:
    id: str
    label: str
    #: "edge" (gratis) o "elevenlabs" (gasta créditos de la cuenta).
    provider: str = "edge"
    #: Muestra de audio de la voz, si el proveedor la da (ElevenLabs sí, sin gastar créditos).
    preview: str = ""


VOICES: tuple[Voice, ...] = (
    Voice("es-MX-DaliaNeural", "Dalia — México ♀"),
    Voice("es-MX-JorgeNeural", "Jorge — México ♂"),
    Voice("es-ES-ElviraNeural", "Elvira — España ♀"),
    Voice("es-ES-AlvaroNeural", "Álvaro — España ♂"),
    Voice("es-ES-XimenaNeural", "Ximena — España ♀"),
    Voice("es-AR-ElenaNeural", "Elena — Argentina ♀"),
    Voice("es-AR-TomasNeural", "Tomás — Argentina ♂"),
    Voice("es-CO-SalomeNeural", "Salomé — Colombia ♀"),
    Voice("es-CO-GonzaloNeural", "Gonzalo — Colombia ♂"),
    Voice("es-CL-CatalinaNeural", "Catalina — Chile ♀"),
    Voice("es-PE-CamilaNeural", "Camila — Perú ♀"),
    Voice("es-US-PalomaNeural", "Paloma — EE.UU. ♀"),
)

DEFAULT_VOICE = "es-MX-DaliaNeural"

#: Lo que dice una voz al probarla: corto, en español, para no gastar créditos de más.
SAMPLE_TEXT = "Hola, así suena mi voz en tu video."
DEFAULT_RATE = "+8%"
DEFAULT_PITCH = "+0Hz"

#: Las voces de ElevenLabs llevan este prefijo: así la misma lista y la misma
#: clave de toma distinguen de qué proveedor es cada voz, sin otro campo.
ELEVEN_PREFIX = "eleven:"
ELEVEN_MODEL = "eleven_multilingual_v2"
ELEVEN_KEY_SETTING = "ELEVENLABS_API_KEY"

#: ElevenLabs acepta una velocidad entre 0,7 y 1,2 (1 = normal).
ELEVEN_MIN_SPEED = 0.7
ELEVEN_MAX_SPEED = 1.2


def is_eleven(voice_id: str | None) -> bool:
    return bool(voice_id) and str(voice_id).startswith(ELEVEN_PREFIX) and len(str(voice_id)) > len(ELEVEN_PREFIX)


_GENDER_MARK = {"female": "♀", "male": "♂"}


def eleven_voice(remote_id: str, name: str, accent: str = "", gender: str = "", preview: str = "") -> Voice:
    """«Rachel — american ♀ — ElevenLabs»: el nombre, lo que la cuenta dice de ella y de dónde viene."""
    detail = " ".join(part for part in (accent.strip(), _GENDER_MARK.get(gender.strip().lower(), "")) if part)
    label = " — ".join(part for part in (name, detail, "ElevenLabs") if part)
    return Voice(f"{ELEVEN_PREFIX}{remote_id}", label, "elevenlabs", preview)


def eleven_remote_id(voice_id: str) -> str:
    """El id que entiende ElevenLabs, sin el prefijo."""
    return voice_id[len(ELEVEN_PREFIX):]


def eleven_speed(rate: str | None) -> float:
    """
    La velocidad de edge-tts («+8%», «-10%») como la pide ElevenLabs (1,08; 0,9),
    dentro de lo que acepta. El tono no tiene equivalente y no se usa.
    """
    text = (rate or "").strip().rstrip("%")
    try:
        speed = 1 + float(text) / 100
    except ValueError:
        return 1.0
    return round(min(ELEVEN_MAX_SPEED, max(ELEVEN_MIN_SPEED, speed)), 2)
