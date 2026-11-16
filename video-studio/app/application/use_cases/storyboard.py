"""
Guion visual: el modelo del guion decide qué se ve en cada escena antes de
pintar ninguna.

Va por el flujo de eventos como el guion, y por lo mismo: el modelo tarda de
segundos a más de un minuto y ninguna petición HTTP debería esperar tanto.

Lleva lo que ya está en el video y nada más. La biblioteca de elementos
guardados no se consulta: lo guardado entra en un video solo si el usuario lo
mete a mano, y entonces llega aquí con el resto del reparto.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.application.ports import EventLog, ScriptComposer
from app.application.use_cases.writer_settings import WriterSettings
from app.domain.errors import DomainError, ValidationError, WriterError
from app.domain.events import (
    STORYBOARD_COMPLETED,
    STORYBOARD_FAILED,
    STORYBOARD_REQUESTED,
    STORYBOARD_TERMINAL,
    Event,
    new_job_key,
)
from app.domain.illustration import Character, split_sentences, validate_guide
from app.domain.script import clean_script
from app.domain.storyboard import SYSTEM_PROMPT, Storyboard, build_prompt, new_seed, parse_storyboard

CONSUMER_GROUP = "storyboarder"


class StoryboardUseCases:
    def __init__(
        self,
        events: EventLog,
        writer: WriterSettings,
        composer: ScriptComposer,
    ) -> None:
        self._events = events
        self._writer = writer
        self._composer = composer

    # Desde la API ------------------------------------------------------------ #

    def request(
        self, topic: str, script: str, style: str = "", characters: list[Mapping] | None = None
    ) -> Event:
        """
        Encola el guion visual y devuelve el evento con la clave del trabajo.
        `characters` es lo que ya está en el video: entra si encaja.
        """
        self._sentences(script)
        current = validate_guide("", characters, None).characters
        if not self._writer.available():
            raise ValidationError(
                "Lo que se ve en cada escena lo decide el modelo del guion: añade una clave en "
                "«Modelo del guion»."
            )
        return self._events.publish(
            STORYBOARD_REQUESTED,
            new_job_key("sb"),
            {
                "topic": topic.strip(),
                "script": script,
                "style": style.strip(),
                "characters": [c.as_dict() for c in current],
            },
        )

    # Desde el consumidor ------------------------------------------------------ #

    def compose(
        self, topic: str, script: str, style: str = "", current: Sequence[Character] = ()
    ) -> Storyboard:
        """Escribe el guion visual ahora, bloqueando. Lo llama el consumidor, nunca la API."""
        sentences = self._sentences(script)
        provider = self._writer.active()
        if provider is None:
            raise WriterError("No hay clave de API configurada. Añade una en «Modelo del guion».")
        raw = self._composer.compose(
            provider,
            self._writer.model_for(provider),
            self._writer.api_key(provider),
            SYSTEM_PROMPT,
            build_prompt(topic, style, sentences, current),
        )
        return parse_storyboard(raw, sentences, new_seed(), current)

    def handle_request(self, event: Event) -> None:
        """Atiende un `storyboard.requested` y publica su desenlace."""
        # Mismas garantías que el guion: llegar dos veces no cuesta dos llamadas.
        if event.key is None or self._events.settled(event.key, STORYBOARD_TERMINAL):
            return
        if not self._events.claim(event.key):
            return

        payload = event.payload
        try:
            current = validate_guide("", payload.get("characters"), None).characters
            storyboard = self.compose(
                payload.get("topic", ""), payload.get("script", ""), payload.get("style", ""), current
            )
        except DomainError as exc:
            self._events.publish(STORYBOARD_FAILED, event.key, {"detail": str(exc)})
            return
        except Exception as exc:  # noqa: BLE001 - el consumidor no debe morir nunca
            self._events.publish(STORYBOARD_FAILED, event.key, {"detail": f"{type(exc).__name__}: {exc}"})
            return

        self._events.publish(STORYBOARD_COMPLETED, event.key, storyboard.as_dict())

    # ------------------------------------------------------------------------ #

    @staticmethod
    def _sentences(script: str) -> list[str]:
        sentences = split_sentences(clean_script(script))
        if not sentences:
            raise ValidationError("Escribe primero el guion: las escenas salen de sus frases.")
        return sentences
