from fastapi import APIRouter, HTTPException

from app.api.deps import StudioDep
from app.api.schemas import WriterRequest

router = APIRouter(prefix="/api", tags=["writer"])


@router.get("/writer")
def writer(studio: StudioDep) -> dict:
    """Proveedores, modelos disponibles y qué clave hay puesta (enmascarada)."""
    return studio.writer.settings()


@router.post("/writer")
def save_writer(req: WriterRequest, studio: StudioDep) -> dict:
    try:
        return studio.writer.save(req.provider, req.api_key, req.model)
    except OSError as exc:
        raise HTTPException(500, f"No se pudo escribir el .env: {exc}") from exc
