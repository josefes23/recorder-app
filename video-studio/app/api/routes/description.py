from fastapi import APIRouter

from app.api.deps import StudioDep
from app.api.schemas import DescriptionRequest

router = APIRouter(prefix="/api", tags=["description"])


@router.post("/description", status_code=202)
def request_description(req: DescriptionRequest, studio: StudioDep) -> dict:
    """Encola la descripción para publicar. Llega por /api/events como `description.completed`."""
    event = studio.description.request(req.topic, req.script, req.title)
    return {"job": event.key, "offset": event.offset}
