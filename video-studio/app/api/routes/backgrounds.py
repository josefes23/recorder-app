from fastapi import APIRouter, UploadFile
from fastapi.responses import FileResponse

from app.api.deps import StudioDep
from app.api.schemas import DownloadRequest

router = APIRouter(prefix="/api", tags=["backgrounds"])


@router.get("/backgrounds")
def backgrounds(studio: StudioDep) -> dict:
    return {"items": [b.as_dict() for b in studio.backgrounds.list()]}


@router.get("/backgrounds/search")
def search_backgrounds(q: str, studio: StudioDep) -> dict:
    """Clips de Pexels para la búsqueda, con miniatura, para elegir antes de bajar nada."""
    return {"items": [c.as_dict() for c in studio.backgrounds.search(q)]}


@router.post("/backgrounds/download")
def download_backgrounds(req: DownloadRequest, studio: StudioDep) -> dict:
    report, items = studio.backgrounds.download(req.query, req.ids)
    return {
        "added": report.added,
        "existing": report.existing,
        "failed": report.failed,
        "items": [b.as_dict() for b in items],
    }


@router.get("/backgrounds/{name}/file")
def background_file(name: str, studio: StudioDep):
    """El fondo entero, para verlo o reproducirlo a tamaño grande."""
    return FileResponse(studio.backgrounds.file(name))


@router.delete("/backgrounds/{name}")
def delete_background(name: str, studio: StudioDep) -> dict:
    return {"deleted": name, "items": [b.as_dict() for b in studio.backgrounds.delete(name)]}


@router.get("/thumb/{name}")
def thumb(name: str, studio: StudioDep):
    return FileResponse(studio.backgrounds.thumbnail(name))


@router.post("/backgrounds/upload")
async def upload_background(file: UploadFile, studio: StudioDep) -> dict:
    name, items = studio.backgrounds.upload(file.filename, file.file)
    return {"name": name, "items": [b.as_dict() for b in items]}
