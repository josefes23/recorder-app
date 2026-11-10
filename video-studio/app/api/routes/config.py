from fastapi import APIRouter

from app.api.deps import StudioDep
from app.domain.style import DEFAULT_STYLE
from app.domain.voice import VOICES

router = APIRouter(prefix="/api", tags=["config"])


@router.get("/config")
def config(studio: StudioDep) -> dict:
    return {
        "voices": [{"id": v.id, "label": v.label} for v in VOICES],
        "default_style": DEFAULT_STYLE,
        "writer": studio.writer.label(),
        "generator": studio.generator,
    }
