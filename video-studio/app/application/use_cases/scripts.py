"""
Redacción del guion.

La petición HTTP solo publica el encargo y contesta al instante; el guion llega
por el flujo de eventos cuando el modelo termina. Redactar tarda decenas de
segundos —medido contra NVIDIA, ochenta y ocho— y ninguna petición debería
durar eso: el proxy de Next corta a los treinta.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.ports import EventLog, ScriptComposer, ScriptTemplate
from app.application.use_cases.writer_settings import WriterSettings
from app.domain.errors import DomainError, ValidationError, WriterError
from app.domain.events import (
    SCRIPT_COMPLETED,
    SCRIPT_FAILED,
    SCRIPT_REQUESTED,
    SCRIPT_TERMINAL,
    Event,
    new_job_key,
    outcome_of,
)
from app.domain.script import ScriptEstimate, clean_script, estimate, estimate_seconds
from app.domain.writer import SYSTEM_PROMPT, build_prompt, validate_script

CONSUMER_GROUP = "scriptgen"


@dataclass(frozen=True)
class ScriptDraft:
    script: str
    seconds: float


class ScriptUseCases:
    def __init__(
        self,
        events: EventLog,
        writer: WriterSettings,
        composer: ScriptComposer,
        template: ScriptTemplate,
    ) -> None:
        self._events = events
        self._writer = writer
        self._composer = composer
        self._template = template

    # Desde la API ------------------------------------------------------------ #

    def request(self, topic: str, notes: str = "") -> Event:
        """Encola la redacción y devuelve el evento con la clave del trabajo."""
        if not topic.strip():
            raise ValidationError("Falta el tema.")
        if not self._writer.available():
            raise ValidationError("No hay clave de API configurada para redactar.")
        return self._events.publish(SCRIPT_REQUESTED, new_job_key(), {"topic": topic, "notes": notes})

    def outcome(self, job: str) -> dict:
        """Desenlace de un encargo, para quien no haya visto pasar su evento.

        El flujo SSE es la vía rápida, pero si un navegador se pierde el evento
        —una pestaña dormida, una recarga a destiempo— el hecho sigue en el log
        y se puede preguntar por él. La red de seguridad es esta, no reintentar.
        """
        for event in self._events.by_key(job, SCRIPT_TERMINAL):
            return {"status": outcome_of(event.topic), **event.payload}
        return {"status": "pending"}

    def from_template(self, topic: str) -> ScriptDraft:
        """La plantilla es local e instantánea, así que se resuelve en el acto."""
        text = clean_script(self._template.template(topic))
        return ScriptDraft(text, round(estimate_seconds(text), 1))

    def estimate(self, text: str) -> ScriptEstimate:
        return estimate(text)

    # Desde el consumidor ------------------------------------------------------ #

    def write(self, topic: str, notes: str = "") -> str:
        """Redacta ahora, bloqueando. Lo llama el consumidor, nunca la API."""
        provider = self._writer.active()
        if provider is None:
            raise WriterError(
                "No hay clave de API configurada. Añade una en «Modelo del guion», "
                "o escribe el guion a mano en el cuadro de texto."
            )
        raw = self._composer.compose(
            provider,
            self._writer.model_for(provider),
            self._writer.api_key(provider),
            SYSTEM_PROMPT,
            build_prompt(topic, notes),
        )
        return validate_script(raw)

    def handle_request(self, event: Event) -> None:
        """Atiende un `script.requested` y publica su desenlace."""
        # Idempotencia: con entrega al menos una vez el mismo encargo puede
        # llegar dos veces tras un corte, y redactar dos veces cuesta dinero.
        if event.key is None or self._events.settled(event.key, SCRIPT_TERMINAL):
            return

        # Y si hay otro backend contra la misma base, que lo redacte solo uno.
        if not self._events.claim(event.key):
            return

        try:
            text = self.write(event.payload.get("topic", ""), event.payload.get("notes", ""))
        except DomainError as exc:
            # Mensaje ya redactado para el usuario: viaja tal cual.
            self._events.publish(SCRIPT_FAILED, event.key, {"detail": str(exc)})
            return
        except Exception as exc:  # noqa: BLE001 - el consumidor no debe morir nunca
            self._events.publish(SCRIPT_FAILED, event.key, {"detail": f"{type(exc).__name__}: {exc}"})
            return

        self._events.publish(
            SCRIPT_COMPLETED,
            event.key,
            {"script": text, "seconds": round(estimate_seconds(text), 1)},
        )
