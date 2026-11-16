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
from app.domain.production import length_by_id
from app.domain.writer import MIN_WORDS, build_prompt, system_prompt, validate_script

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

    def request(self, topic: str, notes: str = "", length: str = "reel", dialogue: bool = False) -> Event:
        """
        Encola la redacción y devuelve el evento con la clave del trabajo. La
        duración (reel o cortometraje) y el diálogo cambian lo que se pide.
        """
        if not topic.strip():
            raise ValidationError("Falta el tema.")
        length_by_id(length)  # que falle aquí, no en el consumidor
        if not self._writer.available():
            raise ValidationError("No hay clave de API configurada para redactar.")
        return self._events.publish(
            SCRIPT_REQUESTED,
            new_job_key(),
            {"topic": topic, "notes": notes, "length": length or "reel", "dialogue": bool(dialogue)},
        )

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

    def write(self, topic: str, notes: str = "", length: str = "reel", dialogue: bool = False) -> str:
        """Redacta ahora, bloqueando. Lo llama el consumidor, nunca la API."""
        target = length_by_id(length)
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
            system_prompt(target, dialogue),
            build_prompt(topic, notes),
        )
        # Muy por debajo de lo pedido no es un guion corto: es uno cortado.
        return validate_script(raw, min_words=max(MIN_WORDS, target.words[0] // 2), keep_lines=dialogue)

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
            payload = event.payload
            text = self.write(
                payload.get("topic", ""), payload.get("notes", ""),
                payload.get("length") or "reel", bool(payload.get("dialogue")),
            )
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
