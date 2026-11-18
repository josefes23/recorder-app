"""
El asistente de crecimiento: ganchos, retención, títulos, SEO, puntaje y tendencias.

Va por el flujo de eventos como el guion y la descripción: el modelo puede
tardar más de lo que aguanta una petición. Un solo tema (`growth.requested`)
sirve para los seis consejos; el tipo viaja en el encargo.
"""

from __future__ import annotations

from app.application.ports import EventLog, ScriptComposer
from app.application.use_cases.prompts import PromptBook
from app.application.use_cases.writer_settings import WriterSettings
from app.domain.cover import plain_title
from app.domain.errors import DomainError, ValidationError, WriterError
from app.domain.events import GROWTH_COMPLETED, GROWTH_FAILED, GROWTH_REQUESTED, GROWTH_TERMINAL, Event, new_job_key
from app.domain.growth import (
    build_growth_prompt,
    check_inputs,
    kind_by_id,
    parse_growth,
    prompt_id,
)
from app.domain.script import clean_script

CONSUMER_GROUP = "growth"


class GrowthUseCases:
    def __init__(
        self,
        events: EventLog,
        writer: WriterSettings,
        composer: ScriptComposer,
        prompts: PromptBook | None = None,
    ) -> None:
        self._events = events
        self._writer = writer
        self._composer = composer
        self._prompts = prompts or PromptBook()

    # Desde la API ------------------------------------------------------------ #

    def request(
        self, kind_id: str, topic: str, script: str = "", title: str = "", description: str = "", length: str = ""
    ) -> Event:
        """Encola el consejo y devuelve el evento con la clave del trabajo."""
        kind = kind_by_id(kind_id)
        text = clean_script(script)
        check_inputs(kind, topic, text)
        if not self._writer.available():
            raise ValidationError(
                "Los consejos los escribe el modelo del guion: añade una clave en «Modelo del guion»."
            )
        return self._events.publish(
            GROWTH_REQUESTED,
            new_job_key("gr"),
            {
                "kind": kind.id,
                "topic": topic.strip(),
                "script": text,
                "title": plain_title(title),
                "description": description.strip(),
                "length": length.strip(),
            },
        )

    # Desde el consumidor ------------------------------------------------------ #

    def advise(
        self, kind_id: str, topic: str, script: str = "", title: str = "", description: str = "", length: str = ""
    ) -> dict:
        """Pide el consejo ahora, bloqueando. Lo llama el consumidor, nunca la API."""
        kind = kind_by_id(kind_id)
        provider = self._writer.active()
        if provider is None:
            raise WriterError("No hay clave de API configurada. Añade una en «Modelo del guion».")
        raw = self._composer.compose(
            provider,
            self._writer.model_for(provider),
            self._writer.api_key(provider),
            self._prompts.template(prompt_id(kind)) or kind.prompt,
            build_growth_prompt(topic, script, title, description, length),
        )
        return parse_growth(kind, raw)

    def handle_request(self, event: Event) -> None:
        """Atiende un `growth.requested` y publica su desenlace."""
        if event.key is None or self._events.settled(event.key, GROWTH_TERMINAL):
            return
        if not self._events.claim(event.key):
            return
        p = event.payload
        try:
            result = self.advise(
                p.get("kind", ""), p.get("topic", ""), p.get("script", ""),
                p.get("title", ""), p.get("description", ""), p.get("length", ""),
            )
        except DomainError as exc:
            self._events.publish(GROWTH_FAILED, event.key, {"detail": str(exc)})
            return
        except Exception as exc:  # noqa: BLE001 - el consumidor no debe morir nunca
            self._events.publish(GROWTH_FAILED, event.key, {"detail": f"{type(exc).__name__}: {exc}"})
            return
        self._events.publish(GROWTH_COMPLETED, event.key, {"kind": p.get("kind"), "result": result})
