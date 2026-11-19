"""
Las voces entre las que se elige: las de edge-tts (gratis, siempre) y, si hay
clave, las de la cuenta de ElevenLabs (gastan créditos). Conviven: cada video, o
cada personaje de un diálogo, usa la que el usuario escoja.
"""

from __future__ import annotations

import time

from app.application.ports import CredentialStore, RemoteVoices
from app.domain.errors import DomainError, ValidationError
from app.domain.voice import ELEVEN_KEY_SETTING, ELEVEN_MODEL, VOICES, Voice

#: La lista de la cuenta cambia poco: se guarda un rato para no pedirla en cada /api/config.
CACHE_SECONDS = 600


def voice_dict(voice: Voice) -> dict:
    return {"id": voice.id, "label": voice.label, "provider": voice.provider, "preview": voice.preview}


class VoiceCatalog:
    def __init__(self, credentials: CredentialStore, eleven: RemoteVoices) -> None:
        self._credentials = credentials
        self._eleven = eleven
        self._cached: tuple[float, str | None, list[Voice]] | None = None

    def _remote(self) -> tuple[list[Voice], str | None]:
        """Las voces de ElevenLabs y, si no se pudieron traer, por qué."""
        key = self._credentials.get(ELEVEN_KEY_SETTING)
        if not key:
            return [], None
        if self._cached and self._cached[1] == key and time.monotonic() - self._cached[0] < CACHE_SECONDS:
            return self._cached[2], None
        try:
            found = self._eleven.voices()
        except DomainError as exc:
            return [], str(exc)
        self._cached = (time.monotonic(), key, found)
        return found, None

    def all(self) -> list[Voice]:
        return [*VOICES, *self._remote()[0]]

    def elevenlabs(self) -> dict:
        voices, problem = self._remote()
        return {
            "ready": bool(self._credentials.get(ELEVEN_KEY_SETTING)),
            "model": ELEVEN_MODEL,
            "voices": len(voices),
            "problem": problem,
        }

    def refresh(self) -> dict:
        """Descarta la lista guardada: la próxima consulta trae las voces de la cuenta otra vez."""
        self._cached = None
        return self.elevenlabs()

    def save_key(self, api_key: str) -> dict:
        """Guarda la clave (vacía = la quita) y comprueba que ElevenLabs la acepta."""
        key = (api_key or "").strip()
        if any(ch.isspace() for ch in key):
            raise ValidationError("La clave no puede llevar espacios.")
        self._cached = None
        self._credentials.save({ELEVEN_KEY_SETTING: key or None})
        return self.elevenlabs()
