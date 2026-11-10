from fastapi import APIRouter
from fastapi.responses import FileResponse

from app.api.deps import StudioDep

router = APIRouter(prefix="/api", tags=["library"])


@router.get("/videos")
def videos(studio: StudioDep) -> dict:
    return {"items": [v.as_dict() for v in studio.library.list()]}


@router.get("/videos/{video_id}/file")
def video_file(video_id: int, studio: StudioDep):
    path = studio.library.file_of(video_id)
    return FileResponse(path, media_type="video/mp4", filename=path.name)


@router.delete("/videos/{video_id}")
def remove_video(video_id: int, studio: StudioDep) -> dict:
    studio.library.delete(video_id)
    return {"deleted": video_id}
