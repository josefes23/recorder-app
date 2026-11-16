from urllib.parse import quote

from fastapi import APIRouter, Response

from app.api.deps import StudioDep
from app.api.schemas import CoverRequest, TitlesRequest

router = APIRouter(prefix="/api", tags=["cover"])

JPEG = "image/jpeg"


@router.post("/cover")
def paint_cover(req: CoverRequest, studio: StudioDep):
    """La portada con lo que hay en el estudio ahora, a tamaño completo."""
    jpeg = studio.cover.paint(req.title, req.design, req.background, req.topic)
    return Response(jpeg, media_type=JPEG, headers={"Cache-Control": "no-store"})


@router.post("/cover/titles", status_code=202)
def request_titles(req: TitlesRequest, studio: StudioDep) -> dict:
    """Encola la propuesta de títulos. Llega por /api/events como `titles.completed`."""
    event = studio.cover.request_titles(req.topic, req.script)
    return {"job": event.key, "offset": event.offset}


@router.get("/videos/{video_id}/cover")
def video_cover(video_id: int, studio: StudioDep):
    """La portada guardada con el video, como archivo para descargar."""
    jpeg, filename = studio.cover.of_video(video_id)
    return Response(
        jpeg,
        media_type=JPEG,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
            "Cache-Control": "no-store",
        },
    )
