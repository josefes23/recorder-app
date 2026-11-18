from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.api.deps import StudioDep
from app.api.schemas import TakeIn

router = APIRouter(prefix="/api", tags=["takes"])


@router.post("/takes")
def make_take(req: TakeIn, studio: StudioDep) -> dict:
    """La voz del guion con sus marcas por palabra. Tarda lo que tarde edge-tts: unos segundos."""
    return studio.takes.take(req.script, req.voice, req.rate, req.pitch, req.voices).as_dict()


@router.get("/takes/{key}")
def take(key: str, studio: StudioDep) -> dict:
    return studio.takes.get(key).as_dict()


@router.get("/takes/{key}/audio")
def take_audio(key: str, studio: StudioDep):
    # La clave sale del contenido: el mismo audio siempre, así que el navegador lo guarda.
    return FileResponse(
        studio.takes.audio_of(key),
        media_type="audio/mpeg",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
