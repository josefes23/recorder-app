from fastapi import APIRouter, HTTPException, Response

from app.api.deps import StudioDep
from app.api.schemas import PreviewRequest, RenderRequest
from app.domain.scene import Scene

router = APIRouter(prefix="/api", tags=["render"])


@router.post("/preview")
def preview(req: PreviewRequest, studio: StudioDep):
    try:
        png = studio.preview.frame(req.caption, req.style, req.background, req.topic)
    except Exception as exc:  # noqa: BLE001 - cualquier fallo del motor debe verse en la UI
        raise HTTPException(400, f"{type(exc).__name__}: {exc}") from exc
    return Response(png, media_type="image/png", headers={"Cache-Control": "no-store"})


@router.post("/render")
def render(req: RenderRequest, studio: StudioDep) -> dict:
    video_id, seconds = studio.render.start(
        topic=req.topic, script=req.script, voice=req.voice, rate=req.rate, pitch=req.pitch,
        style=req.style, scenes=[Scene(s.background, s.start) for s in req.scenes],
        cover=req.cover.model_dump() if req.cover else None,
        description=req.description,
    )
    return {"id": video_id, "seconds": seconds}


@router.get("/jobs/{video_id}")
def job_status(video_id: int, studio: StudioDep) -> dict:
    return studio.render.status(video_id)


@router.get("/jobs")
def active_jobs(studio: StudioDep) -> dict:
    return {"active": studio.render.active()}
