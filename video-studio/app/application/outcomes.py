"""Desenlace de cualquier trabajo encolado, sea un guion o una imagen."""

from __future__ import annotations

from app.application.ports import EventLog
from app.domain.events import outcome_of


def job_outcome(events: EventLog, job: str) -> dict:
    """
    El evento que cerró el trabajo, o «pending» si aún no hay ninguno.

    Es la red de seguridad del flujo SSE: si el navegador se pierde el evento,
    el hecho sigue en el log. Qué tema cierra un trabajo lo decide la
    convención de `domain.events`, así que sirve para cualquier tipo nuevo.
    """
    for event in events.by_key(job):
        status = outcome_of(event.topic)
        if status != "pending":
            return {"status": status, **event.payload}
    return {"status": "pending"}
