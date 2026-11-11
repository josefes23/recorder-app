from fastapi import APIRouter, HTTPException

from app.api.deps import StudioDep
from app.api.schemas import IllustrationRequest, ImageSettingsRequest, StoryboardRequest

router = APIRouter(prefix="/api", tags=["illustrations"])


@router.get("/images")
def image_settings(studio: StudioDep) -> dict:
    """Generadores de imagen, sus modelos y qué datos hay puestos (las claves, enmascaradas)."""
    return studio.images.settings()


@router.post("/images")
def save_image_settings(req: ImageSettingsRequest, studio: StudioDep) -> dict:
    try:
        return studio.images.save(req.provider, req.model, req.values)
    except OSError as exc:
        raise HTTPException(500, f"No se pudo escribir el .env: {exc}") from exc


@router.post("/storyboards", status_code=202)
def request_storyboard(req: StoryboardRequest, studio: StudioDep) -> dict:
    """
    Encola el guion visual: estilo, reparto y lo que se ve en cada escena. Llega
    por /api/events como `storyboard.completed`.
    """
    event = studio.storyboards.request(
        req.topic, req.script, req.style, [c.model_dump() for c in req.characters]
    )
    return {"job": event.key, "offset": event.offset}


@router.post("/illustrations", status_code=202)
def request_illustration(req: IllustrationRequest, studio: StudioDep) -> dict:
    """Encola una imagen. Llega por /api/events como `illustration.completed`."""
    event = studio.illustrations.request(
        req.topic,
        req.description,
        req.look,
        [c.model_dump() for c in req.characters],
        req.seed,
        req.provider,
        req.model,
        req.review,
    )
    return {"job": event.key, "offset": event.offset}
