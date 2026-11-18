"""
La descripción para publicar el video, escrita por el modelo del guion.

Va por el flujo de eventos como el guion y los títulos: el modelo puede tardar
más de lo que aguanta una petición. Se escribe con el guion delante —es un
resumen suyo— y con el título de la portada, para que casen.
"""

from __future__ import annotations

from app.application.ports import EventLog, ScriptComposer
from app.application.use_cases.writer_settings import WriterSettings
from app.application.use_cases.prompts import PromptBook
from app.domain.cover import plain_title
from app.domain.description import (
    DESCRIPTION_SYSTEM_PROMPT,
    build_description_prompt,
    parse_description,
)
from app.domain.errors import DomainError, ValidationError, WriterError
from app.domain.events import (
    DESCRIPTION_COMPLETED,
    DESCRIPTION_FAILED,
    DESCRIPTION_REQUESTED,
    DESCRIPTION_TERMINAL,
    Event,
    new_job_key,
)
from app.domain.script import clean_script

CONSUMER_GROUP = "describer"


class DescriptionUseCases:
    def __init__(
        self,
        events: EventLog,
        writer: WriterSettings,
        composer: ScriptComposer,
        prompts: PromptBook | None = None,
    ) -> None:
        self._prompts = prompts or PromptBook()
        self._events = events
        self._writer = writer
        self._composer = composer

    # Desde la API ------------------------------------------------------------ #

    def request(self, topic: str, script: str, title: str = "") -> Event:
        """Encola la descripción y devuelve el evento con la clave del trabajo."""
        text = clean_script(script)
        if not text:
            raise ValidationError("Escribe primero el guion: la descripción lo resume.")
        if not self._writer.available():
            raise ValidationError(
                "La descripción la escribe el modelo del guion: añade una clave en «Modelo del guion», "
                "o escríbela tú."
            )
        return self._events.publish(
            DESCRIPTION_REQUESTED,
            new_job_key("ds"),
            # El título va sin las marcas de resaltado: al modelo solo le importa qué dice.
            {"topic": topic.strip(), "script": text, "title": plain_title(title)},
        )

    # Desde el consumidor ------------------------------------------------------ #

    def write(self, topic: str, script: str, title: str = "") -> str:
        """Escribe la descripción ahora, bloqueando. Lo llama el consumidor, nunca la API."""
        provider = self._writer.active()
        if provider is None:
            raise WriterError("No hay clave de API configurada. Añade una en «Modelo del guion».")
        raw = self._composer.compose(
            provider,
            self._writer.model_for(provider),
            self._writer.api_key(provider),
            self._prompts.template("description") or DESCRIPTION_SYSTEM_PROMPT,
            build_description_prompt(topic, title, script),
        )
        return parse_description(raw)

    def handle_request(self, event: Event) -> None:
        """Atiende un `description.requested` y publica su desenlace."""
        # Las mismas garantías que el guion: llegar dos veces no cuesta dos llamadas.
        if event.key is None or self._events.settled(event.key, DESCRIPTION_TERMINAL):
            return
        if not self._events.claim(event.key):
            return
        payload = event.payload
        try:
            text = self.write(payload.get("topic", ""), payload.get("script", ""), payload.get("title", ""))
        except DomainError as exc:
            self._events.publish(DESCRIPTION_FAILED, event.key, {"detail": str(exc)})
            return
        except Exception as exc:  # noqa: BLE001 - el consumidor no debe morir nunca
            self._events.publish(DESCRIPTION_FAILED, event.key, {"detail": f"{type(exc).__name__}: {exc}"})
            return
        self._events.publish(DESCRIPTION_COMPLETED, event.key, {"description": text})
