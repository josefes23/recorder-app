"""Biblioteca de elementos que se repiten entre videos, con su imagen de referencia."""

from fastapi import APIRouter, Response
from fastapi.responses import FileResponse

from app.api.deps import StudioDep
from app.api.schemas import CharacterSave, ReferenceRequest

router = APIRouter(prefix="/api", tags=["characters"])


@router.get("/characters")
def list_characters(studio: StudioDep) -> list[dict]:
    """Lo guardado, lo último primero."""
    return studio.characters.list()


@router.post("/characters", status_code=202)
def save_character(req: CharacterSave, studio: StudioDep) -> dict:
    """
    Guarda (o actualiza por nombre) y encarga su imagen de referencia si hace
    falta. Llega por /api/events como `reference.completed`; `job` es null si la
    que tenía sigue valiendo.
    """
    saved, event = studio.characters.save(req.name, req.traits, req.kind, req.look, req.provider, req.model)
    return {"character": saved.as_dict(), "job": event.key if event else None}


@router.post("/characters/{character_id}/reference", status_code=202)
def repaint_reference(character_id: int, req: ReferenceRequest, studio: StudioDep) -> dict:
    event = studio.characters.repaint(character_id, req.look, req.provider, req.model)
    return {"job": event.key, "offset": event.offset}


@router.delete("/characters/{character_id}", status_code=204)
def delete_character(character_id: int, studio: StudioDep) -> Response:
    studio.characters.remove(character_id)
    return Response(status_code=204)


@router.get("/references/{name}")
def reference(name: str, studio: StudioDep):
    return FileResponse(studio.characters.reference_file(name))
