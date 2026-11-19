"""
ElevenLabs como segunda voz del estudio, junto a edge-tts.

Cada llamada gasta créditos de la cuenta del usuario, así que solo se usa con
las voces que él elige (`eleven:<id>`). La API de «con marcas de tiempo» da el
audio y el segundo de cada carácter; aquí se agrupan en palabras, que es lo que
necesitan los subtítulos y el corte de escenas.
"""

from __future__ import annotations

import base64
from collections.abc import Callable
from pathlib import Path

import requests

from app.domain.errors import EngineError
from app.domain.voice import (
    ELEVEN_MODEL,
    Voice,
    eleven_remote_id,
    eleven_speed,
    eleven_voice,
    is_eleven,
)

BASE_URL = "https://api.elevenlabs.io/v1"
TIMEOUT = 120


def words_from_alignment(alignment: dict) -> list[dict]:
    """Los caracteres con su inicio y fin, agrupados en palabras ({text, start, end})."""
    chars = alignment.get("characters") or []
    starts = alignment.get("character_start_times_seconds") or []
    ends = alignment.get("character_end_times_seconds") or []
    words: list[dict] = []
    current = ""
    start = end = 0.0
    for char, begin, finish in zip(chars, starts, ends):
        if char.isspace():
            if current:
                words.append({"text": current, "start": start, "end": end})
                current = ""
            continue
        if not current:
            start = float(begin)
        current += char
        end = float(finish)
    if current:
        words.append({"text": current, "start": start, "end": end})
    return words


def _error_text(response: requests.Response) -> str:
    try:
        detail = response.json().get("detail")
        if isinstance(detail, dict):
            detail = detail.get("message")
        return str(detail or response.text)[:200]
    except ValueError:
        return response.text[:200]


def _rejected(response: requests.Response) -> EngineError:
    """
    Un 401 puede ser una clave mala o una clave sin permiso para esa acción (las
    claves de ElevenLabs se pueden limitar): se muestra lo que ElevenLabs dice.
    """
    reason = _error_text(response).strip()
    return EngineError(
        "ElevenLabs no aceptó la clave" + (f": {reason}" if reason else ". Revísala en elevenlabs.io.")
    )


class ElevenLabsClient:
    """Voces de la cuenta y síntesis. La clave se pide en cada llamada: puede cambiar sin reiniciar."""

    def __init__(self, api_key: Callable[[], str | None]) -> None:
        self._api_key = api_key

    def ready(self) -> bool:
        return bool(self._api_key())

    def _headers(self) -> dict[str, str]:
        key = self._api_key()
        if not key:
            raise EngineError("Falta la clave de ElevenLabs: pégala en el paso Voz.")
        return {"xi-api-key": key}

    def voices(self) -> list[Voice]:
        try:
            response = requests.get(f"{BASE_URL}/voices", headers=self._headers(), timeout=30)
        except requests.RequestException as exc:
            raise EngineError(f"No se pudo consultar ElevenLabs ({type(exc).__name__}). Revisa la conexión.") from exc
        if response.status_code in (401, 403):
            raise _rejected(response)
        if not response.ok:
            raise EngineError(f"ElevenLabs respondió {response.status_code}: {_error_text(response)}")
        found = response.json().get("voices") or []
        return [
            eleven_voice(
                v["voice_id"],
                v.get("name") or v["voice_id"],
                (v.get("labels") or {}).get("accent") or "",
                (v.get("labels") or {}).get("gender") or "",
                v.get("preview_url") or "",
            )
            for v in found
            if v.get("voice_id")
        ]

    def speak(self, text: str, voice: str, rate: str, out_mp3: Path) -> list[dict]:
        """Escribe el audio en `out_mp3` y devuelve las marcas de cada palabra."""
        if not is_eleven(voice):
            raise EngineError(f"«{voice}» no es una voz de ElevenLabs.")
        body = {
            "text": text,
            "model_id": ELEVEN_MODEL,
            "voice_settings": {"speed": eleven_speed(rate)},
        }
        url = f"{BASE_URL}/text-to-speech/{eleven_remote_id(voice)}/with-timestamps"
        try:
            response = requests.post(
                url, headers=self._headers(), json=body, params={"output_format": "mp3_44100_128"}, timeout=TIMEOUT,
            )
        except requests.RequestException as exc:
            raise EngineError(f"No se pudo generar la voz con ElevenLabs ({type(exc).__name__}). Revisa la conexión.") from exc
        if response.status_code in (401, 403):
            raise _rejected(response)
        if response.status_code == 402 or (response.status_code == 400 and "quota" in response.text.lower()):
            raise EngineError("Se acabaron los créditos de ElevenLabs.")
        if not response.ok:
            raise EngineError(f"ElevenLabs respondió {response.status_code}: {_error_text(response)}")
        data = response.json()
        audio = base64.b64decode(data.get("audio_base64") or "")
        if not audio:
            raise EngineError("ElevenLabs devolvió un audio vacío.")
        out_mp3.write_bytes(audio)
        return words_from_alignment(data.get("alignment") or data.get("normalized_alignment") or {})


class VoiceRouter:
    """
    Lo que `synthesize_dialogue` usa como motor: cada voz va a su proveedor.
    `eleven:<id>` a ElevenLabs; cualquier otra a edge-tts, a través del motor.
    """

    def __init__(self, gen, eleven: ElevenLabsClient | None) -> None:
        self._gen = gen
        self._eleven = eleven

    def synthesize_voice(self, text: str, voice: str, rate: str, pitch: str, out_mp3: Path) -> list[dict]:
        if is_eleven(voice):
            if self._eleven is None:
                raise EngineError("ElevenLabs no está configurado.")
            return self._eleven.speak(text, voice, rate, out_mp3)
        return self._gen.synthesize_voice(text, voice, rate, pitch, out_mp3)
