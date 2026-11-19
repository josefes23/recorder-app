"""
Puerto `VoiceSynthesizer`: la voz del guion con edge-tts, a través del motor.

La usan el servidor (para escuchar antes de renderizar) y el worker de render
(cuando la toma no estaba hecha): las dos generan la voz igual, y por eso la
misma clave da el mismo audio.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from app.domain.dialogue import NARRATOR, Line, split_dialogue
from app.domain.errors import EngineError
from app.domain.voice_take import TakeRequest
from app.infrastructure.elevenlabs import ElevenLabsClient, VoiceRouter
from app.infrastructure.soundtrack import synthesize_dialogue


def audio_seconds(path: Path) -> float:
    from moviepy import AudioFileClip

    with AudioFileClip(str(path)) as clip:
        return float(clip.duration)


class EngineVoiceSynthesizer:
    def __init__(self, gen, scratch: Path, eleven: ElevenLabsClient | None = None) -> None:
        # Cada voz va a su proveedor: edge-tts por el motor, ElevenLabs por su API.
        self._gen = VoiceRouter(gen, eleven)
        #: Dónde se escribe el audio mientras se genera; se borra al acabar.
        self._scratch = scratch

    def synthesize(self, request: TakeRequest) -> tuple[bytes, list[dict], float]:
        lines = (
            split_dialogue(request.text, request.voices.keys())
            if request.voices
            else [Line(NARRATOR, request.text)]
        )
        self._scratch.mkdir(parents=True, exist_ok=True)
        out = self._scratch / f".voz-{uuid.uuid4().hex}.mp3"
        try:
            words = synthesize_dialogue(
                self._gen, lines, request.voices, request.voice, request.rate, request.pitch, out,
            )
            return out.read_bytes(), words, audio_seconds(out)
        except SystemExit as exc:
            # El motor sale con sys.exit si edge-tts devuelve un audio vacío.
            raise EngineError(str(exc) or "La voz no se pudo generar.") from None
        except EngineError:
            raise
        except Exception as exc:  # noqa: BLE001 - red, edge-tts o el audio: el usuario debe verlo
            raise EngineError(
                f"No se pudo generar la voz ({type(exc).__name__}: {exc}). Revisa la conexión a internet."
            ) from exc
        finally:
            out.unlink(missing_ok=True)
