import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from app.api.deps import StudioDep

router = APIRouter(prefix="/api", tags=["events"])

# Cada cuánto se manda un comentario si no hay eventos, para que ni el navegador
# ni el proxy den la conexión por muerta.
HEARTBEAT_SECONDS = 15.0


@router.get("/outcomes/{job}")
def outcome(job: str, studio: StudioDep) -> dict:
    """Desenlace de cualquier trabajo encolado, para quien no haya visto pasar su evento."""
    return studio.outcome(job)


@router.get("/events")
async def events(request: Request, studio: StudioDep, after: int | None = None):
    """Flujo SSE del log de eventos.

    Sin `after` arranca en la cabeza: solo lo que pase a partir de ahora. El
    navegador reconecta solo y manda `Last-Event-ID`, así que un corte —el del
    proxy de desarrollo, sin ir más lejos— se reanuda en el offset exacto y no
    se pierde ningún evento. Esa es la gracia de tener posiciones.
    """
    log = studio.events
    resume = request.headers.get("last-event-id")
    if resume and resume.isdigit():
        start = int(resume)
    elif after is not None:
        start = after
    else:
        start = await run_in_threadpool(log.last_offset)

    async def stream():
        offset = start
        while not await request.is_disconnected():
            # La espera bloquea, así que va al pool de hilos y no al bucle.
            batch = await run_in_threadpool(log.wait_for, offset, HEARTBEAT_SECONDS)
            if not batch:
                yield ": ping\n\n"
                continue
            for event in batch:
                offset = event.offset
                # Sin `event:` a propósito: el tema viaja dentro del JSON y así
                # el cliente escucha una sola vez, sin conocer la lista de temas.
                yield f"id: {offset}\ndata: {json.dumps(event.as_dict(), ensure_ascii=False)}\n\n"

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
