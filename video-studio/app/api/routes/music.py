from fastapi import APIRouter, UploadFile
from fastapi.responses import FileResponse

from app.api.deps import StudioDep

router = APIRouter(prefix="/api", tags=["music"])


@router.get("/music")
def music(studio: StudioDep) -> dict:
    return {"items": [t.as_dict() for t in studio.music.list()]}


@router.post("/music/upload")
async def upload_music(file: UploadFile, studio: StudioDep) -> dict:
    name, items = studio.music.upload(file.filename, file.file)
    return {"name": name, "items": [t.as_dict() for t in items]}


@router.get("/music/{name}/file")
def music_file(name: str, studio: StudioDep):
    """La pista entera, para escucharla antes de elegirla."""
    return FileResponse(studio.music.file(name))


@router.delete("/music/{name}")
def delete_music(name: str, studio: StudioDep) -> dict:
    return {"deleted": name, "items": [t.as_dict() for t in studio.music.delete(name)]}
