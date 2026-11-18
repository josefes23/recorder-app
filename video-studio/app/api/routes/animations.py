from fastapi import APIRouter

from app.api.deps import StudioDep
from app.api.schemas import AnimationRequest

router = APIRouter(prefix="/api", tags=["animations"])


@router.get("/animations")
def animation_settings(studio: StudioDep) -> dict:
    """Con qué se animan las escenas, su precio orientativo y si la clave está puesta."""
    return studio.animations.settings()


@router.post("/animations", status_code=202)
def request_animation(req: AnimationRequest, studio: StudioDep) -> dict:
    """
    Encola la animación de una imagen de la galería. El clip llega por
    /api/events como `animation.completed`, con su nombre en la galería.
    """
    event = studio.animations.request(
        req.topic,
        req.source,
        req.seconds,
        req.description,
        req.look,
        [c.model_dump() for c in req.characters],
        req.seed,
        req.format,
        req.motion,
    )
    return {"job": event.key, "offset": event.offset}
