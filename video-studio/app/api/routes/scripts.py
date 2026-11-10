from fastapi import APIRouter

from app.api.deps import StudioDep
from app.api.schemas import ScriptRequest

router = APIRouter(prefix="/api", tags=["script"])


@router.post("/script", status_code=202)
def write_script(req: ScriptRequest, studio: StudioDep) -> dict:
    """Encola la redacción. El guion llega por /api/events, no por aquí."""
    event = studio.scripts.request(req.topic, req.notes)
    return {"job": event.key, "offset": event.offset}


@router.get("/script/{job}")
def script_job(job: str, studio: StudioDep) -> dict:
    """Desenlace de un encargo, para quien no haya visto pasar su evento."""
    return studio.scripts.outcome(job)


@router.post("/script/template")
def template_script(req: ScriptRequest, studio: StudioDep) -> dict:
    draft = studio.scripts.from_template(req.topic)
    return {"script": draft.script, "seconds": draft.seconds}


@router.post("/estimate")
def estimate(req: ScriptRequest, studio: StudioDep) -> dict:
    # Por compatibilidad el texto viaja en `notes`.
    result = studio.scripts.estimate(req.notes)
    return {"seconds": result.seconds, "words": result.words, "in_range": result.in_range}
