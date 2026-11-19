from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.api.deps import StudioDep
from app.api.schemas import SampleIn, TakeIn
from app.domain.voice import SAMPLE_TEXT

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


@router.post("/samples")
def make_sample(req: SampleIn, studio: StudioDep) -> dict:
    """
    Cómo suena una voz: una frase corta en español. Con edge-tts es gratis; con
    ElevenLabs gasta unos pocos créditos, una sola vez: la misma prueba se reutiliza.
    """
    return studio.samples.take(SAMPLE_TEXT, req.voice, req.rate, req.pitch, {}).as_dict()


@router.get("/samples/{key}/audio")
def sample_audio(key: str, studio: StudioDep):
    return FileResponse(
        studio.samples.audio_of(key),
        media_type="audio/mpeg",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )
