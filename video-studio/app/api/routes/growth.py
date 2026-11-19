from fastapi import APIRouter

from app.api.deps import StudioDep
from app.api.schemas import GrowthRequest

router = APIRouter(prefix="/api", tags=["growth"])


@router.post("/growth/{kind}", status_code=202)
def request_growth(kind: str, req: GrowthRequest, studio: StudioDep) -> dict:
    """Encola un consejo (hooks, retention, titles, seo, score, trends) o aplica una recomendación (apply). Llega por /api/events como `growth.completed`."""
    event = studio.growth.request(
        kind, req.topic, req.script, req.title, req.description, req.length, req.recommendation
    )
    return {"job": event.key, "offset": event.offset}
