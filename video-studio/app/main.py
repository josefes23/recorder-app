"""API local de video-studio. Se abre en localhost; no está pensada para exponerse."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app import db, engine, eventlog, jobs, scriptgen, scriptjobs

app = FastAPI(title="video-studio", docs_url=None, redoc_url=None)
jobs.start()
scriptjobs.start()

# --------------------------------------------------------------------------- #
# Modelos de entrada
# --------------------------------------------------------------------------- #

class ScriptRequest(BaseModel):
    topic: str
    notes: str = ""


class WriterRequest(BaseModel):
    provider: str
    api_key: str = ""
    model: str = ""


class Scene(BaseModel):
    background: str | None = None
    start: float = 0.0


class PreviewRequest(BaseModel):
    caption: str = ""
    topic: str = ""
    background: str | None = None
    style: dict = Field(default_factory=dict)


class RenderRequest(BaseModel):
    topic: str
    script: str
    voice: str = "es-MX-DaliaNeural"
    rate: str = "+8%"
    pitch: str = "+0Hz"
    style: dict = Field(default_factory=dict)
    scenes: list[Scene] = Field(default_factory=list)


class FetchRequest(BaseModel):
    query: str
    count: int = 4


# --------------------------------------------------------------------------- #
# Guion
# --------------------------------------------------------------------------- #

@app.get("/api/config")
def config() -> dict:
    return {
        "voices": [{"id": v, "label": label} for v, label in engine.VOICES],
        "default_style": engine.DEFAULT_STYLE,
        "writer": scriptgen.label(),
        "generator": str(engine.GENERATOR),
    }


@app.get("/api/writer")
def writer() -> dict:
    """Proveedores, modelos disponibles y qué clave hay puesta (enmascarada)."""
    return scriptgen.settings()


@app.post("/api/writer")
def save_writer(req: WriterRequest) -> dict:
    try:
        return scriptgen.save_settings(req.provider, req.api_key, req.model)
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc
    except OSError as exc:
        raise HTTPException(500, f"No se pudo escribir el .env: {exc}") from exc


@app.post("/api/script", status_code=202)
def write_script(req: ScriptRequest) -> dict:
    """Encola la redacción. El guion llega por /api/events, no por aquí.

    Redactar tarda decenas de segundos: sostener la petición abierta mientras
    tanto es lo que provocaba los cortes del proxy en desarrollo.
    """
    if not req.topic.strip():
        raise HTTPException(400, "Falta el tema.")
    if not scriptgen.available():
        raise HTTPException(400, "No hay clave de API configurada para redactar.")

    event = scriptjobs.request(req.topic, req.notes)
    return {"job": event.key, "offset": event.offset}


@app.get("/api/script/{job}")
def script_job(job: str) -> dict:
    """Desenlace de un encargo, para quien no haya visto pasar su evento.

    El flujo SSE es la vía rápida, pero si un navegador se pierde el evento —una
    pestaña dormida, una recarga a destiempo— el hecho sigue en el log y se
    puede preguntar por él. La red de seguridad es esta, no reintentar el guion.
    """
    for event in eventlog.by_key(job, scriptjobs.TERMINAL):
        return {"status": event.topic.rsplit(".", 1)[-1], **event.payload}
    return {"status": "pending"}


@app.post("/api/script/template")
def template_script(req: ScriptRequest) -> dict:
    """La plantilla es local e instantánea, así que sigue siendo síncrona."""
    text = scriptgen.fallback(req.topic)
    return {"script": text, "seconds": round(engine.estimate_seconds(text), 1)}


# --------------------------------------------------------------------------- #
# Flujo de eventos
# --------------------------------------------------------------------------- #

# Cada cuánto se manda un comentario si no hay eventos, para que ni el navegador
# ni el proxy den la conexión por muerta.
HEARTBEAT_SECONDS = 15.0


@app.get("/api/events")
async def events(request: Request, after: int | None = None):
    """Flujo SSE del log de eventos.

    Sin `after` arranca en la cabeza: solo lo que pase a partir de ahora. El
    navegador reconecta solo y manda `Last-Event-ID`, así que un corte —el del
    proxy de desarrollo, sin ir más lejos— se reanuda en el offset exacto y no
    se pierde ningún evento. Esa es la gracia de tener posiciones.
    """
    resume = request.headers.get("last-event-id")
    if resume and resume.isdigit():
        start = int(resume)
    elif after is not None:
        start = after
    else:
        start = await run_in_threadpool(eventlog.last_offset)

    async def stream():
        offset = start
        while not await request.is_disconnected():
            # La espera bloquea, así que va al pool de hilos y no al bucle.
            batch = await run_in_threadpool(eventlog.wait_for, offset, HEARTBEAT_SECONDS)
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


@app.post("/api/estimate")
def estimate(req: ScriptRequest) -> dict:
    seconds = engine.estimate_seconds(req.notes)
    return {
        "seconds": round(seconds, 1),
        "words": len(engine.clean_script(req.notes).split()),
        "in_range": 28 <= seconds <= 48,
    }


# --------------------------------------------------------------------------- #
# Fondos
# --------------------------------------------------------------------------- #

@app.get("/api/backgrounds")
def backgrounds() -> dict:
    return {"items": engine.list_backgrounds()}


@app.get("/api/thumb/{name}")
def thumb(name: str):
    path = engine.THUMBS / Path(name).name
    if not path.is_file():
        raise HTTPException(404, "Miniatura no encontrada.")
    return FileResponse(path)


@app.post("/api/backgrounds/fetch")
def fetch_backgrounds(req: FetchRequest) -> dict:
    """Descarga clips de Pexels reutilizando el script del generador."""
    import subprocess
    import sys

    script = engine.GENERATOR / "scripts" / "fetch_backgrounds.py"
    if not script.is_file():
        raise HTTPException(400, "No encuentro fetch_backgrounds.py en el generador.")

    result = subprocess.run(
        [sys.executable, str(script), "--query", req.query, "--count", str(req.count)],
        capture_output=True, text=True, timeout=600,
    )
    if result.returncode != 0:
        raise HTTPException(400, (result.stdout + result.stderr).strip()[-600:])
    return {"log": result.stdout.strip(), "items": engine.list_backgrounds()}


@app.post("/api/backgrounds/upload")
async def upload_background(file: UploadFile) -> dict:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in (engine.VIDEO_EXTS | engine.IMAGE_EXTS):
        raise HTTPException(400, f"Formato no admitido: {suffix or 'sin extensión'}")
    target = engine.background_dir() / Path(file.filename).name
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("wb") as fh:
        shutil.copyfileobj(file.file, fh)
    return {"name": target.name, "items": engine.list_backgrounds()}


# --------------------------------------------------------------------------- #
# Previsualización y render
# --------------------------------------------------------------------------- #

@app.post("/api/preview")
def preview(req: PreviewRequest):
    try:
        png = engine.preview_frame(req.caption, req.style, req.background, req.topic)
    except Exception as exc:  # noqa: BLE001 - cualquier fallo debe verse en la UI
        raise HTTPException(400, f"{type(exc).__name__}: {exc}") from exc
    return Response(png, media_type="image/png", headers={"Cache-Control": "no-store"})


@app.post("/api/render")
def render(req: RenderRequest) -> dict:
    script = engine.clean_script(req.script)
    if not script:
        raise HTTPException(400, "El guion está vacío.")

    scenes = [s.model_dump() for s in req.scenes]
    video_id = db.create_video(req.topic, script, req.voice, req.style, scenes)
    jobs.enqueue(video_id, {
        "topic": req.topic, "script": script, "voice": req.voice,
        "rate": req.rate, "pitch": req.pitch, "style": req.style, "scenes": scenes,
    })
    return {"id": video_id, "seconds": round(engine.estimate_seconds(script), 1)}


@app.get("/api/jobs/{video_id}")
def job_status(video_id: int) -> dict:
    live = jobs.status(video_id)
    record = db.get_video(video_id)
    if not record:
        raise HTTPException(404, "No existe ese video.")
    return {**record, **live, "id": video_id}


@app.get("/api/jobs")
def active_jobs() -> dict:
    return {"active": jobs.all_active()}


# --------------------------------------------------------------------------- #
# Biblioteca
# --------------------------------------------------------------------------- #

@app.get("/api/videos")
def videos() -> dict:
    return {"items": db.list_videos()}


@app.get("/api/videos/{video_id}/file")
def video_file(video_id: int):
    record = db.get_video(video_id)
    if not record or not record.get("filename"):
        raise HTTPException(404, "Ese video todavía no tiene archivo.")
    path = Path(record["filename"])
    if not path.is_file():
        raise HTTPException(404, "El archivo ya no está en el disco.")
    return FileResponse(path, media_type="video/mp4", filename=path.name)


@app.delete("/api/videos/{video_id}")
def remove_video(video_id: int) -> dict:
    if not db.get_video(video_id):
        raise HTTPException(404, "No existe ese video.")
    db.delete_video(video_id)
    return {"deleted": video_id}


# --------------------------------------------------------------------------- #

# La interfaz es Next.js. En desarrollo la sirve `npm run dev` en :3000 (con las
# llamadas a /api reescritas hacia aquí); en producción se exporta a web/out y la
# servimos nosotros, para que todo quede en un solo proceso y un solo puerto.
WEB_BUILD = Path(__file__).resolve().parent.parent / "web" / "out"


@app.get("/")
def index():
    if not WEB_BUILD.is_dir():
        return PlainTextResponse(
            "La interfaz no está compilada todavía.\n\n"
            "  ./run.sh          la compila y la sirve aquí mismo\n"
            "  ./run.sh --dev    Next con recarga en caliente en :3000\n",
            status_code=503,
        )
    return FileResponse(WEB_BUILD / "index.html")


if WEB_BUILD.is_dir():
    # Va al final a propósito: montado en "/" captura todo lo que no haya
    # coincidido antes, y las rutas /api están declaradas más arriba.
    app.mount("/", StaticFiles(directory=WEB_BUILD, html=True), name="web")
