from fastapi import APIRouter, HTTPException

from app.api.deps import StudioDep
from app.api.schemas import ElevenLabsKey
from app.application.use_cases.voice_catalog import voice_dict
from app.domain.style import DEFAULT_STYLE

router = APIRouter(prefix="/api", tags=["config"])


def _config(studio) -> dict:
    return {
        "voices": [voice_dict(v) for v in studio.voices.all()],
        "elevenlabs": studio.voices.elevenlabs(),
        "default_style": DEFAULT_STYLE,
        "writer": studio.writer.label(),
        "generator": studio.generator,
    }


@router.get("/config")
def config(studio: StudioDep) -> dict:
    return _config(studio)


@router.post("/elevenlabs")
def save_elevenlabs_key(req: ElevenLabsKey, studio: StudioDep) -> dict:
    """Guarda la clave de ElevenLabs (vacía la quita) y devuelve la configuración con sus voces."""
    try:
        studio.voices.save_key(req.api_key)
    except OSError as exc:
        raise HTTPException(500, f"No se pudo escribir el .env: {exc}") from exc
    return _config(studio)


@router.post("/elevenlabs/refresh")
def refresh_elevenlabs_voices(studio: StudioDep) -> dict:
    """Vuelve a pedir las voces de la cuenta, para ver al momento una recién agregada."""
    studio.voices.refresh()
    return _config(studio)
