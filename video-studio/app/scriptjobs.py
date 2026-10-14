"""
Redacción de guiones como trabajo asíncrono, consumiendo del log de eventos.

Antes `POST /api/script` bloqueaba hasta que contestaba el modelo. Medido contra
NVIDIA: ochenta y ocho segundos. Ninguna petición HTTP debería durar eso —el
proxy de Next corta a los treinta— así que ahora la petición solo publica el
encargo y contesta al instante; el guion llega por el flujo de eventos cuando
está listo.
"""

from __future__ import annotations

import threading
from uuid import uuid4

from app import engine, eventlog, scriptgen
from app.eventlog import Event

REQUESTED = "script.requested"
COMPLETED = "script.completed"
FAILED = "script.failed"
TERMINAL = (COMPLETED, FAILED)

CONSUMER_GROUP = "scriptgen"

# Cada cuánto despierta el consumidor si no hay nada que hacer. No es sondeo:
# `wait_for` se despierta sola al publicarse; esto solo evita esperas eternas.
IDLE_TIMEOUT = 30.0


def request(topic: str, notes: str) -> Event:
    """Encola la redacción y devuelve el evento con la clave del trabajo."""
    job = f"sc-{uuid4().hex[:10]}"
    return eventlog.publish(REQUESTED, job, {"topic": topic, "notes": notes})


def _handle(event: Event) -> None:
    # Idempotencia: con entrega al menos una vez el mismo encargo puede llegar
    # dos veces tras un corte, y redactar dos veces cuesta dinero y minutos.
    if event.key is None or eventlog.settled(event.key, TERMINAL):
        return

    # Y si hay otro backend contra la misma base, que lo redacte solo uno.
    if not eventlog.claim(event.key):
        return

    try:
        text = scriptgen.write(event.payload.get("topic", ""), event.payload.get("notes", ""))
    except RuntimeError as exc:
        # Mensaje ya redactado para el usuario: viaja tal cual.
        eventlog.publish(FAILED, event.key, {"detail": str(exc)})
        return
    except Exception as exc:  # noqa: BLE001 - el hilo no debe morir nunca
        eventlog.publish(FAILED, event.key, {"detail": f"{type(exc).__name__}: {exc}"})
        return

    eventlog.publish(
        COMPLETED,
        event.key,
        {"script": text, "seconds": round(engine.estimate_seconds(text), 1)},
    )


def _worker() -> None:
    offset = eventlog.committed_offset(CONSUMER_GROUP)
    while True:
        for event in eventlog.wait_for(offset, IDLE_TIMEOUT, topics=(REQUESTED,)):
            _handle(event)
            # Se confirma después de trabajar: si el proceso muere en medio, el
            # encargo se vuelve a entregar en lugar de perderse.
            offset = event.offset
            eventlog.commit(CONSUMER_GROUP, offset)


def start() -> None:
    eventlog.prune()
    threading.Thread(target=_worker, daemon=True, name="script-consumer").start()
